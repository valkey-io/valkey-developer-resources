"""CI tests for the "KV Caching with Valkey" cookbook.

Two tiers:

1. **Always run, no stack needed.** The reader-facing Valkey L2 adapter spec is
   well-formed and matches what ``docker-compose.yml`` passes to the standalone
   ``lmcache server``, and the compose file wires both vLLM replicas to that
   server (and the server to Valkey) the way the notebook expects. These catch
   typos in the files a reader edits without booting a 4-container stack.

2. **Run only when the stack is up** (``docker compose up -d --wait``). These
   drive the same signals the notebook shows: Valkey is reachable, both replicas
   serve the model, a cold request grows ``dbsize`` (KV written through to
   Valkey), and a request on the second replica that shares the prefix reads it
   back (Valkey ``GET``/``MGET`` calls increase). They read Valkey over the
   network with the Valkey GLIDE client, like the notebook, so they work with
   any container runtime (Docker, Podman, nerdctl). They ``skip`` when the
   stack isn't running so the config/structure tier still passes in a bare CI
   job.
"""

from __future__ import annotations

import os
import socket
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "lmcache_config.yaml"
COMPOSE_PATH = HERE / "docker-compose.yml"

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
# The L2 adapter type + the Valkey the lmcache server writes through to.
L2_ADAPTER_TYPE = "valkey"
VALKEY_STARTUP_NODES = "valkey:6379"
REPLICA_A = "http://localhost:8001"
REPLICA_B = "http://localhost:8002"
# Valkey as published by docker-compose.yml (127.0.0.1:6379); overridable the
# same way the CI workflow exposes its Valkey service.
VALKEY_HOST = os.environ.get("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


# ---------------------------------------------------------------------------
# Tier 1: config + compose wiring (no stack required)
# ---------------------------------------------------------------------------
class TestL2AdapterConfig:
    """The documented Valkey L2 adapter spec is well-formed."""

    @pytest.fixture(scope="class")
    def config(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(CONFIG_PATH.read_text())

    def test_adapter_points_at_valkey(self, config):
        assert config["type"] == L2_ADAPTER_TYPE
        assert config["startup_nodes"] == VALKEY_STARTUP_NODES

    def test_demo_defaults_are_local(self, config):
        # The single-node CPU demo runs standalone, no TLS.
        assert config["cluster_mode"] is False
        assert config["tls_enable"] is False


class TestComposeWiring:
    """docker-compose.yml must wire vLLM -> lmcache server -> Valkey."""

    @pytest.fixture(scope="class")
    def compose(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(COMPOSE_PATH.read_text())

    def test_four_services(self, compose):
        assert set(compose["services"]) == {
            "valkey",
            "lmcache-server",
            "vllm-a",
            "vllm-b",
        }

    def test_valkey_pinned_bundle(self, compose):
        image = compose["services"]["valkey"]["image"]
        assert image.startswith("valkey/valkey-bundle:")
        assert ":latest" not in image

    def test_lmcache_server_uses_valkey_l2_adapter(self, compose):
        server = compose["services"]["lmcache-server"]
        command = server["command"]
        command_text = " ".join(command) if isinstance(command, list) else command
        # The Valkey L2 adapter needs the sync glide client specifically.
        assert "valkey-glide-sync" in command_text
        # The server runs and points its L2 tier at Valkey.
        assert "lmcache server" in command_text
        assert "--l2-adapter" in command_text
        # The L2 adapter JSON names the valkey type and the Valkey service.
        assert '"type":"valkey"' in command_text.replace(" ", "")
        assert VALKEY_STARTUP_NODES in command_text
        # skip_l1 makes L1 a write buffer only, so reads come from Valkey (L2) —
        # otherwise the demo would serve every reuse from L1 and never read Valkey.
        assert "--l2-store-policy skip_l1" in command_text
        # CPU workers use the engine-driven transfer path; "auto" loads it.
        assert "--supported-transfer-mode auto" in command_text
        # Wait for a healthy Valkey before starting.
        assert server["depends_on"]["valkey"]["condition"] == "service_healthy"

    @pytest.mark.parametrize("svc", ["vllm-a", "vllm-b"])
    def test_replica_wired_to_lmcache_server_via_mp_connector(self, compose, svc):
        service = compose["services"][svc]
        # Official vLLM CPU image, pinned to the v0.28.0 tag (optionally by
        # digest as well, e.g. ...:v0.28.0@sha256:...).
        assert service["image"].startswith("vllm/vllm-openai-cpu:v0.28.0")
        assert ":latest" not in service["image"]
        command = service["command"]
        command_text = " ".join(command) if isinstance(command, list) else command
        # LMCache is not bundled in the CPU image, so it is installed on startup.
        assert "pip install" in command_text and "lmcache" in command_text
        # The CPU build has no in-worker KV connector, so KV is handed to the
        # standalone lmcache server via the multi-process connector.
        assert "LMCacheMPConnector" in command_text
        # Both replicas point at the same lmcache server host/port.
        packed = command_text.replace(" ", "")
        assert '"lmcache.mp.host":"tcp://lmcache-server"' in packed
        assert '"lmcache.mp.port":5555' in packed
        # vLLM's multiprocess executor needs more than the default 64 MiB shm.
        assert service["shm_size"]
        # Wait for a healthy lmcache server before starting.
        assert service["depends_on"]["lmcache-server"]["condition"] == "service_healthy"

    def test_both_replicas_share_one_lmcache_server(self, compose):
        commands = {}
        for svc in ("vllm-a", "vllm-b"):
            c = compose["services"][svc]["command"]
            commands[svc] = " ".join(c) if isinstance(c, list) else c
        # Same connector config in both -> same lmcache server -> shared cache.
        assert "tcp://lmcache-server" in commands["vllm-a"]
        assert "tcp://lmcache-server" in commands["vllm-b"]


# ---------------------------------------------------------------------------
# Tier 2: live stack (skipped unless the stack is up)
# ---------------------------------------------------------------------------
def _connect_valkey():
    """A Valkey GLIDE (sync) client on the published Valkey port."""
    from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

    return GlideClient.create(
        GlideClientConfiguration(
            addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
            request_timeout=2000,
        )
    )


def _valkey_running() -> bool:
    # Cheap TCP probe first: with nothing listening, GLIDE would retry the
    # connection for a few seconds (and log each attempt) before giving up.
    try:
        socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=2).close()
    except OSError:
        return False
    try:
        client = _connect_valkey()
    except Exception:
        return False
    try:
        return client.ping() in (b"PONG", "PONG")
    except Exception:
        return False
    finally:
        client.close()


def _replica_healthy(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _stack_up() -> bool:
    """The live tests need Valkey *and* both replicas — not just one of them."""
    return (
        _valkey_running()
        and _replica_healthy(REPLICA_A)
        and _replica_healthy(REPLICA_B)
    )


requires_stack = pytest.mark.skipif(
    not _stack_up(),
    reason="full stack not running; `docker compose up -d --wait` to run live tests",
)


@pytest.fixture(scope="module")
def valkey():
    pytest.importorskip("glide_sync")
    client = _connect_valkey()
    yield client
    client.close()


def _dbsize(valkey) -> int:
    return int(valkey.custom_command(["DBSIZE"]))


def _settled_dbsize(valkey, quiet_s: float = 1.0, timeout_s: float = 15.0) -> int:
    """``dbsize`` once it has stopped changing for ``quiet_s`` seconds.

    The LMCache server writes KV through to Valkey asynchronously, so a read
    taken right after a response can miss keys that are still in flight.
    """
    deadline = time.monotonic() + timeout_s
    last, since = _dbsize(valkey), time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        current = _dbsize(valkey)
        if current != last:
            last, since = current, time.monotonic()
        elif time.monotonic() - since >= quiet_s:
            break
    return last


def _valkey_get_calls(valkey) -> int:
    """Cumulative Valkey GET/MGET calls, from INFO commandstats.

    With the server's ``--l2-store-policy skip_l1`` (L1 is a write buffer only),
    a cache *read* has to come from Valkey, so reuse shows up as GET calls here.
    """
    info = valkey.custom_command(["INFO", "commandstats"])
    if isinstance(info, bytes):
        info = info.decode()
    total = 0
    for line in info.splitlines():
        if line.startswith(("cmdstat_get:", "cmdstat_mget:")):
            for field in line.split(":", 1)[1].split(","):
                if field.startswith("calls="):
                    total += int(field.split("=", 1)[1])
    return total


@pytest.fixture(scope="module")
def clients():
    openai = pytest.importorskip("openai")
    a = openai.OpenAI(base_url=f"{REPLICA_A}/v1", api_key="not-needed")
    b = openai.OpenAI(base_url=f"{REPLICA_B}/v1", api_key="not-needed")
    return a, b


# KV is stored in whole chunks (LMCache's default is 256 tokens), so the demo
# conversation must be long enough to fill at least one chunk for KV to land in
# Valkey. A short greeting would store nothing. A per-run nonce keeps the prefix
# unique, so the "cold" turn is genuinely cold even if a previous run left KV in
# Valkey (the test never depends on a flushed store).

_LONG_CONTEXT_BODY = (
    "You are a concise assistant that answers questions about world geography. "
    + "Consider the following reference facts carefully before answering. " * 60
)


def _fresh_system_message():
    nonce = uuid.uuid4().hex
    return {"role": "system", "content": f"[session {nonce}] {_LONG_CONTEXT_BODY}"}


@requires_stack
def test_both_replicas_serve_the_model(clients):
    a, b = clients
    assert MODEL in [m.id for m in a.models.list().data]
    assert MODEL in [m.id for m in b.models.list().data]


@requires_stack
def test_cold_stores_kv_in_valkey_then_warm_and_cross_replica_reuse(clients, valkey):
    """The signals the notebook shows, in one flow.

    KV storage is owned by the shared LMCache server. It runs with
    ``--l2-store-policy skip_l1``, so L1 is only a write buffer and reads come
    from Valkey (L2). That gives two Valkey-observable signals:

      * a cold turn *stores* KV in Valkey (``dbsize`` grows), and
      * a request on a second replica that shares the prefix *reads* that KV
        back from Valkey (GET calls increment) instead of recomputing it —
        proving the cache is genuinely shared through Valkey, not held in one
        engine's memory.
    """
    a, b = clients
    system = _fresh_system_message()
    prefix = [
        system,
        {"role": "user", "content": "What is the capital of France?"},
    ]

    # Turn 1 (cold): full prefill on replica A. This prefix is unique to this
    # run, so its KV cannot already be cached. LMCache writes the KV through to
    # Valkey (L2), so the key count grows. The write-through is asynchronous,
    # so read the count once it has settled rather than right after the reply.
    before = _settled_dbsize(valkey)
    r1 = a.chat.completions.create(
        model=MODEL, messages=prefix, max_tokens=32, temperature=0.0,
    )
    assert r1.choices[0].message.content is not None
    after_cold = _settled_dbsize(valkey)
    assert after_cold > before, "cold turn should store KV blocks in Valkey"

    # Turn 2 (warm, shared prefix on replica A): the prefix is already cached, so
    # this is a hit for that prefix, not a re-store — it does not re-write the
    # prefix's KV. (A little growth from the new tokens in the follow-up question
    # is fine; the point is the cached prefix is not stored again.)
    warm = prefix + [
        {"role": "assistant", "content": r1.choices[0].message.content},
        {"role": "user", "content": "What about Italy?"},
    ]
    a.chat.completions.create(
        model=MODEL, messages=warm, max_tokens=32, temperature=0.0,
    )
    assert _settled_dbsize(valkey) >= after_cold, "warm turn must not lose the cached KV"

    # Cross-replica: replica B has served no traffic, but the KV for this exact
    # prefix lives in Valkey. B reads it back from Valkey rather than recomputing
    # or re-storing it: GET calls increment and the key count does not grow.
    # Keys are never removed in this stack (eviction policy noop, no TTL), so
    # the count cannot drop back: sample it only after the earlier turns' async
    # writes have landed, and compare once B's own writes (if any) would have.
    gets_before = _valkey_get_calls(valkey)
    before_b = _settled_dbsize(valkey)
    r3 = b.chat.completions.create(
        model=MODEL, messages=prefix, max_tokens=32, temperature=0.0,
    )
    assert r3.choices[0].message.content is not None
    assert _valkey_get_calls(valkey) > gets_before, (
        "replica B should read the shared prefix's KV from Valkey (L2)"
    )
    assert _settled_dbsize(valkey) == before_b, (
        "replica B should reuse the shared cache, not re-store the same prefix"
    )
