# Production Deployment

> Cluster mode, generic TLS configuration, the current recommended MP-mode adapter, and Valkey cache monitoring — every generated config is round-tripped through LMCache's own real parsing code.

**Advanced** · Python · ~20 min

**Who is this for:** Python developers preparing to deploy LMCache with Valkey in production, who want configs that are verified to parse correctly before they reach a GPU host.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - KV Cache Sharing](02-kv-cache-sharing.md)
- A local Valkey instance for the production configuration examples
- Familiarity with vLLM deployment

## Two Connector Modes

LMCache ships two ways to talk to Valkey:

| Mode | Config surface | Status |
| ---- | --------------- | ------ |
| In-process connector (`remote_url: "valkey://..."`) | `LMCACHE_CONFIG_FILE` YAML | **Deprecated** as of LMCache's docs — still functional, in wide use today |
| MP-mode adapter (`--l2-adapter '{"type": "valkey", ...}'`) | JSON CLI flag to `lmcache server` | Current recommended path — newer, less battle-tested |

LMCache's own documentation states: *"This page documents the behavior of LMCache's in-process
mode (deprecated). Please consider using LMCache MP mode for better feature support and
performance."* Both are covered below — the in-process connector because it's what most existing
LMCache+Valkey deployments run today, and MP mode because it's the direction LMCache is moving.

## In-Process Connector: Cluster Mode

Cluster mode distributes KV cache chunks across multiple shards.

### Configuration (Endpoint-Based)

Use a local endpoint in the configuration example:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 10.0
remote_url: "valkey://localhost:6379"
remote_serde: "cachegen"
pre_caching_hash_algorithm: sha256_cbor_64bit
extra_config:
  valkey_mode: "cluster"
  valkey_num_workers: 32
```

The GLIDE client auto-discovers cluster topology from the seed node — no need to list every shard.

For a TLS-enabled cluster, add `tls_enable: true` under `extra_config`. Users of hosted Valkey
services should consult their provider's documentation for service-specific TLS and authentication
configuration.

> **Security:** Never hardcode credentials in config files checked into source control. Prefer
> injecting `valkey_username`/`valkey_password` at deploy time via templating, secrets managers, or
> mounting the config file from a secure store.

### Validating a Generated Config

Every legacy (`LMCACHE_CONFIG_FILE`) config in this cookbook is validated by loading it through
LMCache's real config parser before you ever hand it to a GPU host:

```python
from lmcache.v1.config import load_engine_config_with_overrides

config = load_engine_config_with_overrides(config_file_path="lmcache_config.yaml")
assert config.extra_config["valkey_mode"] == "cluster"
```

This catches typos and malformed YAML before deployment — `load_engine_config_with_overrides` is
the same function LMCache calls internally, so if it raises here, it would raise on the GPU host
too.

The MP-mode `--l2-adapter` JSON isn't an `LMCACHE_CONFIG_FILE`, so it doesn't go through
`load_engine_config_with_overrides` — but LMCache ships a separate real parser for exactly this
shape, `ValkeyL2AdapterConfig.from_dict`, and `sample/production_deployment.py` validates every
generated MP config against it the same way:

```python
from lmcache.v1.distributed.l2_adapters.valkey_l2_adapter import ValkeyL2AdapterConfig

config = ValkeyL2AdapterConfig.from_dict({"type": "valkey", "startup_nodes": "127.0.0.1:6379"})
```

## MP Mode: The Recommended Path

MP mode runs LMCache as a standalone server process that vLLM connects to over ZMQ, with Valkey as its L2 adapter:

```bash
lmcache server --l1-size-gb 4 --eviction-policy LRU --chunk-size 256 --port 6555 \
  --l2-adapter '{"type": "valkey", "cluster_mode": true, "startup_nodes": "localhost:6379", "num_workers": 16}'
```

Generate this exact config with the sample script:

```bash
python sample/production_deployment.py --mode mp --host localhost:6379 --cluster-mode
```

`--l2-adapter` is a JSON object. Key fields:

- `startup_nodes`: `"host:port[,host:port...]"` seed nodes
- `cluster_mode`: `true` for `GlideClusterClient`, `false` (default) for standalone
- `num_workers`: size of the internal worker thread pool (the real I/O concurrency knob)

vLLM then connects to the LMCache server instead of using an in-process connector:

```bash
vllm serve meta-llama/Llama-3.1-70B-Instruct \
  --kv-transfer-config '{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both","kv_connector_extra_config":{"lmcache.mp.host":"tcp://localhost","lmcache.mp.port":6555}}'
