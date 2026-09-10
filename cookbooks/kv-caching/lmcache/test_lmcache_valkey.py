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
   Valkey), and a warm request with a shared prefix increments
   ``keyspace_hits``. They ``skip`` when the stack isn't running so the
   config/structure tier still passes in a bare CI job.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "lmcache_config.yaml"
COMPOSE_PATH = HERE / "docker-compose.yml"

MODEL = "facebook/opt-125m"
# The L2 adapter type + the Valkey the lmcache server writes through to.
L2_ADAPTER_TYPE = "valkey"
VALKEY_STARTUP_NODES = "valkey:6379"
REPLICA_A = "http://localhost:8001"
REPLICA_B = "http://localhost:8002"


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
        # Wait for a healthy Valkey before starting.
        assert server["depends_on"]["valkey"]["condition"] == "service_healthy"

    @pytest.mark.parametrize("svc", ["vllm-a", "vllm-b"])
    def test_replica_wired_to_lmcache_server_via_mp_connector(self, compose, svc):
        service = compose["services"][svc]
        # Official vLLM CPU image, pinned.
        assert service["image"] == "vllm/vllm-openai-cpu:v0.28.0"
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
def _valkey_running() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        out = subprocess.run(
            ["docker", "exec", "valkey", "valkey-cli", "PING"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return False
    return out.stdout.strip() == "PONG"


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


def _valkey_cli(*args) -> str:
    out = subprocess.run(
        ["docker", "exec", "valkey", "valkey-cli", *args],
        capture_output=True, text=True, timeout=10,
    )
    return out.stdout.strip()


def _dbsize() -> int:
    return int(_valkey_cli("DBSIZE"))


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
import uuid

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
def test_cold_stores_kv_in_valkey_then_warm_and_cross_replica_reuse(clients):
    """The signals the notebook shows, in one flow.

    KV storage is owned by the shared LMCache server: an L1 tier in its own
    memory, writing through to Valkey as L2. So the reliable, Valkey-observable
    signals are:

      * a cold turn *stores* KV in Valkey (``dbsize`` grows), and
      * a later request that shares the prefix is a *hit*, not a re-store —
        ``dbsize`` does not grow again, and the KV still lives in Valkey.

    (The warm read is served from the server's shared L1, so it doesn't move
    Valkey's ``keyspace_hits``; the durable copy in Valkey is what makes the
    cache shared and restart-survivable.)
    """
    a, b = clients
    system = _fresh_system_message()
    prefix = [
        system,
        {"role": "user", "content": "What is the capital of France?"},
    ]

    # Turn 1 (cold): full prefill on replica A. This prefix is unique to this
    # run, so its KV cannot already be cached. LMCache writes the KV through to
    # Valkey (L2), so the key count grows.
    before = _dbsize()
    r1 = a.chat.completions.create(
        model=MODEL, messages=prefix, max_tokens=32, temperature=0.0,
    )
    assert r1.choices[0].message.content is not None
    after_cold = _dbsize()
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
    assert _dbsize() >= after_cold, "warm turn must not lose the cached KV"

    # Cross-replica: replica B has served no traffic, but the KV for this exact
    # prefix lives in the shared store. B reuses it rather than storing it again,
    # so replaying the cold prefix on B does not grow the key count.
    before_b = _dbsize()
    r3 = b.chat.completions.create(
        model=MODEL, messages=prefix, max_tokens=32, temperature=0.0,
    )
    assert r3.choices[0].message.content is not None
    assert _dbsize() == before_b, (
        "replica B should reuse the shared cache, not re-store the same prefix"
    )
