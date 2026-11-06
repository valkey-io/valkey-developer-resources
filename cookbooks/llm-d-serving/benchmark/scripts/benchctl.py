#!/usr/bin/env python3
"""Helpers for run-benchmark.sh.

Run inside the bench network (``docker compose run ... loadgen``), because
they reach the fixed container addresses:

  calibrate        measure peak prefill throughput on one vLLM replica
  wait-router      block until a completion succeeds through Envoy and the EPP
  snapshot         record every replica's cache-hit counters to a JSON file

Run on the host:

  describe         print a configuration's router config and KV connector
  valkey-stats     turn `valkey-cli INFO` output (stdin) into JSON
  host-ram-check   refuse to start if the host can't hold Valkey's maxmemory
                   plus the replicas and the LMCache server

Standard library only, so it runs in any image with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

# Each configuration is a router config (epp/<epp>.yaml) plus whether the
# replicas run with LMCacheMPConnector. Every configuration except the
# baseline shares KV through LMCache and Valkey.
CONFIGS = {
    "random-no-lmcache": {"epp": "random", "lmcache": False},
    "random": {"epp": "random", "lmcache": True},
    "approximate": {"epp": "approximate", "lmcache": True},
    "precise-memory": {"epp": "precise-memory", "lmcache": True},
    "precise-valkey": {"epp": "precise-valkey", "lmcache": True},
}

# Fixed addresses from compose.yaml.
REPLICA_URLS = {
    "vllm-0": "http://172.16.90.11:8000",
    "vllm-1": "http://172.16.90.12:8000",
    "vllm-2": "http://172.16.90.13:8000",
    "vllm-3": "http://172.16.90.14:8000",
}
ROUTER_URL = "http://172.16.90.10:8081"

# vLLM Prometheus counters (vllm/v1/metrics/loggers.py in v0.30.0; the
# Prometheus client adds _total). The recipe notebook reads the same two hit
# counters to tell local hits from Valkey hits:
#   prefix_cache_hits      prompt tokens found in the replica's GPU prefix cache
#   external_prefix_cache_hits
#                          prompt tokens the KV connector (LMCache, so Valkey)
#                          supplied
#   prompt_tokens          all prompt tokens, the denominator for both shares
COUNTERS = (
    "vllm:prompt_tokens_total",
    "vllm:prefix_cache_queries_total",
    "vllm:prefix_cache_hits_total",
    "vllm:external_prefix_cache_queries_total",
    "vllm:external_prefix_cache_hits_total",
    "vllm:request_success_total",
    "vllm:generation_tokens_total",
)

GIB = 1024**3


def post(url: str, body: dict | None = None, timeout: float = 30.0):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Surface the server's explanation (vLLM puts it in the body).
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"POST {url} returned HTTP {exc.code}: {detail}") from None


def time_to_first_token(endpoint: str, model: str, n_tokens: int) -> float:
    # Random token IDs, so the prefix cache misses and we time a full prefill.
    # IDs stay well inside Qwen3's vocabulary and away from special tokens.
    prompt = [random.randint(1000, 100_000) for _ in range(n_tokens)]
    body = {"model": model, "prompt": prompt, "max_tokens": 1, "temperature": 0, "stream": True}
    start = time.perf_counter()
    with post(f"{endpoint}/v1/completions", body, timeout=300) as resp:
        for raw in resp:
            if raw.startswith(b"data:") and raw.strip() != b"data: [DONE]":
                elapsed = time.perf_counter() - start
                for _ in resp:  # drain the stream
                    pass
                return elapsed
    raise RuntimeError("stream ended without a token")


def calibrate(args: argparse.Namespace) -> None:
    """peakPrefillThroughput = chunk / median(TTFT), the method llm-d's
    guides/recipes/router/calibration uses. chunk should equal vLLM's
    --max-num-batched-tokens."""
    for _ in range(args.warmup):
        time_to_first_token(args.endpoint, args.model, args.chunk)
    samples = [time_to_first_token(args.endpoint, args.model, args.chunk) for _ in range(args.measure)]
    median = statistics.median(samples)
    print(
        f"calibrate: chunk={args.chunk} median_ttft={median:.4f}s "
        f"min={min(samples):.4f}s max={max(samples):.4f}s",
        file=sys.stderr,
    )
    print(round(args.chunk / median))


def wait_router(args: argparse.Namespace) -> None:
    body = {"model": args.model, "prompt": "ping", "max_tokens": 1}
    deadline = time.monotonic() + args.timeout
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            with post(f"{args.url}/v1/completions", body, timeout=30) as resp:
                if resp.status == 200:
                    print("wait-router: router is serving", file=sys.stderr)
                    return
                last_error = f"HTTP {resp.status}"
        except (urllib.error.URLError, OSError, RuntimeError) as exc:
            last_error = str(exc)
        time.sleep(3)
    sys.exit(f"wait-router: router not serving after {args.timeout}s (last error: {last_error})")


def parse_counters(text: str, names=COUNTERS) -> dict[str, float]:
    """Sum each counter over all its label sets in a Prometheus text page."""
    totals = {name: 0.0 for name in names}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(\S+)", line)
        if match and match.group(1) in totals:
            totals[match.group(1)] += float(match.group(3))
    return totals


def snapshot(args: argparse.Namespace) -> None:
    out = {"time": time.time(), "replicas": {}}
    for name, url in REPLICA_URLS.items():
        with urllib.request.urlopen(f"{url}/metrics", timeout=10) as resp:
            text = resp.read().decode()
        counters = parse_counters(text)
        missing = [n for n in COUNTERS if f"{n} " not in text and f"{n}{{" not in text]
        if missing:
            print(f"snapshot: {name} does not export {', '.join(missing)}", file=sys.stderr)
        out["replicas"][name] = counters
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"snapshot: wrote {args.out}", file=sys.stderr)


def describe(args: argparse.Namespace) -> None:
    if args.name not in CONFIGS:
        sys.exit(f"unknown configuration: {args.name} (known: {' '.join(CONFIGS)})")
    config = CONFIGS[args.name]
    print(config["epp"], "lmcache" if config["lmcache"] else "none")


def parse_info(text: str) -> dict:
    """Parse `INFO memory keyspace errorstats` into the fields the summary
    needs: memory, per-database key counts, and OOM rejections."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            fields[key] = value
    keys_per_db = {}
    for key, value in fields.items():
        if re.fullmatch(r"db\d+", key):
            stats = dict(part.split("=", 1) for part in value.split(","))
            keys_per_db[key] = int(stats["keys"])
    oom = 0
    if "errorstat_OOM" in fields:
        oom = int(dict(p.split("=", 1) for p in fields["errorstat_OOM"].split(","))["count"])
    return {
        "used_memory": int(fields["used_memory"]),
        "used_memory_peak": int(fields["used_memory_peak"]),
        "maxmemory": int(fields.get("maxmemory", 0)),
        "maxmemory_policy": fields.get("maxmemory_policy"),
        "keys_per_db": keys_per_db,
        "oom_errors": oom,
    }


