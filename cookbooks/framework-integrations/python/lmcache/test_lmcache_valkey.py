"""CI tests for the "KV Caching with Valkey" cookbook.

Two tiers:

1. **Always run, no stack needed.** The reader-facing config actually loads
   through LMCache's own parser, and ``docker-compose.yml`` wires the two vLLM
   replicas to Valkey the way the notebook expects. These catch typos in the
   files a reader edits without booting a 3-container stack.

2. **Run only when the stack is up** (``docker compose up -d --wait``). These
   drive the same signals the notebook shows: Valkey is reachable, both replicas
   serve the model, a cold request grows ``dbsize``, and a warm request with a
   shared prefix increments ``keyspace_hits``. They ``skip`` when the stack
   isn't running so the config/structure tier still passes in a bare CI job.
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "lmcache_config.yaml"
COMPOSE_PATH = HERE / "docker-compose.yml"

MODEL = "facebook/opt-125m"
VALKEY_URL = "valkey://valkey:6379"
REPLICA_A = "http://localhost:8001"
REPLICA_B = "http://localhost:8002"


# ---------------------------------------------------------------------------
# Tier 1: config + compose wiring (no stack required)
# ---------------------------------------------------------------------------
class TestConfigLoading:
    def test_config_loads_through_lmcache_parser(self):
        """The one config line points LMCache at Valkey, via LMCache's parser."""
        from lmcache.v1.config import load_engine_config_with_overrides

        config = load_engine_config_with_overrides(config_file_path=str(CONFIG_PATH))
        assert config.remote_url == VALKEY_URL
        # cachegen needs a GPU encoder; the CPU walkthrough must stay on naive.
        assert config.remote_serde == "naive"

    def test_malformed_config_rejected(self, tmp_path):
        """A broken config fails in the parser, not on a GPU host later."""
        from lmcache.v1.config import load_engine_config_with_overrides

        bad = tmp_path / "bad.yaml"
        bad.write_text("chunk_size: [unclosed\n")
        with pytest.raises(Exception):
            load_engine_config_with_overrides(config_file_path=str(bad))


class TestComposeWiring:
    """docker-compose.yml must wire both replicas to Valkey consistently."""

    @pytest.fixture(scope="class")
    def compose(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(COMPOSE_PATH.read_text())

    def test_three_services(self, compose):
        assert set(compose["services"]) == {"valkey", "vllm-a", "vllm-b"}

    def test_valkey_pinned_bundle(self, compose):
        image = compose["services"]["valkey"]["image"]
        assert image.startswith("valkey/valkey-bundle:")
        assert ":latest" not in image

    @pytest.mark.parametrize("svc", ["vllm-a", "vllm-b"])
    def test_replica_wired_to_valkey_via_lmcache(self, compose, svc):
        service = compose["services"][svc]
        # Official vLLM CPU image, pinned.
        assert service["image"] == "vllm/vllm-openai-cpu:v0.28.0"
        # The command may be a scalar or a YAML list (list form runs a startup
        # shell that pip-installs LMCache before launching vLLM). Join either
        # shape into one string before asserting on its contents.
        command = service["command"]
        command_text = " ".join(command) if isinstance(command, list) else command
        # LMCache is not bundled in the CPU image, so it is installed on startup.
        assert "pip install" in command_text and "lmcache" in command_text
        # KV connector that drives LMCache.
        assert "LMCacheConnectorV1" in command_text
        # LMCache picks up the mounted config, and the experimental flag that
        # enables the remote backend is set as an env var (required).
        env = service["environment"]
        assert env["LMCACHE_CONFIG_FILE"] == "/etc/lmcache/lmcache_config.yaml"
        assert str(env["LMCACHE_USE_EXPERIMENTAL"]).lower() == "true"
        # vLLM's multiprocess executor needs more than the default 64 MiB shm.
        assert service["shm_size"]
        # Wait for a healthy Valkey before starting.
        assert service["depends_on"]["valkey"]["condition"] == "service_healthy"

    def test_both_replicas_mount_the_same_config(self, compose):
        mounts = {
            svc: compose["services"][svc]["volumes"][0]
            for svc in ("vllm-a", "vllm-b")
        }
        assert mounts["vllm-a"] == mounts["vllm-b"]
        assert "lmcache_config.yaml" in mounts["vllm-a"]


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


def _keyspace_hits() -> int:
    for line in _valkey_cli("INFO", "stats").splitlines():
        if line.startswith("keyspace_hits:"):
            return int(line.split(":", 1)[1])
    return 0


@pytest.fixture(scope="module")
def clients():
    openai = pytest.importorskip("openai")
    a = openai.OpenAI(base_url=f"{REPLICA_A}/v1", api_key="not-needed")
    b = openai.OpenAI(base_url=f"{REPLICA_B}/v1", api_key="not-needed")
    return a, b


@requires_stack
def test_both_replicas_serve_the_model(clients):
    a, b = clients
    assert MODEL in [m.id for m in a.models.list().data]
    assert MODEL in [m.id for m in b.models.list().data]


@requires_stack
def test_cold_then_warm_then_cross_replica(clients):
    """The three signals the notebook shows, in one flow."""
    a, b = clients
    system = {"role": "system", "content": "You are a concise geography assistant."}
    messages = [system]

    # Turn 1 (cold): full prefill, KV blocks land in Valkey -> dbsize grows.
    before = _dbsize()
    messages.append({"role": "user", "content": "What is the capital of France?"})
    r1 = a.chat.completions.create(
        model=MODEL, messages=messages, max_tokens=32, temperature=0.0,
    )
    messages.append({"role": "assistant", "content": r1.choices[0].message.content})
    assert _dbsize() > before, "cold turn should store KV blocks in Valkey"

    # Turn 2 (warm, shared prefix): reading cached prefix increments hits.
    hits_before = _keyspace_hits()
    messages.append({"role": "user", "content": "What about Italy?"})
    a.chat.completions.create(
        model=MODEL, messages=messages, max_tokens=32, temperature=0.0,
    )
    assert _keyspace_hits() > hits_before, "warm turn should hit the cached prefix"

    # Replica B hits the prefix replica A computed -> shared cache proof.
    hits_before = _keyspace_hits()
    r3 = b.chat.completions.create(
        model=MODEL, messages=messages[:-1], max_tokens=32, temperature=0.0,
    )
    assert r3.choices[0].message.content is not None
    assert _keyspace_hits() > hits_before, "replica B should reuse A's cached prefix"
