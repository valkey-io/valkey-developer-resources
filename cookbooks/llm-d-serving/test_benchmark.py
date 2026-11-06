"""Structural tests for the optional GPU benchmark (``benchmark/``).

These need no GPU, no Docker and no running stack, so they run in CI next to
``test_llm_d_serving.py``. They check that the files a reader edits agree
with each other the way ``scripts/run-benchmark.sh`` relies on: four GPU
replicas, the LMCache server and Valkey wired as in the CPU stack, the router
index in its own Valkey database, one router config per configuration, the
no-LMCache baseline really running without a KV connector, Valkey sized for
the default workload, and the summary's median/spread arithmetic and run
metadata.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
BENCH = HERE / "benchmark"
SCRIPTS = BENCH / "scripts"
COMPOSE_PATH = BENCH / "compose.yaml"
DOCKERFILE = BENCH / "vllm" / "Dockerfile"
SERVE_VLLM = BENCH / "vllm" / "serve-vllm.sh"
RUN_BENCHMARK = SCRIPTS / "run-benchmark.sh"
REPLICAS = ("vllm-0", "vllm-1", "vllm-2", "vllm-3")

sys.path.insert(0, str(SCRIPTS))
import benchctl  # noqa: E402
import metadata  # noqa: E402
import render  # noqa: E402
import summarize  # noqa: E402


def _yaml(path: Path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text())


def _plugin(config: dict, plugin_type: str) -> dict:
    return next(p for p in config["plugins"] if p["type"] == plugin_type)


def _command_text(service: dict) -> str:
    command = service.get("command") or ""
    return " ".join(command) if isinstance(command, list) else command


def _script_defaults() -> dict[str, str]:
    """NAME -> default from run-benchmark.sh's `export NAME="${NAME:-default}"`."""
    text = RUN_BENCHMARK.read_text()
    return dict(re.findall(r'^export (\w+)="\$\{\1:-([^}]*)\}"', text, re.M))


@pytest.fixture(scope="module")
def compose():
    return _yaml(COMPOSE_PATH)


@pytest.fixture(scope="module")
def cpu_compose():
    return _yaml(HERE / "docker-compose.yml")


@pytest.fixture(scope="module")
def precise_valkey():
    return _yaml(BENCH / "epp" / "precise-valkey.yaml")


@pytest.fixture(scope="module")
def precise_memory():
    return _yaml(BENCH / "epp" / "precise-memory.yaml")


def _devices(service: dict) -> list[dict]:
    return service["deploy"]["resources"]["reservations"]["devices"]


