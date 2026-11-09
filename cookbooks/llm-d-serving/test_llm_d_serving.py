"""CI tests for the "llm-d serving with Valkey" recipe.

Two tiers:

1. **Always run, no stack needed.** The router configs, the batch processor's
   transport config, the Envoy config and ``docker-compose.yml`` agree with each
   other the way the notebook relies on: the router index points at its own
   Valkey database, vLLM's block size and KV-event ports match the router's,
   each replica's fixed address matches its ``POD_IP`` and the router's endpoint
   file (which the notebook reads instead of hardcoding addresses), batch jobs
   go through Envoy, and the busy-replica example's token
   arithmetic holds. These catch drift in the files a reader edits without
   booting a seven-container stack.

2. **Run only when the stack is up** (``docker compose up -d --wait``). These
   drive the signals the notebook shows: follow-ups routed back to the replica
   that holds the conversation, the router index in Valkey database 1, a
   replica loading another replica's KV from Valkey, a busy replica spilling a
   conversation over to its neighbor, and a batch job submitted from Python in
   llm-d-async's wire format coming back through the router, with excess jobs
   held by the per-user quota until its window expires. They read Valkey
   with the Valkey GLIDE client, like the notebook, and ``skip`` when the stack
   isn't running so the first tier still passes in a bare CI job.
"""

from __future__ import annotations

