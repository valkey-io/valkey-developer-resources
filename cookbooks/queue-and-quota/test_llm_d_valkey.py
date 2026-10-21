"""CI tests for the "Valkey as a job queue and admission gate for llm-d" cookbook.

Two tiers:

1. **Always run, no stack needed.** The async-processor transport config and the
   compose file are well-formed and wire the processor to Valkey the way the
   notebook expects: the transport points at Valkey, the one queue names the
   ``request-sortedset`` sorted set and the ``redis-quota`` admission gate, and
   every published port is bound to localhost. These catch typos in the files a
   reader edits without booting the stack.

2. **Run only when the stack is up** (``docker compose up -d --wait``). These
   read the same state the notebook shows: Valkey is reachable, submitted jobs
   land in the ``request-sortedset`` sorted set, and a job carries its submitted
   metadata. They read Valkey over the network with the Valkey GLIDE client, like
   the notebook, so they work with any container runtime (Docker, Podman,
   nerdctl). They ``skip`` when the stack isn't running so the config/structure
   tier still passes in a bare CI job.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

HERE = Path(__file__).parent
TRANSPORT_PATH = HERE / "transport-config.json"
COMPOSE_PATH = HERE / "docker-compose.yml"

QUEUE_NAME = "request-sortedset"
RESULT_QUEUE = "result-list"
GATE_TYPE = "redis-quota"
# Valkey as published by docker-compose.yml (127.0.0.1:6379); overridable the
# same way a CI workflow would expose its Valkey service.
VALKEY_HOST = os.environ.get("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


def _container_engine() -> str | None:
    """First of docker/podman that is installed and answers `info`.

    Honors $CONTAINER_ENGINE. Mirrors the notebook (and the kv-caching cookbook)
    so the live tests run the same under Docker, Podman, or a compatible runtime.
    Returns None if no runtime is available (live tests then skip).
    """
    forced = os.environ.get("CONTAINER_ENGINE")
    for cand in ([forced] if forced else ["docker", "podman"]):
        if cand and shutil.which(cand):
            try:
                subprocess.run([cand, "info"], check=True, capture_output=True, timeout=20)
                return cand
            except Exception:
                continue
    return None


ENGINE = _container_engine()


# ---------------------------------------------------------------------------
# Tier 1: transport config + compose wiring (no stack required)
# ---------------------------------------------------------------------------
class TestTransportConfig:
    """The async-processor transport config points at Valkey and names the
    queue + quota gate the notebook relies on."""

    @pytest.fixture(scope="class")
    def config(self):
        return json.loads(TRANSPORT_PATH.read_text())

    def test_transport_points_at_valkey(self, config):
        # The processor reaches Valkey by URL alone — the one line that makes
        # "works with Valkey unchanged" true.
        assert config["url"].startswith("redis://valkey:")

    def test_single_batch_queue_on_the_sorted_set(self, config):
        assert len(config["queues"]) == 1
        queue = config["queues"][0]
        assert queue["queue_name"] == QUEUE_NAME
        assert queue["result_queue_name"] == RESULT_QUEUE
        # A pool id must be set or the processor rejects the queue.
        assert queue["worker_pool_id"]

    def test_redis_quota_gate_is_configured(self, config):
        gate = config["queues"][0]
        assert gate["gate_type"] == GATE_TYPE
        params = gate["gate_params"]
        # The gate opens its own client, so it needs Valkey's address.
        assert params["address"].startswith("valkey:")
        # It keys on a request attribute; a positive limit over a window.
        assert params["attribute"]
        assert isinstance(params["limit"], int) and params["limit"] > 0
        assert params["window"]
        assert params["prefix"]


class TestComposeWiring:
    """docker-compose.yml must wire producer -> Valkey <- async-processor -> sim."""

    @pytest.fixture(scope="class")
    def compose(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(COMPOSE_PATH.read_text())

    def test_three_services(self, compose):
        assert set(compose["services"]) == {"valkey", "llm-sim", "async-processor"}

    def test_valkey_pinned_bundle(self, compose):
        image = compose["services"]["valkey"]["image"]
        assert image.startswith("docker.io/valkey/valkey-bundle:")
        assert ":latest" not in image

    def test_images_fully_qualified_and_not_latest(self, compose):
        # Podman resolves short names through registries.conf, which may list no
        # search registry or several; fully-qualified names behave the same
        # everywhere. No image may float on :latest.
        for name, svc in compose["services"].items():
            image = svc["image"]
            assert "/" in image.split(":")[0], name  # registry-qualified
            assert ":latest" not in image, name
            assert ":" in image, name  # an explicit tag, never implicit latest

    def test_ports_bound_to_localhost(self, compose):
        # Nothing in the stack should be exposed beyond the host.
        for name, svc in compose["services"].items():
            for mapping in svc.get("ports", []):
                assert str(mapping).startswith("127.0.0.1:"), (name, mapping)

    def test_processor_points_at_valkey_and_config(self, compose):
        proc = compose["services"]["async-processor"]
        cmd = " ".join(proc["command"])
        assert "--transport=redis-sortedset" in cmd
        assert "--transport-config-file=/etc/ap/transport-config.json" in cmd
        # The transport config is mounted in.
        mounts = " ".join(proc["volumes"])
        assert "transport-config.json" in mounts
        # Waits for a healthy Valkey before starting.
        assert proc["depends_on"]["valkey"]["condition"] == "service_healthy"

    def test_processor_has_kubeconfig_stub(self, compose):
        # Off-cluster the processor still needs a kubeconfig to build its metrics
        # server; the stub is mounted and KUBECONFIG points at it.
        proc = compose["services"]["async-processor"]
        mounts = " ".join(proc["volumes"])
        assert "kubeconfig-dummy.yaml" in mounts
        assert any(e.startswith("KUBECONFIG=") for e in proc["environment"])


# ---------------------------------------------------------------------------
# Tier 2: live stack (skipped unless the stack is up)
# ---------------------------------------------------------------------------
def _connect_valkey():
    from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

    return GlideClient.create(
        GlideClientConfiguration(
            addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
            request_timeout=2000,
        )
    )


def _valkey_running() -> bool:
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


def _compose_network() -> str:
    """The compose-created network name, so the producer container can join it."""
    return f"{HERE.name}_default"


def _stack_up() -> bool:
    """The live tests need the full compose stack, not just a reachable Valkey.

    CI runs the structural tier against a bare Valkey *service container* with no
    compose stack, no producer image, and no compose network — those tests must
    skip there, not fail. So require: a container engine, a reachable Valkey, the
    compose network, and the producer image all present.
    """
    if not (ENGINE and _valkey_running()):
        return False
    # The compose network the producer container joins.
    net = subprocess.run(
        [ENGINE, "network", "inspect", _compose_network()],
        capture_output=True,
    )
    if net.returncode != 0:
        return False
    # The producer image the live tests run.
    img = subprocess.run(
        [ENGINE, "image", "inspect", "llm-d-valkey-producer"],
        capture_output=True,
    )
    return img.returncode == 0


requires_stack = pytest.mark.skipif(
    not _stack_up(),
    reason="full compose stack not up (needs the compose network + producer "
    "image, not just a reachable Valkey); build the producer image and "
    "`docker compose up -d --wait` to run the live tests",
)


def _submit(n: int, userid: str | None = None) -> None:
    """Submit n jobs through the producer image (flags only — a leading
    positional would make Go's flag parser skip the flags)."""
    args = [
        ENGINE, "run", "--rm", "--network", _compose_network(),
        "llm-d-valkey-producer",
        "--redis-url", "redis://valkey:6379",
        "--request-queue", QUEUE_NAME,
        "--n", str(n),
        "--read-results=false",
    ]
    if userid:
        args += ["--userid", userid]
    subprocess.run(args, check=True, capture_output=True, timeout=60)


@pytest.fixture(scope="module")
def valkey():
    pytest.importorskip("glide_sync")
    client = _connect_valkey()
    yield client
    client.close()


def _zcard(valkey, key: str) -> int:
    return int(valkey.custom_command(["ZCARD", key]))


@requires_stack
def test_submitted_jobs_land_in_the_sorted_set(valkey):
    """A submitted job becomes a member of the request-sortedset ZSET."""
    # Pause the processor so submissions accumulate instead of draining.
    subprocess.run(
        [ENGINE, "compose", "pause", "async-processor"],
        cwd=HERE, check=True, capture_output=True,
    )
    try:
        valkey.custom_command(["DEL", QUEUE_NAME])
        _submit(3)
        # Give the one-shot producer a moment to finish writing.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _zcard(valkey, QUEUE_NAME) < 3:
            time.sleep(0.2)
        assert _zcard(valkey, QUEUE_NAME) == 3, "3 submitted jobs should be queued"
        # The member is the request payload as JSON, carrying the enqueue data.
        members = valkey.custom_command(["ZRANGE", QUEUE_NAME, "0", "0"])
        raw = members[0]
        if isinstance(raw, bytes):
            raw = raw.decode()
        job = json.loads(raw)
        assert "data" in job
    finally:
        subprocess.run(
            [ENGINE, "compose", "unpause", "async-processor"],
            cwd=HERE, check=True, capture_output=True,
        )


@requires_stack
def test_job_carries_submitted_userid_metadata(valkey):
    """A job submitted with --userid carries that metadata, so the quota gate
    (which keys on it) can see it. A job with no such metadata is always
    admitted, so setting userid is what makes the gate observable."""
    subprocess.run(
        [ENGINE, "compose", "pause", "async-processor"],
        cwd=HERE, check=True, capture_output=True,
    )
    try:
        valkey.custom_command(["DEL", QUEUE_NAME])
        _submit(1, userid="alice")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _zcard(valkey, QUEUE_NAME) < 1:
            time.sleep(0.2)
        members = valkey.custom_command(["ZRANGE", QUEUE_NAME, "0", "0"])
        raw = members[0]
        if isinstance(raw, bytes):
            raw = raw.decode()
        job = json.loads(raw)
        assert job["data"].get("metadata", {}).get("userid") == "alice"
    finally:
        subprocess.run(
            [ENGINE, "compose", "unpause", "async-processor"],
            cwd=HERE, check=True, capture_output=True,
        )