# ---------------------------------------------------------------------------
# Compose wiring
# ---------------------------------------------------------------------------
class TestBenchmarkCompose:
    def test_services(self, compose):
        assert set(compose["services"]) == {
            "model-download", "valkey", "lmcache-server", *REPLICAS, "envoy", "epp", "loadgen",
        }

    @pytest.mark.parametrize("index,name", enumerate(REPLICAS))
    def test_one_gpu_per_replica_and_host_ipc(self, compose, index, name):
        svc = compose["services"][name]
        (device,) = _devices(svc)
        assert device["driver"] == "nvidia" and device["capabilities"] == ["gpu"]
        assert device["device_ids"] == [str(index)]
        # lmcache_driven transfers use CUDA IPC between the replica and the
        # LMCache server, which needs a shared IPC namespace.
        assert svc["ipc"] == "host"
        assert "shm_size" not in svc

    def test_lmcache_server_sees_every_gpu_and_shares_ipc(self, compose):
        svc = compose["services"]["lmcache-server"]
        (device,) = _devices(svc)
        assert device["device_ids"] == [str(i) for i in range(len(REPLICAS))]
        assert svc["ipc"] == "host"

    def test_replicas_and_server_share_the_pinned_image(self, compose):
        dockerfile = DOCKERFILE.read_text()
        base = re.search(r"^ARG VLLM_BASE_IMAGE=(\S+)$", dockerfile, re.M).group(1)
        assert re.fullmatch(r"docker\.io/vllm/vllm-openai:v0\.30\.0@sha256:[0-9a-f]{64}", base)
        assert "FROM ${VLLM_BASE_IMAGE}" in dockerfile
        assert re.search(r"^ARG LMCACHE_VERSION=0\.5\.5$", dockerfile, re.M)
        assert re.search(r"^ARG VALKEY_GLIDE_SYNC_VERSION=2\.5\.2$", dockerfile, re.M)
        built = {compose["services"][s]["image"] for s in ("lmcache-server", *REPLICAS)}
        assert len(built) == 1
        for name in ("lmcache-server", *REPLICAS):
            assert compose["services"][name]["build"]["dockerfile"] == "vllm/Dockerfile", name
        # The model download uses the base image the build starts from.
        assert compose["services"]["model-download"]["image"] == base

    def test_images_qualified_and_pinned(self, compose, cpu_compose):
        for name, svc in compose["services"].items():
            if "build" in svc:
                continue
            image = svc["image"]
            assert image.split("/")[0] in ("docker.io", "ghcr.io", "quay.io"), name
            if name != "valkey":
                assert re.search(r":[^/@]+@sha256:[0-9a-f]{64}$", image), name
        # Router images and the Valkey version are the CPU stack's.
        for name in ("valkey", "envoy", "epp"):
            assert compose["services"][name]["image"] == cpu_compose["services"][name]["image"], name

    def test_valkey_memory_limit_and_policy(self, compose):
        command = compose["services"]["valkey"]["command"]
        assert command[0] == "valkey-server"
        args = dict(zip(command[1::2], command[2::2]))
        assert args["--save"] == "" and args["--appendonly"] == "no"
        assert args["--maxmemory-policy"] == "noeviction"
        default = re.fullmatch(r"\$\{VALKEY_MAXMEMORY:-(\w+)\}", args["--maxmemory"]).group(1)
        assert default == _script_defaults()["VALKEY_MAXMEMORY"]

    def test_lmcache_server_uses_valkey(self, compose):
        svc = compose["services"]["lmcache-server"]
        text = _command_text(svc).replace(" ", "")
        assert '--l2-adapter\'{"type":"valkey","startup_nodes":"valkey:6379"}\'' in text
        assert "--supported-transfer-mode\"$$LMCACHE_SERVER_TRANSFER_MODE\"" in text
        assert "importlmcache.v1.multiprocess.server" in text and "glide_sync" in text
        env = svc["environment"]
        defaults = _script_defaults()
        for name, value in (("LMCACHE_L2_STORE_POLICY", "skip_l1"), ("LMCACHE_SERVER_TRANSFER_MODE", "auto"),
                            ("LMCACHE_L1_SIZE_GB", defaults["LMCACHE_L1_SIZE_GB"]),
                            ("LMCACHE_EVICTION_POLICY", defaults["LMCACHE_EVICTION_POLICY"])):
            assert env[name] == f"${{{name}:-{value}}}", name
            assert defaults[name] == value, name

    def test_chunk_size_is_whole_router_blocks(self, compose, precise_valkey):
        chunk = int(re.search(r"--chunk-size (\d+)", _command_text(compose["services"]["lmcache-server"])).group(1))
        block = int(re.search(r"--block-size (\d+)", SERVE_VLLM.read_text()).group(1))
        router = _plugin(precise_valkey, "precise-prefix-cache-producer")["parameters"]
        assert block == router["tokenProcessorConfig"]["blockSizeTokens"] == 64
        assert chunk == 256 and chunk % block == 0
        # The default system prompt is a whole number of LMCache chunks.
        assert int(_script_defaults()["SYSTEM_PROMPT_LEN"]) % chunk == 0

    @pytest.mark.parametrize("name", REPLICAS)
    def test_replica_environment(self, compose, name):
        env = compose["services"][name]["environment"]
        assert env["KV_CONNECTOR"] == "${KV_CONNECTOR:-lmcache}"
        assert env["LMCACHE_MP_TRANSFER_MODE"] == "${LMCACHE_MP_TRANSFER_MODE:-auto}"
        assert compose["services"][name]["depends_on"]["lmcache-server"]["condition"] == "service_healthy"

    def test_healthchecks_survive_every_runtime(self, compose):
        for name, svc in compose["services"].items():
            if "healthcheck" not in svc:
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

    def test_bind_mounts_relabelled(self, compose):
        for name, svc in compose["services"].items():
            for mount in svc.get("volumes", []):
                if mount.startswith("./"):
                    # Results are written by the load generator; everything
                    # else is mounted read-only.
                    suffix = ":z" if mount.startswith("./results:") else ":ro,z"
                    assert mount.endswith(suffix), (name, mount)