import contextlib
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).parent
COMPOSE_PATH = HERE / "docker-compose.yml"
PRECISE_PATH = HERE / "epp" / "precise-valkey.yaml"
RANDOM_PATH = HERE / "epp" / "random.yaml"
ENDPOINTS_PATH = HERE / "epp" / "endpoints.yaml"
ENVOY_PATH = HERE / "envoy" / "envoy.yaml"
TRANSPORT_PATH = HERE / "async" / "transport-config.json"
NOTEBOOK_PATH = HERE / "llm-d-serving-with-valkey.ipynb"

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REPLICAS = ("vllm-a", "vllm-b")
ROUTER_URL = "http://127.0.0.1:8080"
REPLICA_URLS = {"vllm-a": "http://127.0.0.1:8001", "vllm-b": "http://127.0.0.1:8002"}
EPP_METRICS = "http://127.0.0.1:9090/metrics"
VALKEY_HOST = os.environ.get("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
# Distroless images: no shell or HTTP client for a container healthcheck.
NO_HEALTHCHECK = {"envoy", "epp", "async-processor"}


def _yaml(path: Path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text())


def _command_text(service: dict) -> str:
    command = service["command"]
    return " ".join(command) if isinstance(command, list) else command


def _plugin(config: dict, plugin_type: str) -> dict:
    return next(p for p in config["plugins"] if p["type"] == plugin_type)


def _flag(text: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}[ =](\S+)", text)
    assert match, f"{name} missing"
    return match.group(1)


# ---------------------------------------------------------------------------
# Tier 1: config + compose wiring (no stack required)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def compose():
    return _yaml(COMPOSE_PATH)


@pytest.fixture(scope="module")
def precise():
    return _yaml(PRECISE_PATH)


@pytest.fixture(scope="module")
def endpoints():
    return _yaml(ENDPOINTS_PATH)["endpoints"]


@pytest.fixture(scope="module")
def transport():
    return json.loads(TRANSPORT_PATH.read_text())


class TestComposeWiring:
    def test_seven_services(self, compose):
        assert set(compose["services"]) == {
            "valkey", "lmcache-server", "vllm-a", "vllm-b", "envoy", "epp", "async-processor",
        }

    def test_images_qualified_and_pinned(self, compose):
        for name, svc in compose["services"].items():
            image = svc["image"]
            assert image.split("/")[0] in ("docker.io", "ghcr.io"), name
            assert ":latest" not in image and ":" in image.split("/")[-1], name
            if name != "valkey":  # valkey-bundle is pinned by version tag, as in kv-caching
                assert "@sha256:" in image, name
        assert compose["services"]["valkey"]["image"].startswith("docker.io/valkey/valkey-bundle:")

    def test_healthchecks_survive_every_runtime(self, compose):
        # Same rule as the KV caching recipe: one CMD-SHELL string, or a CMD
        # whose arguments have no whitespace (Podman splits on whitespace).
        for name, svc in compose["services"].items():
            if name in NO_HEALTHCHECK:
                assert "healthcheck" not in svc, name
                continue
            test = svc["healthcheck"]["test"]
            if test[0] == "CMD-SHELL":
                assert len(test) == 2 and "\n" not in test[1], name
            else:
                assert test[0] == "CMD", name
                assert not any(any(ch.isspace() for ch in arg) for arg in test[1:]), name

    def test_ports_bound_to_localhost(self, compose):
        for name, svc in compose["services"].items():
            for mapping in svc.get("ports", []):
                assert str(mapping).startswith("127.0.0.1:"), (name, mapping)

    def test_bind_mounts_read_only_and_selinux_relabelled(self, compose):
        for name, svc in compose["services"].items():
            for mount in svc.get("volumes", []):
                if mount.startswith("./"):
                    assert mount.endswith(":ro,z"), (name, mount)

    def test_lmcache_installs_are_fully_constrained(self, compose):
        for svc in ("lmcache-server", *REPLICAS):
            service = compose["services"][svc]
            pins = service["environment"]["LMCACHE_PIP_CONSTRAINTS"].split()
            assert all("==" in p for p in pins), svc
            text = _command_text(service)
            assert "-c /tmp/lmcache-constraints.txt" in text, svc
            for word in text.split():
                if word.startswith(("lmcache==", "valkey-glide-sync==")):
                    assert word in pins, (svc, word)

    def test_lmcache_server_uses_valkey(self, compose):
        text = _command_text(compose["services"]["lmcache-server"]).replace(" ", "")
        assert '"type":"valkey"' in text and '"startup_nodes":"valkey:6379"' in text
        assert "--l2-store-policyskip_l1" in text


class TestReplicaAddressing:
    """File discovery needs each replica's literal IPv4, in four places."""

    def test_addresses_agree(self, compose, endpoints):
        subnet = ipaddress.ip_network(compose["networks"]["serving"]["ipam"]["config"][0]["subnet"])
        by_name = {e["name"]: e for e in endpoints}
        assert set(by_name) == set(REPLICAS)
        for name in REPLICAS:
            svc = compose["services"][name]
            address = svc["networks"]["serving"]["ipv4_address"]
            assert ipaddress.ip_address(address) in subnet, name
            assert svc["environment"]["POD_IP"] == address, name
            assert by_name[name]["address"] == address, name
            assert by_name[name]["port"] == "8000", name

    def test_notebook_reads_replica_addresses_from_endpoint_file(self, endpoints):
        # The notebook maps the router's "<ip>:<port>" names to replica names
        # from epp/endpoints.yaml, so a subnet change needs no notebook edit.
        code = "\n".join("".join(c["source"]) for c in json.loads(NOTEBOOK_PATH.read_text())["cells"]
                         if c["cell_type"] == "code")
        assert "epp/endpoints.yaml" in code
        for endpoint in endpoints:
            assert endpoint["address"] not in code, endpoint["name"]

    def test_notebook_memory_preflight_matches_readme(self):
        # The notebook's preflight and the README's startup check use the same
        # minimum (stop) and recommended (warn) memory thresholds.
        code = "\n".join("".join(c["source"]) for c in json.loads(NOTEBOOK_PATH.read_text())["cells"]
                         if c["cell_type"] == "code")
        readme = (HERE / "README.md").read_text()
        for name in ("MIN_RUNTIME_MEMORY", "RECOMMENDED_RUNTIME_MEMORY"):
            cutoff = re.search(rf"\b{name} = ([0-9_]+)", code)
            assert cutoff, f"the setup cell should define {name}"
            assert f'-lt {int(cutoff.group(1).replace("_", ""))} ]' in readme, name

    def test_every_fixed_address_is_unique_and_in_subnet(self, compose):
        subnet = ipaddress.ip_network(compose["networks"]["serving"]["ipam"]["config"][0]["subnet"])
        addresses = [svc["networks"]["serving"]["ipv4_address"]
                     for svc in compose["services"].values() if "networks" in svc]
        assert len(addresses) == len(set(addresses))
        assert all(ipaddress.ip_address(a) in subnet for a in addresses)


class TestRouterMatchesVllm:
    @pytest.mark.parametrize("svc", REPLICAS)
    def test_vllm_flags_the_router_needs(self, compose, precise, svc):
        text = _command_text(compose["services"][svc])
        producer = _plugin(precise, "precise-prefix-cache-producer")["parameters"]
        assert "--enable-prefix-caching" in text
        assert "--no-enable-prefix-caching" not in text
        assert "--enable-prompt-tokens-details" in text
        assert int(_flag(text, "--block-size")) == producer["tokenProcessorConfig"]["blockSizeTokens"]
        discovery = producer["kvEventsConfig"]["podDiscoveryConfig"]
        assert f'"endpoint":"tcp://*:{discovery["socketPort"]}"' in text
        assert f'"replay_endpoint":"tcp://*:{discovery["replaySocketPort"]}"' in text
        # Topic "kv@<POD_IP>:8000@<model>" must start with the router's filter.
        topic = re.search(r'"topic":"([^"]+)"', text).group(1)
        assert topic.startswith(producer["kvEventsConfig"]["topicFilter"])
        assert topic.endswith(f":8000@{MODEL}")
        assert "LMCacheMPConnector" in text and "tcp://lmcache-server" in text

    def test_token_producer_model_matches(self, precise, compose):
        assert _plugin(precise, "token-producer")["parameters"]["modelName"] == MODEL
        assert f"--model {MODEL}" in _command_text(compose["services"]["vllm-a"])


class TestRouterConfig:
    def test_index_in_its_own_valkey_database(self, precise):
        # RedisIndex.Clear SCANs its whole database and HKEYS every non-engine
        # key; LMCache's string keys there would make it fail with WRONGTYPE.
        producer = _plugin(precise, "precise-prefix-cache-producer")["parameters"]
        address = producer["indexerConfig"]["kvBlockIndexConfig"]["redisConfig"]["address"]
        match = re.fullmatch(r"redis://valkey:6379/(\d+)", address)
        assert match and int(match.group(1)) != 0

    def test_cpu_load_settings(self, precise):
        load = _plugin(precise, "inflight-load-producer")["parameters"]
        assert load["addEstimatedOutputTokens"] is True
        affinity = _plugin(precise, "prefix-cache-affinity-filter")["parameters"]
        assert affinity["maxTTFTPenaltyMs"] < 18000
        assert affinity["peakPrefillThroughput"] < 15928

    def test_busy_example_arithmetic(self, precise, compose):
        # The notebook's busy-replica example sends two long requests (1,000
        # output tokens each, plus at most one uncached 64-token block) to the
        # sticky replica. The first must not break stickiness for the second,
        # and two of them must break it for the conversation. Tokens over which
        # the router leaves the sticky replica: penalty_ms * tokens_per_s / 1000.
        affinity = _plugin(precise, "prefix-cache-affinity-filter")["parameters"]
        threshold = affinity["maxTTFTPenaltyMs"] * affinity["peakPrefillThroughput"] / 1000
        one_request = 1000 + 64
        assert one_request < threshold < 2 * 1000
        # Two long requests must fill a replica, so staying would really wait.
        assert int(_flag(_command_text(compose["services"]["vllm-a"]), "--max-num-seqs")) == 2

    def test_scheduling_profile(self, precise):
        refs = [p["pluginRef"] for p in precise["schedulingProfiles"][0]["plugins"]]
        assert refs == ["prefix-cache-affinity-filter", "token-load-scorer"]

    def test_random_baseline(self):
        config = _yaml(RANDOM_PATH)
        assert [p["type"] for p in config["plugins"]] == ["file-discovery", "random-picker"]

    def test_epp_runs_in_envoy_namespace(self, compose):
        epp = compose["services"]["epp"]
        assert epp["network_mode"] == "service:envoy"
        text = _command_text(epp)
        assert "--config-file=/etc/epp/${EPP_STRATEGY:-precise-valkey}.yaml" in text
        for strategy in ("precise-valkey", "random"):
            assert (HERE / "epp" / f"{strategy}.yaml").exists()
        assert "--pool-name=file-discovery" in text


class TestEnvoy:
    def test_attribution_header(self):
        head = ENVOY_PATH.read_text().split("\nadmin:")[0]
        assert "licensed under the Apache License 2.0" in head
        assert "guides/no-kubernetes-deployment/router/envoy/envoy.yaml" in head

    def test_ext_proc_and_listener_match_compose(self, compose):
        envoy = _yaml(ENVOY_PATH)
        listener_port = envoy["static_resources"]["listeners"][0]["address"]["socket_address"]["port_value"]
        assert "127.0.0.1:8080:" + str(listener_port) in compose["services"]["envoy"]["ports"]
        ext_proc = next(c for c in envoy["static_resources"]["clusters"] if c["name"] == "ext_proc")
        sock = ext_proc["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"]
        assert sock["address"] == "127.0.0.1"
        assert f"--grpc-port={sock['port_value']}" in _command_text(compose["services"]["epp"])


class TestBatchProcessor:
    def test_queue_and_quota_in_valkey(self, transport):
        assert transport["url"] == "redis://valkey:6379"
        (queue,) = transport["queues"]
        assert queue["queue_name"] == "request-sortedset"
        assert queue["result_queue_name"] == "result-list"
        assert queue["gate_type"] == "redis-quota"
        params = queue["gate_params"]
        assert params["address"] == "valkey:6379"
        assert params["attribute"] == "userid" and params["mode"] == "rate-limit"
        assert isinstance(params["limit"], int) and params["limit"] > 0

    def test_jobs_go_through_the_router(self, transport):
        envoy = _yaml(ENVOY_PATH)
        listener_port = envoy["static_resources"]["listeners"][0]["address"]["socket_address"]["port_value"]
        assert transport["queues"][0]["igw_base_url"] == f"http://envoy:{listener_port}"

    def test_processor_wiring(self, compose):
        proc = compose["services"]["async-processor"]
        text = _command_text(proc)
        assert "--transport=redis-sortedset" in text
        assert "--transport-config-file=/etc/ap/transport-config.json" in text
        mounts = " ".join(proc["volumes"])
        assert "transport-config.json" in mounts and "kubeconfig-dummy.yaml" in mounts
        assert proc["environment"]["KUBECONFIG"] == "/etc/ap/kubeconfig.yaml"
        assert _flag(text, "--health-port") != "8081"


# ---------------------------------------------------------------------------
# Tier 2: live stack (skipped unless the stack is up)
# ---------------------------------------------------------------------------
def _connect_valkey(database_id=0):
    from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

    return GlideClient.create(GlideClientConfiguration(
        addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)], database_id=database_id,
        request_timeout=5000))


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _affinity_metric_present() -> bool:
    try:
        with urllib.request.urlopen(EPP_METRICS, timeout=5) as resp:
            return b"llm_d_epp_prefix_cache_affinity_filter" in resp.read()
    except Exception:
        return False