def valkey_stats(args: argparse.Namespace) -> None:
    json.dump(parse_info(sys.stdin.read()), sys.stdout, indent=2)
    print()


def parse_valkey_bytes(value: str) -> int:
    """Valkey's memory units: k/m/g are powers of 1000, kb/mb/gb of 1024."""
    match = re.fullmatch(r"\s*(\d+)\s*(b|k|kb|m|mb|g|gb)?\s*", value.lower())
    if not match:
        raise ValueError(f"not a Valkey memory size: {value!r} (use e.g. 192gb)")
    units = {None: 1, "b": 1, "k": 1000, "kb": 1024, "m": 1000**2, "mb": 1024**2, "g": 1000**3, "gb": GIB}
    return int(match.group(1)) * units[match.group(2)]


def required_host_ram(valkey_maxmemory: str, l1_size_gb: float, replicas: int,
                      replica_gib: float, lmcache_server_gib: float, system_gib: float) -> int:
    """Host RAM the stack needs, in bytes: Valkey's maxmemory, the LMCache
    server's L1 (LMCache's GB are GiB) plus its own process, each vLLM
    replica's host memory, and a reserve for the OS, Docker and the router."""
    if parse_valkey_bytes(valkey_maxmemory) == 0:
        raise ValueError("VALKEY_MAXMEMORY must be set (0 means unlimited in Valkey)")
    return int(parse_valkey_bytes(valkey_maxmemory)
               + (l1_size_gb + lmcache_server_gib + replicas * replica_gib + system_gib) * GIB)


def host_mem_total(meminfo: str) -> int:
    match = re.search(r"^MemTotal:\s+(\d+) kB", meminfo, re.M)
    if not match:
        raise ValueError("MemTotal not found in /proc/meminfo")
    return int(match.group(1)) * 1024


def host_ram_check(args: argparse.Namespace) -> None:
    try:
        need = required_host_ram(args.valkey_maxmemory, args.l1_size_gb, args.replicas,
                                 args.replica_gib, args.lmcache_server_gib, args.system_gib)
        with open(args.meminfo) as fh:
            have = host_mem_total(fh.read())
    except (OSError, ValueError) as exc:
        sys.exit(f"host-ram-check: {exc}")
    summary = (f"host RAM {have / GIB:.0f} GiB; needed {need / GIB:.0f} GiB = Valkey maxmemory "
               f"{parse_valkey_bytes(args.valkey_maxmemory) / GIB:.0f} GiB + LMCache L1 {args.l1_size_gb:g} GiB "
               f"+ LMCache server {args.lmcache_server_gib:g} GiB + {args.replicas} replicas x "
               f"{args.replica_gib:g} GiB + system {args.system_gib:g} GiB")
    if have < need:
        sys.exit(f"host-ram-check: not enough memory: {summary}. Lower VALKEY_MAXMEMORY and the "
                 "workload (README.md, \"Sizing Valkey\"), or use a larger host.")
    print(f"host-ram-check: ok, {summary}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("calibrate")
    p.add_argument("--endpoint", default=REPLICA_URLS["vllm-0"], help="one vLLM replica")
    p.add_argument("--model", required=True)
    p.add_argument("--chunk", type=int, default=8192)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--measure", type=int, default=20)
    p.set_defaults(func=calibrate)

    p = sub.add_parser("wait-router")
    p.add_argument("--url", default=ROUTER_URL)
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(func=wait_router)

    p = sub.add_parser("snapshot")
    p.add_argument("--out", required=True)
    p.set_defaults(func=snapshot)

    p = sub.add_parser("describe")
    p.add_argument("name")
    p.set_defaults(func=describe)

    p = sub.add_parser("valkey-stats")
    p.set_defaults(func=valkey_stats)

    p = sub.add_parser("host-ram-check")
    p.add_argument("--valkey-maxmemory", required=True)
    p.add_argument("--l1-size-gb", type=float, required=True)
    p.add_argument("--replicas", type=int, default=len(REPLICA_URLS))
    p.add_argument("--replica-gib", type=float, required=True)
    p.add_argument("--lmcache-server-gib", type=float, required=True)
    p.add_argument("--system-gib", type=float, required=True)
    p.add_argument("--meminfo", default="/proc/meminfo")
    p.set_defaults(func=host_ram_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