class TestBenchmarkAddressing:
    def test_addresses_agree(self, compose):
        subnet = ipaddress.ip_network(compose["networks"]["bench"]["ipam"]["config"][0]["subnet"])
        endpoints = {e["name"]: e for e in _yaml(BENCH / "epp" / "endpoints.yaml")["endpoints"]}
        assert set(endpoints) == set(REPLICAS) == set(benchctl.REPLICA_URLS)
        for name in REPLICAS:
            svc = compose["services"][name]
            address = svc["networks"]["bench"]["ipv4_address"]
            assert ipaddress.ip_address(address) in subnet, name
            assert svc["environment"]["POD_IP"] == address, name
            assert endpoints[name]["address"] == address, name
            assert benchctl.REPLICA_URLS[name] == f"http://{address}:8000", name
        envoy = compose["services"]["envoy"]["networks"]["bench"]["ipv4_address"]
        assert benchctl.ROUTER_URL == f"http://{envoy}:8081"
        assert f"base_url: http://{envoy}:8081" in (BENCH / "loadgen" / "shared-prefix.yaml").read_text()

    def test_subnet_differs_from_cpu_stack(self, compose, cpu_compose):
        gpu = ipaddress.ip_network(compose["networks"]["bench"]["ipam"]["config"][0]["subnet"])
        cpu = ipaddress.ip_network(cpu_compose["networks"]["serving"]["ipam"]["config"][0]["subnet"])
        assert not gpu.overlaps(cpu)

    def test_fixed_addresses_unique(self, compose):
        addresses = [svc["networks"]["bench"]["ipv4_address"] for svc in compose["services"].values()
                     if isinstance(svc.get("networks"), dict)]
        assert len(addresses) == len(set(addresses))


# ---------------------------------------------------------------------------
# Router configs
# ---------------------------------------------------------------------------
class TestBenchmarkRouter:
    def test_index_in_valkey_database_1(self, precise_valkey):
        producer = _plugin(precise_valkey, "precise-prefix-cache-producer")["parameters"]
        assert producer["indexerConfig"]["kvBlockIndexConfig"]["redisConfig"]["address"] == "redis://valkey:6379/1"

    def test_precise_configs_differ_only_in_index_backend(self, precise_valkey, precise_memory):
        stripped = json.loads(json.dumps(precise_valkey))
        index = _plugin(stripped, "precise-prefix-cache-producer")["parameters"]["indexerConfig"]["kvBlockIndexConfig"]
        del index["redisConfig"]
        assert stripped == precise_memory

    @pytest.mark.parametrize("name", ["precise-valkey", "precise-memory"])
    def test_gpu_calibration_not_cpu_overrides(self, name):
        config = _yaml(BENCH / "epp" / f"{name}.yaml")
        load = _plugin(config, "inflight-load-producer")["parameters"]
        assert "addEstimatedOutputTokens" not in load
        affinity = _plugin(config, "prefix-cache-affinity-filter")["parameters"]
        assert affinity["peakPrefillThroughput"] == "${PEAK_PREFILL_THROUGHPUT}"
        assert "maxTTFTPenaltyMs" not in affinity
        assert _plugin(config, "token-producer")["parameters"]["modelName"] == "${MODEL}"

    def test_epp_reads_rendered_configs(self, compose):
        epp = compose["services"]["epp"]
        assert epp["network_mode"] == "service:envoy"
        assert "./rendered/epp:/etc/epp:ro,z" in epp["volumes"]
        assert "--config-file=/etc/epp/${EPP_STRATEGY:-precise-valkey}.yaml" in epp["command"]


# ---------------------------------------------------------------------------
# Configurations and rendering
# ---------------------------------------------------------------------------
RENDER_ENV = {
    "MODEL": "Qwen/Qwen3-8B", "PEAK_PREFILL_THROUGHPUT": "11000", "RUN_ID": "test-run",
    "CONCURRENCY_LEVELS": "8 16 32", "WARMUP_REQUESTS": "384", "STAGE_REQUESTS": "768",
    "NUM_PREFIXES": "192", "PROMPTS_PER_PREFIX": "4", "SYSTEM_PROMPT_LEN": "4096",
    "QUESTION_LEN": "256", "OUTPUT_LEN": "64", "SEED": "42",
}