def _stack_up() -> bool:
    try:
        socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=2).close()
    except OSError:
        return False
    if not all(_http_ok(f"{u}/health") for u in REPLICA_URLS.values()):
        return False
    # The affinity filter's metric exists only with epp/precise-valkey.yaml, and
    # only after the filter has made a decision: on a fresh stack, send one
    # one-token request through the router first (as the notebook's
    # wait_for_router() does), retrying while the EPP starts.
    if _affinity_metric_present():
        return True
    body = json.dumps({"model": MODEL, "prompt": "ping", "max_tokens": 1}).encode()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{ROUTER_URL}/v1/completions", body, {"Content-Type": "application/json"}),
                timeout=10).read()
            break
        except Exception:
            time.sleep(1)
    else:
        return False
    return _affinity_metric_present()


requires_stack = pytest.mark.skipif(
    not _stack_up(),
    reason="full stack (with the precise-valkey router) not running; "
           "`docker compose up -d --wait` to run live tests",
)


def _scrape(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode()


def _metric(text: str, name: str, **labels) -> float:
    total = 0.0
    for match in re.finditer(rf"^{re.escape(name)}(?:\{{([^}}]*)\}})? (\S+)$", text, re.M):
        found = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1) or ""))
        if all(found.get(k) == v for k, v in labels.items()):
            total += float(match.group(2))
    return total


