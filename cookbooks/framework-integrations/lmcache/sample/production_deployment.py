"""
03 - Production Deployment: Cluster mode, TLS, tuning, and monitoring.

Demonstrates production configuration patterns for LMCache with Valkey.
Generates config files for different deployment scenarios and shows how
to monitor cache effectiveness.

NOTE: UNTESTED — the config generator runs anywhere, but actual LMCache
usage requires Linux + NVIDIA GPU + vLLM. Based on LMCache official docs.

Prerequisites:
    - Valkey running (standalone for local demo, cluster for full test)
    - pip install -r requirements.txt

Usage:
    # Local standalone demo (monitoring only)
    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
    python production_deployment.py --mode standalone

    # Cluster mode (requires a Valkey cluster)
    python production_deployment.py --mode cluster --host my-cluster.endpoint:6379

    # ElastiCache Serverless (requires TLS endpoint)
    python production_deployment.py --mode serverless --host my-cache.serverless.region.cache.amazonaws.com:6379
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path


def generate_standalone_config(host: str = "localhost:6379") -> str:
    """Generate config for standalone Valkey."""
    addr, port = _parse_host(host)
    return textwrap.dedent(f"""\
        chunk_size: 256
        local_cpu: true
        max_local_cpu_size: 5.0
        remote_url: "valkey://{addr}:{port}"
        remote_serde: "naive"
        extra_config:
          valkey_num_workers: 8
          request_timeout: 5.0
          connection_timeout: 10.0
    """)


def generate_cluster_config(host: str) -> str:
    """Generate config for Valkey cluster mode."""
    addr, port = _parse_host(host)
    return textwrap.dedent(f"""\
        chunk_size: 256
        local_cpu: true
        max_local_cpu_size: 10.0
        remote_url: "valkey://{addr}:{port}"
        remote_serde: "cachegen"
        pre_caching_hash_algorithm: sha256_cbor_64bit
        extra_config:
          valkey_mode: "cluster"
          valkey_num_workers: 32
          request_timeout: 5.0
          connection_timeout: 10.0
    """)


def generate_serverless_config(host: str) -> str:
    """Generate config for ElastiCache Serverless (TLS required)."""
    addr, port = _parse_host(host)
    return textwrap.dedent(f"""\
        chunk_size: 256
        local_cpu: true
        max_local_cpu_size: 10.0
        remote_url: "valkey://{addr}:{port}"
        remote_serde: "cachegen"
        pre_caching_hash_algorithm: sha256_cbor_64bit
        extra_config:
          valkey_mode: "cluster"
          tls_enable: true
          valkey_num_workers: 32
          request_timeout: 5.0
          connection_timeout: 10.0
    """)


def monitor_cache_stats(host: str = "localhost", port: int = 6379) -> None:
    """Query Valkey for cache-related metrics."""
    print("\n--- Valkey Cache Metrics ---")

    commands = [
        ("DBSIZE", "Total keys (KV cache chunks stored)"),
        ("INFO memory", "Memory usage"),
        ("INFO stats", "Keyspace hit/miss stats"),
    ]

    for cmd, description in commands:
        print(f"\n{description}:")
        result = subprocess.run(
            ["valkey-cli", "-h", host, "-p", str(port)] + cmd.split(),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # Filter to relevant lines for INFO commands
            if "keyspace" in cmd.lower() or "memory" in description.lower():
                lines = [
                    line for line in output.splitlines()
                    if any(k in line for k in [
                        "keyspace_hits", "keyspace_misses",
                        "used_memory_human", "used_memory_peak_human",
                    ])
                ]
                print("  " + "\n  ".join(lines) if lines else f"  {output}")
            else:
                print(f"  {output}")
        else:
            print(f"  (could not connect: {result.stderr.strip()})")

    # Calculate hit rate
    result = subprocess.run(
        ["valkey-cli", "-h", host, "-p", str(port), "INFO", "stats"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        hits = misses = 0
        for line in result.stdout.splitlines():
            if line.startswith("keyspace_hits:"):
                hits = int(line.split(":")[1])
            elif line.startswith("keyspace_misses:"):
                misses = int(line.split(":")[1])
        total = hits + misses
        if total > 0:
            rate = hits / total * 100
            print(f"\n  Cache hit rate: {rate:.1f}% ({hits}/{total})")
        else:
            print("\n  No keyspace activity yet.")


def _parse_host(host: str) -> tuple[str, str]:
    """Parse host:port string, defaulting port to 6379."""
    if ":" in host:
        addr, port = host.rsplit(":", 1)
        return addr, port
    return host, "6379"


def main() -> None:
    """Generate config and optionally monitor cache stats."""
    parser = argparse.ArgumentParser(
        description="LMCache + Valkey production configuration generator"
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "cluster", "serverless"],
        default="standalone",
        help="Deployment mode (default: standalone)",
    )
    parser.add_argument(
        "--host",
        default="localhost:6379",
        help="Valkey host:port (default: localhost:6379)",
    )
    parser.add_argument(
        "--output",
        default="lmcache_config.yaml",
        help="Output config file path (default: lmcache_config.yaml)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Query Valkey for cache metrics after generating config",
    )
    args = parser.parse_args()

    generators = {
        "standalone": generate_standalone_config,
        "cluster": generate_cluster_config,
        "serverless": generate_serverless_config,
    }

    config = generators[args.mode](args.host)
    output_path = Path(args.output)
    output_path.write_text(config)

    print(f"Generated {args.mode} config → {output_path}")
    print(f"\n{config}")

    print("Launch vLLM with:")
    print(f"  PYTHONHASHSEED=0 \\")
    print(f"  LMCACHE_CONFIG_FILE={output_path} \\")
    print(f"  vllm serve <model> \\")
    print(f"    --kv-transfer-config \\")
    print(f"    '{{\"kv_connector\":\"LMCacheConnectorV1\",\"kv_role\":\"kv_both\"}}'")

    if args.monitor:
        addr, port = _parse_host(args.host)
        monitor_cache_stats(addr, int(port))


if __name__ == "__main__":
    main()