class TestConfigurations:
    @pytest.mark.parametrize("name", list(benchctl.CONFIGS))
    def test_every_configuration_has_a_router_config(self, name):
        assert (BENCH / "epp" / f"{benchctl.CONFIGS[name]['epp']}.yaml").exists()

    def test_configurations_match_issue_scope(self):
        assert set(benchctl.CONFIGS) == {
            "random", "approximate", "precise-memory", "precise-valkey", "random-no-lmcache"}
        assert [n for n, c in benchctl.CONFIGS.items() if not c["lmcache"]] == ["random-no-lmcache"]
        assert benchctl.CONFIGS["random-no-lmcache"]["epp"] == "random"

    def test_defaults_run_every_configuration_three_times(self):
        defaults = _script_defaults()
        assert defaults["STRATEGIES"].split() == list(benchctl.CONFIGS)
        assert defaults["RUNS"] == "3"
        example = (BENCH / ".env.example").read_text()
        assert f'# STRATEGIES="{defaults["STRATEGIES"]}"' in example
        assert f"# VALKEY_MAXMEMORY={defaults['VALKEY_MAXMEMORY']}" in example

    def test_describe(self, capsys):
        benchctl.describe(type("A", (), {"name": "random-no-lmcache"}))
        assert capsys.readouterr().out.split() == ["random", "none"]
        with pytest.raises(SystemExit):
            benchctl.describe(type("A", (), {"name": "nope"}))

    def test_render_epp(self, tmp_path):
        render.render_epp(RENDER_ENV, tmp_path)
        rendered = {p.stem for p in (tmp_path / "epp").glob("*.yaml")}
        assert rendered == {"endpoints"} | {c["epp"] for c in benchctl.CONFIGS.values()}
        config = _yaml(tmp_path / "epp" / "precise-valkey.yaml")
        assert _plugin(config, "prefix-cache-affinity-filter")["parameters"]["peakPrefillThroughput"] == 11000

    def test_render_loadgen_one_stage_per_file(self, tmp_path):
        names = render.render_loadgen(RENDER_ENV, "precise-valkey", 2, tmp_path)
        assert names == ["warmup", "c8", "c16", "c32"]
        for name in names:
            config = _yaml(tmp_path / "loadgen" / f"{name}.yaml")
            (stage,) = config["load"]["stages"]
            assert stage["num_requests"] == (384 if name == "warmup" else 768)
            assert stage["concurrency_level"] == (8 if name == "warmup" else int(name[1:]))
            assert config["storage"]["local_storage"]["path"] == f"/results/test-run/precise-valkey/run-2/{name}"
            assert config["data"]["shared_prefix"]["num_unique_system_prompts"] == 192


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
class TestServeVllm:
    """Run serve-vllm.sh with stub `vllm` and `python3` commands that print
    their arguments, so the real flags are checked without a GPU."""

    def _args(self, tmp_path, **env) -> subprocess.CompletedProcess:
        stub = tmp_path / "bin"
        stub.mkdir(exist_ok=True)
        (stub / "vllm").write_text('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\n')
        (stub / "python3").write_text("#!/bin/sh\nexit 0\n")
        for f in stub.iterdir():
            f.chmod(0o755)
        full_env = {"PATH": f"{stub}:{os.environ['PATH']}", "MODEL": "Qwen/Qwen3-8B", "POD_IP": "172.16.90.11", **env}
        return subprocess.run(["bash", str(SERVE_VLLM)], env=full_env, capture_output=True, text=True)

    def test_lmcache_by_default(self, tmp_path):
        result = self._args(tmp_path)
        assert result.returncode == 0, result.stderr
        args = result.stdout.splitlines()
        config = json.loads(args[args.index("--kv-transfer-config") + 1])
        assert config["kv_connector"] == "LMCacheMPConnector"
        assert config["kv_connector_extra_config"]["lmcache.mp.host"] == "tcp://lmcache-server"
        events = json.loads(args[args.index("--kv-events-config") + 1])
        assert events["topic"] == "kv@172.16.90.11:8000@Qwen/Qwen3-8B"
        assert args[args.index("--block-size") + 1] == "64"
        assert "--enable-prefix-caching" in args

    def test_baseline_drops_kv_transfer_config(self, tmp_path):
        result = self._args(tmp_path, KV_CONNECTOR="none")
        assert result.returncode == 0, result.stderr
        args = result.stdout.splitlines()
        assert "--kv-transfer-config" not in args
        assert not any("LMCache" in a for a in args)
        # Everything else is the same as with LMCache.
        with_lmcache = self._args(tmp_path).stdout.splitlines()
        i = with_lmcache.index("--kv-transfer-config")
        assert with_lmcache[:i] + with_lmcache[i + 2:] == args

    def test_unknown_connector_fails(self, tmp_path):
        assert self._args(tmp_path, KV_CONNECTOR="nixl").returncode != 0