def _counters() -> dict:
    out = {}
    for name, url in REPLICA_URLS.items():
        text = _scrape(f"{url}/metrics")
        out[name] = {"served": _metric(text, "vllm:request_success_total"),
                     "local": _metric(text, "vllm:prefix_cache_hits_total"),
                     "valkey": _metric(text, "vllm:external_prefix_cache_hits_total")}
    return out


def _chat(base_url: str, messages: list, max_tokens: int = 8) -> dict:
    """Non-streaming chat request; returns the replica that served it and its hits."""
    before = _counters()
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
    req = urllib.request.Request(f"{base_url}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.load(resp)
    answer = body["choices"][0]["message"]["content"]
    after = _counters_until(lambda c: any(c[n]["served"] > before[n]["served"] for n in c))
    moved = [n for n in after if after[n]["served"] > before[n]["served"]]
    assert len(moved) == 1, f"could not tell which replica served the request: {moved}"
    name = moved[0]
    return {"replica": name, "answer": answer, "prompt": body["usage"]["prompt_tokens"],
            "local": after[name]["local"] - before[name]["local"],
            "valkey": after[name]["valkey"] - before[name]["valkey"]}


def _counters_until(predicate, timeout_s: float = 3.0) -> dict:
    """Replica counters once ``predicate(counters)`` holds, or after ``timeout_s``.

    vLLM's Prometheus counters can lag behind the response that bumped them.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        counters = _counters()
        if predicate(counters) or time.monotonic() > deadline:
            return counters
        time.sleep(0.05)


def _wait_until_replicas_idle(timeout_s: float = 120.0) -> None:
    """Wait until no replica is running a request (e.g. long generations an
    earlier test aborted, which vLLM may still be finishing)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        running = {n: _metric(_scrape(f"{u}/metrics"), "vllm:num_requests_running")
                   for n, u in REPLICA_URLS.items()}
        if not any(running.values()):
            return
        time.sleep(0.5)
    pytest.fail(f"replicas still running requests after {timeout_s:.0f} s: {running}")


def _close_connections(connections: list) -> None:
    """Close every connection, even if one fails. Closing the socket makes vLLM
    abort a request it is still generating."""
    for conn in connections:
        if conn.sock is not None:
            with contextlib.suppress(OSError):
                conn.sock.shutdown(socket.SHUT_RDWR)
        conn.close()


def _remove_batch_jobs(valkey, job_ids, queue_name="request-sortedset", result_name="result-list",
                       extra_keys=()) -> None:
    """Remove these jobs' queue entries, results and state, keeping everyone else's."""
    for raw in valkey.custom_command(["ZRANGE", queue_name, "0", "-1"]) or []:
        if json.loads(raw)["data"]["id"] in job_ids:
            valkey.custom_command(["ZREM", queue_name, raw])
    for raw in valkey.custom_command(["LRANGE", result_name, "0", "-1"]) or []:
        if json.loads(raw)["id"] in job_ids:
            valkey.custom_command(["LREM", result_name, "1", raw])
    valkey.delete([*extra_keys, *[f"request-active:{job_id}" for job_id in job_ids]])


def _document(tag: str, clauses: int = 29) -> str:
    return f"[document {tag}] " + " ".join(
        f"Clause {i}: the tenant of unit {tag} shall keep fixture {i * 7 % 13} in good "
        f"repair and report any fault within {i % 5 + 1} days." for i in range(clauses))


def _conversation() -> list:
    # Random hex tokenizes into a variable number of tokens, and the tag appears
    # in every clause, so the prompt length varies by ~180 tokens. With 36
    # clauses it measured 1,105-1,290 tokens over 500 tags (17-20 full 64-token
    # blocks); with 29 it was 923-1,043, often only 14 or 15 blocks.
    return [{"role": "system", "content": _document(uuid.uuid4().hex[:8], clauses=36)},
            {"role": "user", "content": "Summarise clause 3."}]


def _scan(client, match: str | None = None) -> list[str]:
    """Every key in the client's database, following the SCAN cursor to the end."""
    cursor, keys = b"0", []
    while True:
        cursor, batch = client.scan(cursor, match=match, count=1000)
        keys += [k.decode() for k in batch]
        if cursor in (b"0", "0"):
            return keys


def _settled_dbsize(client, quiet_s: float = 1.0, timeout_s: float = 15.0) -> int:
    """``DBSIZE`` once it has stopped changing for ``quiet_s`` seconds.

    The LMCache server writes KV through to Valkey asynchronously
    (``--l2-store-policy skip_l1``), so a replica that asks for a prefix right
    after another replica computed it can find chunks that are not stored yet.
    Same approach as the KV caching recipe's tests.
    """
    deadline = time.monotonic() + timeout_s
    last, since = int(client.custom_command(["DBSIZE"])), time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        current = int(client.custom_command(["DBSIZE"]))
        if current != last:
            last, since = current, time.monotonic()
        elif time.monotonic() - since >= quiet_s:
            break
    return last


@pytest.fixture(scope="module")
def valkey():
    pytest.importorskip("glide_sync")
    client = _connect_valkey(0)
    yield client
    client.close()


@pytest.fixture(scope="module")
def router_index():
    pytest.importorskip("glide_sync")
    client = _connect_valkey(1)
    yield client
    client.close()


@requires_stack
def test_follow_up_routed_to_the_replica_with_the_conversation():
    messages = _conversation()
    first = _chat(ROUTER_URL, messages)
    messages += [{"role": "assistant", "content": first["answer"]},
                 {"role": "user", "content": "And clause 9?"}]
    second = _chat(ROUTER_URL, messages)
    assert second["replica"] == first["replica"]
    # Turn 1's prompt is a prefix of turn 2's, so every full 64-token block of
    # it should be found in the replica's own memory, and none in Valkey.
    full_blocks = 64 * (first["prompt"] // 64)
    assert full_blocks >= 1024, f"conversation too short to be meaningful: {first['prompt']} tokens"
    assert second["local"] >= full_blocks, "follow-up should be a local prefix-cache hit"
    assert second["valkey"] == 0


@requires_stack
def test_router_index_lives_in_valkey_database_1(valkey, router_index):
    _chat(ROUTER_URL, _conversation())
    # The router writes its index from vLLM's KV events, after the response.
    deadline = time.monotonic() + 10
    while True:
        keys = _scan(router_index)
        blocks = [k for k in keys if k.isdigit()]
        if (blocks and any(k.startswith("engine:") for k in keys)) or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    assert any(k.startswith("engine:") for k in keys), "no engine:<hash> key in database 1 after 10 s"
    assert blocks, "no block hash in database 1 after 10 s"
    entry = json.loads(router_index.hkeys(blocks[0])[0])
    assert entry["PodIdentifier"].endswith(":8000")
    # Nothing of the router's lands in database 0 (walk every SCAN page: one
    # page can be empty while later ones still match).
    assert not _scan(valkey, match="engine:*")


@requires_stack
def test_neighbor_loads_kv_from_valkey(valkey):
    messages = _conversation()
    cold = _chat(REPLICA_URLS["vllm-a"], messages, max_tokens=1)
    assert cold["local"] == 0 and cold["valkey"] == 0
    _settled_dbsize(valkey)  # wait for A's KV to be written through to Valkey
    neighbor = _chat(REPLICA_URLS["vllm-b"], messages, max_tokens=1)
    assert neighbor["valkey"] >= 256, "replica B should load replica A's KV from Valkey"


@requires_stack
def test_busy_replica_spills_over_to_its_neighbor(valkey):
    tag = uuid.uuid4().hex[:8]
    template = f"[report template {tag}] " + _document(f"template-{tag}", clauses=26)
    # Warm the template on replica A as the same raw completion prompt prefix.
    warm = {"model": MODEL, "prompt": template, "max_tokens": 1}
    urllib.request.urlopen(urllib.request.Request(
        f"{REPLICA_URLS['vllm-a']}/v1/completions", json.dumps(warm).encode(),
        {"Content-Type": "application/json"}), timeout=120).read()
    messages = _conversation()
    turn1 = _chat(REPLICA_URLS["vllm-a"], messages)
    messages += [{"role": "assistant", "content": turn1["answer"]},
                 {"role": "user", "content": "And clause 9?"}]
    _settled_dbsize(valkey)  # the conversation's KV is in Valkey before B needs it
    connections = []
    try:
        for job in range(2):
            conn = http.client.HTTPConnection("127.0.0.1", 8080, timeout=600)
            connections.append(conn)  # tracked first, so a failed send is closed too
            body = {"model": MODEL, "prompt": f"{template}\nReport {job}:", "max_tokens": 1000,
                    "ignore_eos": True, "temperature": 0}
            conn.request("POST", "/v1/completions", json.dumps(body), {"Content-Type": "application/json"})
            time.sleep(0.3)
        time.sleep(0.5)
        spilled = _chat(ROUTER_URL, messages)
    finally:
        _close_connections(connections)
    assert spilled["replica"] == "vllm-b"
    assert spilled["valkey"] >= 256, "the neighbor should load the conversation from Valkey"


# submitRequestScript from llm-d-async v1.0.0 producer/redis_sortedset_producer.go
SUBMIT_REQUEST = """
local seq = redis.call("INCR", KEYS[1])
redis.call("EXPIREAT", KEYS[1], ARGV[3])
redis.call("DEL", KEYS[2])
redis.call("SET", KEYS[3], ARGV[1], "PX", ARGV[2])
local score = tonumber(ARGV[6]) + math.min(seq, 2097151) / 2097152
redis.call("ZADD", KEYS[4], string.format("%.17g", score), ARGV[4] .. seq .. ARGV[5])
if KEYS[5] then
  redis.call("SET", KEYS[5], ARGV[7], "PX", ARGV[8])
end
return seq
"""


def _submit_batch_job(valkey, job_id: str, userid: str | None = None):
    """Submit a short job, optionally subject to the configured per-user gate."""
    from glide_sync import Script

    created = int(time.time())
    deadline = created + 120
    token = secrets.token_hex(16)
    data = {
        "id": job_id, "created": created, "deadline": deadline,
        "payload": {"model": MODEL, "prompt": "Say hello.", "max_tokens": 4},
        "endpoint": "/v1/completions", "model": MODEL,
    }
    if userid is not None:
        data["metadata"] = {"userid": userid}
    envelope = json.dumps({
        "internal": {"request_token": token, "request_queue_name": "request-sortedset",
                     "result_queue_name": "result-list", "enqueue_seq": -1},
        "request_kind": "plain",
        "data": data,
    }, separators=(",", ":"))
    head, tail = envelope.split('"enqueue_seq":-1', 1)
    valkey.invoke_script(
        Script(SUBMIT_REQUEST),
        keys=[f"request-seq:request-sortedset:{deadline}", f"request-cancel:{job_id}",
              f"request-active:{job_id}", "request-sortedset"],
        args=[token, str((deadline - created) * 1000), str(deadline + 3600),
              head + '"enqueue_seq":', tail, str(deadline)])


@requires_stack
def test_batch_job_from_python_runs_through_the_router(valkey):
    job_id = f"test-{uuid.uuid4().hex}"
    before = _counters()
    try:
        _submit_batch_job(valkey, job_id)
        result = None
        stop = time.monotonic() + 60
        while result is None and time.monotonic() < stop:
            for raw in valkey.custom_command(["LRANGE", "result-list", "0", "-1"]) or []:
                parsed = json.loads(raw)
                if parsed["id"] == job_id:
                    result = parsed
                    valkey.custom_command(["LREM", "result-list", "1", raw])
            time.sleep(0.5)
        assert result is not None, "the batch processor did not return a result"
        assert result["status_code"] == 200
        assert json.loads(result["payload"])["choices"]
        after = _counters_until(lambda c: sum(c[n]["served"] - before[n]["served"] for n in c) >= 1)
        assert sum(after[n]["served"] - before[n]["served"] for n in after) >= 1
        assert not valkey.exists([f"request-active:{job_id}"]), "processor cleans up the job state"
    finally:
        # On a timeout the job may still be queued, or its result may arrive later.
        _remove_batch_jobs(valkey, {job_id})


@requires_stack
def test_per_user_quota_holds_excess_batch_jobs_until_the_window_expires(valkey, transport):
    queue = transport["queues"][0]
    gate = queue["gate_params"]
    limit = gate["limit"]
    window = re.fullmatch(r"(\d+)s", gate["window"])
    assert window, "this test expects a quota window expressed in seconds"
    window_s = int(window.group(1))
    user = f"test-quota-{uuid.uuid4().hex}"
    quota_key = f"{gate['prefix']}{gate['attribute']}:{user}"
    job_ids = {f"{user}-{i}" for i in range(limit + 1)}

    def results():
        return {result["id"]: result
                for raw in valkey.custom_command(["LRANGE", queue["result_queue_name"], "0", "-1"]) or []
                if (result := json.loads(raw))["id"] in job_ids}

    def queued_jobs():
        return {job_id
                for raw in valkey.custom_command(["ZRANGE", queue["queue_name"], "0", "-1"]) or []
                if (job_id := json.loads(raw)["data"]["id"]) in job_ids}

    # Long generations an earlier test aborted may still be running, and would
    # slow these jobs down enough to eat into the quota window.
    _wait_until_replicas_idle()
    try:
        for job_id in sorted(job_ids):
            _submit_batch_job(valkey, job_id, userid=user)

        # The window starts at the first admission, which is when the gate
        # adds the first member to the quota sorted set.
        stop = time.monotonic() + 60
        while not valkey.zcard(quota_key):
            if time.monotonic() > stop:
                pytest.fail("the gate admitted no job within 60 s")
            time.sleep(0.05)
        started = time.monotonic()

        # Observe only this user's jobs, before any admission can age out.
        # Refused jobs are briefly dequeued on each poll, so retry snapshots
        # until the excess job is back in the sorted set.
        stop = started + window_s - 2
        held_since = None
        while time.monotonic() < stop:
            admitted = results()
            assert len(admitted) <= limit, "the quota admitted too many jobs in one window"
            if (len(admitted) == limit
                    and queued_jobs() == job_ids - admitted.keys()
                    and valkey.zcard(quota_key) == limit):
                held_since = held_since or time.monotonic()
                # Wait through at least two processor polls to catch a gate
                # that records admissions but does not actually hold jobs.
                if time.monotonic() - held_since >= 1:
                    break
            time.sleep(0.1)
        else:
            pytest.fail("did not observe the admitted jobs and excess queued job before quota expiry")

        assert all(result["status_code"] == 200 for result in admitted.values())
        assert valkey.exists([quota_key]), "the per-user quota should live in database 0"
        assert valkey.custom_command(["TYPE", quota_key]) == b"zset"
        assert valkey.ttl(quota_key) > 0

        # The held job must eventually run when the sliding window frees a
        # slot; a job permanently stuck in the queue is not a passing gate.
        stop = started + 2 * window_s + 10
        while time.monotonic() < stop:
            completed = results()
            # 1 s of slack: `started` is when polling saw the first admission.
            if time.monotonic() - started < window_s - 1:
                assert len(completed) <= limit, "the held job ran before the quota window expired"
            if completed.keys() == job_ids:
                break
            time.sleep(0.2)
        else:
            pytest.fail("the held batch job did not finish after the quota window expired")
        assert all(result["status_code"] == 200 for result in completed.values())
        assert all(json.loads(result["payload"])["choices"] for result in completed.values())
        assert not queued_jobs()
        assert not valkey.exists([f"request-active:{job_id}" for job_id in job_ids])
    finally:
        # Preserve other users' queued jobs and results, including on failure.
        _remove_batch_jobs(valkey, job_ids, queue["queue_name"], queue["result_queue_name"],
                           extra_keys=[quota_key])
