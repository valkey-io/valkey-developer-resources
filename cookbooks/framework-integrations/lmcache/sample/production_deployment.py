"""03 - Production Deployment: generate and validate LMCache Valkey configs.

Generates configs for the legacy in-process connector (standalone,
cluster, TLS/ElastiCache Serverless) and the current recommended MP-mode
``--l2-adapter`` JSON, then round-trips each legacy config through
LMCache's real ``load_engine_config_with_overrides`` to prove it actually
parses — not just that it looks right.

Also includes a ``--monitor`` mode that queries Valkey for cache-related
metrics via a real GLIDE client (no ``valkey-cli`` binary required).

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:8.1.1
    python production_deployment.py --mode standalone --monitor
    python production_deployment.py --mode cluster --host my-cluster.endpoint:6379
    python production_deployment.py --mode serverless --host my-cache.serverless.region.cache.amazonaws.com:6379
    python production_deployment.py --mode mp --host 127.0.0.1:6379
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import textwrap
from pathlib import Path

from common import connection_settings, create_client, load_lmcache_config, parse_host, parse_startup_nodes


def generate_standalone_config(host: str = "localhost:6379") -> str:
    """Generate a legacy in-process config for standalone Valkey."""
    addr, port = parse_host(host)
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
    """Generate a legacy in-process config for Valkey cluster mode."""
    addr, port = parse_host(host)
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
    """Generate a legacy in-process config for ElastiCache Serverless (TLS required)."""
    addr, port = parse_host(host)
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


def generate_mp_l2_adapter(host: str, cluster_mode: bool = False) -> dict:
    """Generate the current recommended MP-mode ``--l2-adapter`` JSON config.

    Field names verified against ``ValkeyL2AdapterConfig`` in
    ``lmcache/v1/distributed/l2_adapters/valkey_l2_adapter.py`` and
    ``examples/kv_cache_reuse/remote_backends/valkey/README.md`` in the
    LMCache repo (lmcache==0.5.2). Unlike the legacy configs above, this is
    not an ``LMCACHE_CONFIG_FILE`` YAML, so it isn't validated through
    ``load_engine_config_with_overrides`` — instead ``validate_mp_config``
    round-trips it through LMCache's real ``ValkeyL2AdapterConfig.from_dict``.
    ``host`` is also validated separately up front (see
    ``parse_startup_nodes``) since this value is later embedded in a printed
    example shell command with no other escaping step.

    Raises:
        ValueError: If ``host`` isn't a valid comma-separated
            ``host:port[,host:port...]`` startup_nodes string.
    """
    validated_host = parse_startup_nodes(host)
    return {
        "type": "valkey",
        "cluster_mode": cluster_mode,
        "startup_nodes": validated_host,
        "num_workers": 16,
    }


def validate_legacy_config(yaml_text: str) -> None:
    """Round-trip a generated legacy config through LMCache's real config loader.

    Raises whatever ``load_engine_config_with_overrides`` raises if the
    config is invalid — this is the difference between "looks right" and
    "LMCache actually accepts it".
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        temp_path = f.name
    try:
        config = load_lmcache_config(temp_path)
        print(f"  Validated OK — remote_url={config.remote_url!r}, "
              f"remote_serde={config.remote_serde!r}, extra_config={config.extra_config!r}")
    finally:
        Path(temp_path).unlink(missing_ok=True)


def validate_mp_config(adapter: dict) -> None:
    """Round-trip a generated MP-mode adapter dict through LMCache's real
    ``ValkeyL2AdapterConfig.from_dict``.

    This is the MP-mode equivalent of ``validate_legacy_config`` — it isn't
    an ``LMCACHE_CONFIG_FILE`` YAML, so ``load_engine_config_with_overrides``
    doesn't apply, but LMCache ships a separate real parser
    (``lmcache.v1.distributed.l2_adapters.valkey_l2_adapter.ValkeyL2AdapterConfig.from_dict``)
    for exactly this JSON shape, and it's usable standalone on CPU with no
    GPU/engine bootstrap required. Raises whatever that real parser raises
    if the dict is invalid.
    """
    from lmcache.v1.distributed.l2_adapters.valkey_l2_adapter import ValkeyL2AdapterConfig

    config = ValkeyL2AdapterConfig.from_dict(adapter)
    print(f"  Validated OK — startup_nodes={config.startup_nodes!r}, "
          f"cluster_mode={config.cluster_mode!r}, num_workers={config.num_workers!r}")


async def monitor_cache_stats(host: str, port: int) -> None:
    """Query Valkey for cache-related metrics via a real GLIDE client."""
    print("\n--- Valkey Cache Metrics ---")
    client = await create_client(host, port)
    try:
        dbsize = await client.dbsize()
        print(f"Total keys (KV cache chunks stored): {dbsize}")

        stats = await client.custom_command(["INFO", "stats"])
        stats_text = stats.decode() if isinstance(stats, bytes) else str(stats)
        hits = misses = 0
        for line in stats_text.splitlines():
            if line.startswith("keyspace_hits:"):
                hits = int(line.split(":")[1])
            elif line.startswith("keyspace_misses:"):
                misses = int(line.split(":")[1])
        total = hits + misses
        if total > 0:
            print(f"Keyspace hit rate: {hits / total * 100:.1f}% ({hits}/{total})")
        else:
            print("No keyspace activity yet.")

        memory = await client.custom_command(["INFO", "memory"])
        memory_text = memory.decode() if isinstance(memory, bytes) else str(memory)
        for line in memory_text.splitlines():
            if line.startswith("used_memory_human:"):
                print(f"Memory usage: {line.split(':', 1)[1]}")
    finally:
        await client.close()


def main() -> None:
    """Generate, validate, and optionally monitor LMCache Valkey configs."""
    parser = argparse.ArgumentParser(
        description="LMCache + Valkey production configuration generator"
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "cluster", "serverless", "mp"],
        default="standalone",
        help="Deployment mode (default: standalone)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Valkey host:port. Defaults to VALKEY_HOST/VALKEY_PORT env vars "
        "(same as getting_started.py and kv_cache_sharing.py), or localhost:6379 if unset.",
    )
    parser.add_argument(
        "--cluster-mode",
        action="store_true",
        help="Set cluster_mode: true in the generated MP-mode --l2-adapter config (--mode mp only)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Query Valkey for cache metrics after generating the config",
    )
    args = parser.parse_args()

    if args.host is None:
        env_host, env_port = connection_settings()
        args.host = f"{env_host}:{env_port}"

    if args.mode == "mp":
        adapter = generate_mp_l2_adapter(args.host, cluster_mode=args.cluster_mode)
        print("Generated MP-mode --l2-adapter config (current recommended path):")
        print(json.dumps(adapter))
        print("Validating against LMCache's real ValkeyL2AdapterConfig.from_dict...")
        validate_mp_config(adapter)
        print("\nStart the LMCache server with:")
        print(f"  lmcache server --l1-size-gb 4 --eviction-policy LRU --chunk-size 256 "
              f"--port 6555 --l2-adapter '{json.dumps(adapter)}'")
    else:
        generators = {
            "standalone": generate_standalone_config,
            "cluster": generate_cluster_config,
            "serverless": generate_serverless_config,
        }
        config_text = generators[args.mode](args.host)
        print(f"Generated {args.mode} config (legacy in-process connector):\n")
        print(config_text)
        print("Validating against LMCache's real config loader...")
        validate_legacy_config(config_text)

    if args.monitor:
        addr, port = parse_host(args.host)
        asyncio.run(monitor_cache_stats(addr, int(port)))


if __name__ == "__main__":
    main()