```

> **Note:** MP-mode Valkey support is new — the adapter was added to LMCache only a few weeks
> before this cookbook was written. It's the direction the project is heading, but it has far less
> production track record than the in-process connector above. Evaluate accordingly.

## Valkey Integration Settings

`valkey_num_workers` (in-process) / `num_workers` (MP mode) controls the number of parallel
Valkey connections and therefore the integration's I/O concurrency. See
[LMCache's documentation](https://docs.lmcache.ai) for LMCache model-sizing and tuning guidance.

### Hash Algorithm for TP > 1

When using tensor parallelism greater than 1, enable consistent hashing so all TP ranks produce the same chunk keys:

```yaml
pre_caching_hash_algorithm: sha256_cbor_64bit
```

## Monitoring Cache Hits

### Valkey-Side Metrics

```bash
valkey-cli INFO stats | grep keyspace
# keyspace_hits:142857
# keyspace_misses:3201
```

```bash
valkey-cli INFO stats | awk -F: '/keyspace_hits/{hits=$2} /keyspace_misses/{misses=$2} END{printf "Hit rate: %.1f%%\n", hits/(hits+misses)*100}'
```

### Memory Usage

```bash
valkey-cli INFO memory | grep used_memory_human
```

### From Python (used by this cookbook's sample)

```bash
python sample/production_deployment.py --mode standalone --monitor
```

This queries the same metrics via a GLIDE client instead of shelling out to `valkey-cli` — see `sample/production_deployment.py`'s `monitor_cache_stats`.

## Capacity Planning

Estimate Valkey memory needs from the number of unique prompt prefixes expected to be cached. Each
LMCache chunk represents `chunk_size` tokens of KV data. See
[LMCache's documentation](https://docs.lmcache.ai) for model-specific KV cache size estimates.

Set `maxmemory` to a limit that leaves headroom for Valkey overhead. For an evictable LMCache
remote cache, use `allkeys-lru` so Valkey removes least-recently-used cache entries under memory
pressure:

```conf
maxmemory <memory-limit>
maxmemory-policy allkeys-lru
```

Monitor `INFO MEMORY` and `INFO STATS`, including `used_memory`, `used_memory_overhead`, and
`evicted_keys`, then tune `maxmemory` from observed peak usage and eviction activity. See Valkey's
[key eviction documentation](https://valkey.io/topics/lru-cache/).

## Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| `ConnectionError` on startup | Valkey unreachable | Check `remote_url`/`startup_nodes`, network access, and TLS settings |
| 0% cache hits across instances | Different `PYTHONHASHSEED` in a real deployment | Export `PYTHONHASHSEED=0` on all vLLM instances |
| Low hit rate with TP > 1 | Missing hash algorithm | Add `pre_caching_hash_algorithm: sha256_cbor_64bit` |
| High latency on cache load | Network bandwidth saturated | Switch to `cachegen` serde, increase worker count |
| Valkey OOM | Too many cached chunks | Increase cluster size or set Valkey `maxmemory` with `allkeys-lru` eviction |
| Config fails to load | Invalid YAML or unknown key | Run it through `load_engine_config_with_overrides` locally first — see above |

## Configuration Reference

| Key | Mode | Default | Description |
| ----- | ------ | --------- | -------------- |
| `valkey_num_workers` (in-process) / `num_workers` (MP) | both | 8 | Parallel GLIDE client threads |
| `valkey_mode` (in-process) / `cluster_mode` (MP) | both | `standalone` / `false` | Standalone or cluster topology |
| `tls_enable` | in-process cluster | `false` | Enable TLS when the Valkey endpoint requires it |
| `valkey_username` / `valkey_password` (in-process); `username` / `password` (MP) | both | `""` | Authentication credentials |
| `valkey_database` (in-process only) | in-process | None | Database ID (standalone mode only) |
| `request_timeout` | in-process | 5.0 | GLIDE request timeout in seconds |
| `connection_timeout` | in-process | 10.0 | Initial connection timeout in seconds |

---

[← 02 - KV Cache Sharing](02-kv-cache-sharing.md) | [README →](./README.md)