# ---------------------------------------------------------------------------
# Valkey sizing
# ---------------------------------------------------------------------------
KV_BYTES_PER_TOKEN = 36 * 8 * 128 * 2 * 2  # Qwen3-8B: layers x KV heads x head dim x (K, V) x bf16


class TestValkeySizing:
    def test_kv_per_token(self):
        assert KV_BYTES_PER_TOKEN == 144 * 1024

    def test_default_maxmemory_holds_default_workload(self):
        d = {k: int(v) for k, v in _script_defaults().items() if v.isdigit()}
        chunk = 256
        prefix_chunks = d["NUM_PREFIXES"] * d["SYSTEM_PROMPT_LEN"] // chunk
        prompts = d["NUM_PREFIXES"] * d["PROMPTS_PER_PREFIX"]
        # Each distinct prompt adds its full chunks past the shared prefix.
        question_chunks = prompts * ((d["SYSTEM_PROMPT_LEN"] + d["QUESTION_LEN"]) // chunk
                                     - d["SYSTEM_PROMPT_LEN"] // chunk)
        assert (prefix_chunks, question_chunks) == (3072, 768)
        assert prefix_chunks * chunk == 786_432
        value = chunk * KV_BYTES_PER_TOKEN  # 36 MiB
        # jemalloc rounds a 36 MiB allocation up to its 40 MiB size class.
        allocated = 2 ** math.floor(math.log2(value))
        allocated += math.ceil((value - allocated) / (allocated // 4)) * (allocated // 4)
        assert allocated == 40 * 1024**2
        expected = (prefix_chunks + question_chunks) * allocated
        assert expected == 150 * benchctl.GIB
        assert benchctl.parse_valkey_bytes(_script_defaults()["VALKEY_MAXMEMORY"]) >= expected * 1.2

    def test_parse_valkey_bytes(self):
        assert benchctl.parse_valkey_bytes("192gb") == 192 * 1024**3
        assert benchctl.parse_valkey_bytes("1g") == 10**9
        assert benchctl.parse_valkey_bytes("512mb") == 512 * 1024**2
        assert benchctl.parse_valkey_bytes("1024") == 1024
        with pytest.raises(ValueError):
            benchctl.parse_valkey_bytes("lots")

    def test_host_ram_preflight(self, tmp_path):
        need = benchctl.required_host_ram("192gb", 16, 4, 16, 8, 16)
        assert need == (192 + 16 + 8 + 4 * 16 + 16) * benchctl.GIB
        with pytest.raises(ValueError):
            benchctl.required_host_ram("0", 16, 4, 16, 8, 16)

        def check(mem_total_gib: int) -> None:
            meminfo = tmp_path / "meminfo"
            meminfo.write_text(f"MemTotal:       {mem_total_gib * 1024 * 1024} kB\nMemFree: 1 kB\n")
            args = type("A", (), dict(valkey_maxmemory="192gb", l1_size_gb=16.0, replicas=4, replica_gib=16.0,
                                      lmcache_server_gib=8.0, system_gib=16.0, meminfo=str(meminfo)))
            benchctl.host_ram_check(args)

        check(384)  # g6e.12xlarge
        with pytest.raises(SystemExit, match="not enough memory"):
            check(256)

    def test_preflight_runs_before_anything_starts(self):
        text = RUN_BENCHMARK.read_text()
        assert text.index("host-ram-check") < text.index("docker compose build")

    def test_both_databases_flushed_by_default_with_router_stopped(self):
        text = RUN_BENCHMARK.read_text()
        assert "FLUSHALL" not in text
        assert "valkey_cli -n 0 FLUSHDB" in text
        assert re.search(r'if \[\[ "\$FLUSH_ROUTER_INDEX" == "1" \]\]; then\n\s+valkey_cli -n 1 FLUSHDB', text)
        assert _script_defaults()["FLUSH_ROUTER_INDEX"] == "1"
        # The router must be gone before its index is flushed.
        assert text.index("docker compose rm -sf epp") < text.index("valkey_cli -n 1 FLUSHDB")

    def test_parse_info(self):
        info = "\r\n".join([
            "# Memory", "used_memory:1073741824", "used_memory_peak:2147483648", "maxmemory:206158430208",
            "maxmemory_policy:noeviction", "# Keyspace", "db0:keys=3840,expires=0,avg_ttl=0",
            "db1:keys=21000,expires=0,avg_ttl=0", "# Errorstats", "errorstat_OOM:count=7",
        ])
        stats = benchctl.parse_info(info)
        assert stats["used_memory"] == 1024**3 and stats["used_memory_peak"] == 2 * 1024**3
        assert stats["keys_per_db"] == {"db0": 3840, "db1": 21000}
        assert stats["oom_errors"] == 7 and stats["maxmemory_policy"] == "noeviction"


# ---------------------------------------------------------------------------
# Counters, summary and metadata
# ---------------------------------------------------------------------------
PROM = """# HELP vllm:prefix_cache_hits Prefix cache hits
# TYPE vllm:prefix_cache_hits counter
vllm:prefix_cache_hits_total{engine="0",model_name="Qwen/Qwen3-8B"} 1000.0
vllm:external_prefix_cache_hits_total{engine="0",model_name="Qwen/Qwen3-8B"} 250.0
vllm:prompt_tokens_total{engine="0",model_name="Qwen/Qwen3-8B"} 4000.0
vllm:prompt_tokens_by_source_total{engine="0",model_name="Qwen/Qwen3-8B",source="local_cache_hit"} 99.0
vllm:request_success_total{engine="0",finished_reason="stop",model_name="Qwen/Qwen3-8B"} 3.0
vllm:request_success_total{engine="0",finished_reason="length",model_name="Qwen/Qwen3-8B"} 2.0
"""


def _snapshot(per_replica: dict[str, float]) -> dict:
    return {"time": 0, "replicas": {r: dict(per_replica) for r in REPLICAS}}


def _write_stage(stage_dir: Path, p50: float, rps: float, local: float, valkey: float, failed: int = 0):
    """A fake inference-perf report plus before/after counter snapshots.
    Each replica serves 1,000 prompt tokens, `local` and `valkey` of them
    from the GPU prefix cache and from Valkey."""
    (stage_dir / "inference-perf").mkdir(parents=True)
    report = {
        "load_summary": {"count": 10},
        "successes": {"count": 10, "latency": {"time_to_first_token": {"median": p50, "p90": p50 * 2, "p99": p50 * 3}},
                      "prompt_tokens": {"total": 4000, "cached": (local + valkey) * 4},
                      "throughput": {"requests_per_sec": rps}},
        "failures": {"count": failed},
    }
    (stage_dir / "inference-perf" / "stage_0_lifecycle_metrics.json").write_text(json.dumps(report))
    base = {name: 100.0 for name in benchctl.COUNTERS}
    after = {**base, "vllm:prompt_tokens_total": 1100.0, "vllm:prefix_cache_hits_total": 100.0 + local,
             "vllm:external_prefix_cache_hits_total": 100.0 + valkey}
    (stage_dir / "counters-before.json").write_text(json.dumps(_snapshot(base)))
    (stage_dir / "counters-after.json").write_text(json.dumps(_snapshot(after)))


META = {
    "date_utc": "2026-11-20T10:00:00Z", "cloud": "aws", "instance_type": "g6e.12xlarge", "region": "ap-northeast-1",
    "gpu_model": "NVIDIA L40S", "gpu_count": 4, "gpu_memory_mib": 46068, "gpu_driver": "580.95.05",
    "model": "Qwen/Qwen3-8B", "vllm_version": "0.30.0", "lmcache_version": "0.5.5",
    "git_commit": "0123456789abcdef", "git_dirty": False,
}


class TestCounters:
    def test_parse_counters_sums_label_sets(self):
        counters = benchctl.parse_counters(PROM)
        assert counters["vllm:prefix_cache_hits_total"] == 1000
        assert counters["vllm:external_prefix_cache_hits_total"] == 250
        assert counters["vllm:request_success_total"] == 5
        # Similar names are not mixed in.
        assert counters["vllm:prompt_tokens_total"] == 4000

    def test_same_hit_counters_as_the_notebook(self):
        notebook = (HERE / "llm-d-serving-with-valkey.ipynb").read_text()
        for name in ("vllm:prefix_cache_hits_total", "vllm:external_prefix_cache_hits_total"):
            assert name in notebook and name in benchctl.COUNTERS

    def test_counter_delta(self):
        before = _snapshot({"vllm:prompt_tokens_total": 10.0})
        after = _snapshot({"vllm:prompt_tokens_total": 35.0})
        assert summarize.counter_delta(before, after, "vllm:prompt_tokens_total") == 4 * 25


class TestSummarize:
    @pytest.fixture
    def run_dir(self, tmp_path):
        # Three runs of one configuration at two concurrency levels.
        runs = {1: (0.120, 4.0, 600, 300), 2: (0.100, 4.4, 640, 280), 3: (0.140, 3.8, 620, 260)}
        for run, (p50, rps, local, valkey) in runs.items():
            for level, factor in ((8, 1.0), (16, 2.0)):
                _write_stage(tmp_path / "precise-valkey" / f"run-{run}" / f"c{level}",
                             p50 * factor, rps * factor, local, valkey, failed=1 if run == 3 else 0)
            # Warm-up is ignored.
            _write_stage(tmp_path / "precise-valkey" / f"run-{run}" / "warmup", 9.0, 0.1, 0, 0)
            info = {"used_memory": 150 * benchctl.GIB, "used_memory_peak": 151 * benchctl.GIB,
                    "maxmemory": 192 * benchctl.GIB, "keys_per_db": {"db0": 3840, "db1": 20000},
                    "oom_errors": 3 if run == 2 else 0}
            (tmp_path / "precise-valkey" / f"run-{run}" / "valkey.json").write_text(json.dumps(info))
            (tmp_path / "precise-valkey" / f"run-{run}" / "valkey-before.json").write_text(
                json.dumps({**info, "keys_per_db": {"db1": 1}}))
        (tmp_path / "metadata.json").write_text(json.dumps(META))
        return tmp_path

    def test_median_and_spread(self, run_dir):
        data = summarize.collect(run_dir)
        c8 = data["precise-valkey"][8]
        assert c8["runs"] == 3 and c8["failed"] == [0, 0, 1]
        assert c8["ttft_p50"] == {"median": 0.120, "min": 0.100, "max": 0.140, "n": 3}
        assert c8["ttft_p99"]["median"] == pytest.approx(0.360)
        assert c8["requests_per_s"] == {"median": 4.0, "min": 3.8, "max": 4.4, "n": 3}
        assert c8["local_share"]["median"] == pytest.approx(0.62)
        assert (c8["local_share"]["min"], c8["local_share"]["max"]) == (pytest.approx(0.60), pytest.approx(0.64))
        assert c8["valkey_share"]["median"] == pytest.approx(0.28)
        assert c8["usage_cached_share"]["median"] == pytest.approx(0.90)
        assert data["precise-valkey"][16]["ttft_p50"]["median"] == pytest.approx(0.240)

    def test_spread_ignores_missing_values(self):
        assert summarize.spread([None, 2.0, 1.0, 3.0]) == {"median": 2.0, "min": 1.0, "max": 3.0, "n": 3}
        assert summarize.spread([None]) is None

    def test_markdown(self, run_dir):
        text, _ = summarize.render(run_dir)
        line = metadata.metadata_line(META)
        assert "aws g6e.12xlarge in ap-northeast-1" in line and "4x NVIDIA L40S 45 GiB" in line
        assert "2026-11-20T10:00:00Z" in line and "lmcache 0.5.5" in line
        lines = text.splitlines()
        # The metadata line sits directly above (one blank line) every table.
        headers = [i for i, row in enumerate(lines) if row.startswith("| Configuration |")]
        assert len(headers) == 2
        for i in headers:
            assert lines[i - 2] == line and lines[i - 1] == ""
        assert "| precise-valkey | 8 | 3 | 120 (100–140) | 240 (200–280) | 360 (300–420) | 4.00 (3.80–4.40) " \
               "| 62% (60–64%) | 28% (26–30%) | 1 |" in text
        assert "rejected writes (OOM) in precise-valkey run 2" in text
        assert "| precise-valkey | 1 | 150.0 | 151.0 | 192 | 3840 | 20000 | 1 | 0 |" in text


class TestMetadata:
    def test_required_fields(self):
        probes = {"gpus": metadata.parse_nvidia_smi("NVIDIA L40S, 46068, 580.95.05\n" * 4),
                  "host_ram_bytes": 384 * benchctl.GIB,
                  "images": {"vllm-0": {"ref": "x", "id": "sha256:1"}},
                  "versions": {"lmcache": "0.5.5", "valkey_glide_sync": "2.5.2", "vllm": "0.30.0"},
                  "git_commit": "abc", "git_dirty": False}
        env = {"BENCH_CLOUD": "aws", "BENCH_INSTANCE_TYPE": "g6e.12xlarge", "BENCH_REGION": "ap-northeast-1",
               "MODEL": "Qwen/Qwen3-8B", **{k: "1" for k in metadata.WORKLOAD_VARS}}
        meta = metadata.build_metadata(env, probes)
        for field in metadata.REQUIRED_FIELDS:
            assert field in meta, field
        assert meta["gpu_count"] == 4 and meta["gpu_model"] == "NVIDIA L40S"
        assert meta["gpu_memory_mib"] == 46068 and meta["gpu_driver"] == "580.95.05"
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", meta["date_utc"])
        assert set(meta["workload"]) == {k.lower() for k in metadata.WORKLOAD_VARS}
        assert meta["stack"]["router_index"] == "redis://valkey:6379/1"
        assert meta["stack"]["lmcache_chunk_size"] == 256 and meta["stack"]["vllm_block_size"] == 64

    def test_unset_location_is_unknown(self):
        meta = metadata.build_metadata({}, {})
        assert (meta["cloud"], meta["instance_type"], meta["region"]) == (None, None, None)
        assert "on unknown unknown in unknown" in metadata.metadata_line(meta)

    def test_mixed_gpus_listed(self):
        gpus = metadata.parse_nvidia_smi("NVIDIA L4, 23034, 580\nNVIDIA L40S, 46068, 580\n")
        meta = metadata.build_metadata({}, {"gpus": gpus})
        assert meta["gpu_model"] == ["NVIDIA L4", "NVIDIA L40S"] and meta["gpu_driver"] == "580"

    def test_no_vendor_specific_code_in_the_benchmark(self):
        # Only terraform/aws/ knows about AWS; the scripts read BENCH_* only.
        for path in [*(p for p in SCRIPTS.iterdir() if p.is_file()), COMPOSE_PATH, SERVE_VLLM, DOCKERFILE]:
            text = path.read_text().lower()
            assert "169.254.169.254" not in text and "imds" not in text, path.name


class TestTerraformLayout:
    def test_state_and_plugins_ignored(self):
        ignored = (BENCH / "terraform" / "aws" / ".gitignore").read_text().split()
        assert ".terraform/" in ignored and "*.tfstate" in ignored and "*.tfvars" in ignored

    def test_defaults(self):
        variables = (BENCH / "terraform" / "aws" / "variables.tf").read_text()
        assert re.search(r'variable "instance_type" \{[^}]*default\s+= "g6e\.12xlarge"', variables)
        assert re.search(r'variable "region" \{[^}]*type\s+= string', variables)
        root = re.search(r'variable "root_volume_gb" \{[^}]*default\s+= (\d+)', variables)
        assert int(root.group(1)) >= 150

    def test_push_stack_sends_the_benchmark_dir(self):
        text = (BENCH / "terraform" / "aws" / "push-stack.sh").read_text()
        assert 'BENCH_DIR="$(cd ../.. && pwd)"' in text and '"$BENCH_DIR/compose.yaml"' in text
        assert "prompt-routing" not in text
