#!/usr/bin/env python3
"""Record what produced a benchmark run, as results/<run>/metadata.json.

  metadata.py collect --out results/<run>/metadata.json

Run on the host by run-benchmark.sh while the stack is up. It reads the GPUs
from nvidia-smi, host RAM from /proc/meminfo, the images each container
actually runs from `docker inspect`, the lmcache, vLLM and GLIDE versions from
inside the containers, the git commit of this repository, and the workload
and stack settings from the environment.

Where the run happened comes from three environment variables, so the
benchmark itself stays the same on any host:

  BENCH_CLOUD           e.g. aws, gcp, azure, on-prem
  BENCH_INSTANCE_TYPE   e.g. g6e.12xlarge
  BENCH_REGION          e.g. ap-northeast-1

Unset ones are recorded as null, and the summary says "unknown". The
optional AWS Terraform (terraform/aws/) fills them from instance metadata.

Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent.parent

# Fields every metadata.json has (values may be null if a probe failed).
REQUIRED_FIELDS = (
    "date_utc", "cloud", "instance_type", "region",
    "gpu_model", "gpu_count", "gpu_memory_mib", "gpu_driver", "host_ram_bytes",
    "images", "lmcache_version", "valkey_glide_sync_version", "vllm_version",
    "model", "workload", "stack", "git_commit", "git_dirty",
)

# Workload and stack settings copied from the environment run-benchmark.sh
# exports, with the names they have in .env.
WORKLOAD_VARS = (
    "NUM_PREFIXES", "PROMPTS_PER_PREFIX", "SYSTEM_PROMPT_LEN", "QUESTION_LEN",
    "OUTPUT_LEN", "SEED", "WARMUP_REQUESTS", "STAGE_REQUESTS",
    "CONCURRENCY_LEVELS", "STRATEGIES", "RUNS",
)
STACK_VARS = (
    "DTYPE", "MAX_MODEL_LEN", "MAX_NUM_BATCHED_TOKENS", "GPU_MEMORY_UTILIZATION",
    "PEAK_PREFILL_THROUGHPUT", "VALKEY_MAXMEMORY", "LMCACHE_L1_SIZE_GB",
    "LMCACHE_EVICTION_POLICY", "LMCACHE_L2_STORE_POLICY", "LMCACHE_MAX_GPU_WORKERS",
    "LMCACHE_SERVER_TRANSFER_MODE", "LMCACHE_MP_TRANSFER_MODE", "FLUSH_ROUTER_INDEX",
)
# Fixed in serve-vllm.sh, compose.yaml and the router configs.
FIXED_STACK = {"vllm_block_size": 64, "router_block_size_tokens": 64, "lmcache_chunk_size": 256,
               "router_index": "redis://valkey:6379/1", "lmcache_l2": "valkey:6379 database 0"}


def run(cmd: list[str], errors: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=BENCH_DIR).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        errors.append(f"{' '.join(cmd[:4])}: {detail.strip()[:200]}")
        return None


def parse_nvidia_smi(csv: str | None) -> list[dict]:
    """`nvidia-smi --query-gpu=name,memory.total,driver_version
    --format=csv,noheader,nounits` -> one dict per GPU."""
    gpus = []
    for line in (csv or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            gpus.append({"name": parts[0], "memory_mib": int(float(parts[1])), "driver": parts[2]})
    return gpus


def _one(values: list) -> object:
    """The value if every GPU agrees, else the list."""
    unique = sorted(set(values), key=str)
    if not unique:
        return None
    return unique[0] if len(unique) == 1 else unique


def build_metadata(env: dict[str, str], probes: dict) -> dict:
    """Assemble metadata.json from the environment and probe results.

    probes: gpus (list from parse_nvidia_smi), host_ram_bytes, images
    ({service: {...}}), versions ({"lmcache": .., "valkey_glide_sync": ..,
    "vllm": ..}), pip_changes, git_commit, git_dirty, errors.
    """
    gpus = probes.get("gpus") or []
    versions = probes.get("versions") or {}
    return {
        "date_utc": probes.get("date_utc")
        or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": env.get("RUN_ID"),
        "cloud": env.get("BENCH_CLOUD") or None,
        "instance_type": env.get("BENCH_INSTANCE_TYPE") or None,
        "region": env.get("BENCH_REGION") or None,
        "gpu_model": _one([g["name"] for g in gpus]),
        "gpu_count": len(gpus),
        "gpu_memory_mib": _one([g["memory_mib"] for g in gpus]),
        "gpu_driver": _one([g["driver"] for g in gpus]),
        "gpus": gpus,
        "host_ram_bytes": probes.get("host_ram_bytes"),
        "images": probes.get("images") or {},
        "lmcache_version": versions.get("lmcache"),
        "valkey_glide_sync_version": versions.get("valkey_glide_sync"),
        "vllm_version": versions.get("vllm"),
        "lmcache_pip_changes": probes.get("pip_changes"),
        "model": env.get("MODEL"),
        "workload": {name.lower(): env.get(name) for name in WORKLOAD_VARS},
        "stack": {**{name.lower(): env.get(name) for name in STACK_VARS}, **FIXED_STACK},
        "git_commit": probes.get("git_commit"),
        "git_dirty": probes.get("git_dirty"),
        "probe_errors": probes.get("errors") or [],
    }


def metadata_line(meta: dict) -> str:
    """One line naming where and when the numbers below it were measured."""
    def known(value) -> str:
        return "unknown" if value in (None, "", []) else str(value)

    gpu_mem = meta.get("gpu_memory_mib")
    gpu = f"{meta.get('gpu_count') or 0}x {known(meta.get('gpu_model'))}"
    if isinstance(gpu_mem, int):
        gpu += f" {gpu_mem / 1024:.0f} GiB"
    commit = (meta.get("git_commit") or "unknown")[:12]
    if meta.get("git_dirty"):
        commit += " (modified)"
    return (f"Measured {known(meta.get('date_utc'))} on {known(meta.get('cloud'))} "
            f"{known(meta.get('instance_type'))} in {known(meta.get('region'))}: {gpu}, "
            f"driver {known(meta.get('gpu_driver'))}; model {known(meta.get('model'))}, "
            f"vLLM {known(meta.get('vllm_version'))}, lmcache {known(meta.get('lmcache_version'))}; "
            f"commit {commit}.")


def _container_python(service: str, code: str, errors: list[str]) -> str | None:
    return run(["docker", "compose", "exec", "-T", service, "python3", "-c", code], errors)


def collect() -> dict:
    errors: list[str] = []
    probes: dict = {"errors": errors}

    probes["gpus"] = parse_nvidia_smi(run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"], errors))
    try:
        from benchctl import host_mem_total

        probes["host_ram_bytes"] = host_mem_total(Path("/proc/meminfo").read_text())
    except (OSError, ValueError) as exc:
        errors.append(f"/proc/meminfo: {exc}")

    # The image each running container uses, and every image the compose
    # file names (loadgen and model-download only run on demand).
    images: dict[str, dict] = {}
    for service in ("valkey", "lmcache-server", "vllm-0", "vllm-1", "vllm-2", "vllm-3", "envoy", "epp"):
        cid = run(["docker", "compose", "ps", "-q", service], errors)
        if not cid:
            continue
        ref_and_id = run(["docker", "inspect", "--format", "{{.Config.Image}}|{{.Image}}", cid], errors)
        if ref_and_id:
            ref, image_id = ref_and_id.split("|", 1)
            images[service] = {"ref": ref, "id": image_id}
    refs = run(["docker", "compose", "--profile", "tools", "config", "--images"], errors) or ""
    for ref in sorted(set(refs.split())):
        out = run(["docker", "image", "inspect", "--format", "{{.Id}}|{{json .RepoDigests}}", ref], errors)
        if out:
            image_id, digests = out.split("|", 1)
            images.setdefault("by_ref", {})[ref] = {"id": image_id, "repo_digests": json.loads(digests)}
    probes["images"] = images

    def version(package: str) -> str:
        return f"import importlib.metadata as m; print(m.version({package!r}))"

    probes["versions"] = {
        "lmcache": _container_python("lmcache-server", version("lmcache"), errors),
        "valkey_glide_sync": _container_python("lmcache-server", version("valkey-glide-sync"), errors),
        "vllm": _container_python("vllm-0", "import vllm; print(vllm.__version__)", errors),
        "lmcache_in_vllm_0": _container_python("vllm-0", version("lmcache"), errors),
    }
    probes["pip_changes"] = run(["docker", "compose", "exec", "-T", "vllm-0", "cat", "/opt/bench/pip-changes.txt"],
                                errors)
    probes["git_commit"] = run(["git", "rev-parse", "HEAD"], errors)
    status = run(["git", "status", "--porcelain", "--", "."], errors)
    probes["git_dirty"] = None if status is None else bool(status)
    # A copy pushed without .git (e.g. terraform/aws/push-stack.sh) carries
    # the commit in .stack-commit: the commit on line 1, "dirty" or "clean" on line 2.
    stack_commit = Path(__file__).resolve().parent.parent / ".stack-commit"
    if probes["git_commit"] is None and stack_commit.is_file():
        lines = stack_commit.read_text().split()
        if lines:
            probes["git_commit"] = lines[0]
            probes["git_dirty"] = len(lines) > 1 and lines[1] == "dirty"
            errors[:] = [e for e in errors if not e.startswith("git ")]

    meta = build_metadata(dict(os.environ), probes)
    meta["lmcache_version_in_replicas"] = probes["versions"]["lmcache_in_vllm_0"]
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--out", required=True)
    args = parser.parse_args()

    meta = collect()
    Path(args.out).write_text(json.dumps(meta, indent=2) + "\n")
    for error in meta["probe_errors"]:
        print(f"metadata: warning: {error}", file=sys.stderr)
    for field in ("cloud", "instance_type", "region"):
        if meta[field] is None:
            print(f"metadata: warning: BENCH_{field.upper()} is not set; recorded as unknown", file=sys.stderr)
    print(metadata_line(meta))


if __name__ == "__main__":
    main()
