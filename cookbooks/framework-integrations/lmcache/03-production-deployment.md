# Production Deployment

> Cluster mode, TLS/ElastiCache Serverless, the current recommended MP-mode adapter, worker tuning, and cache-hit monitoring — every generated config round-tripped through LMCache's own real parsing code.

**Advanced** · Python · ~20 min

**Who is this for:** Python developers preparing to deploy LMCache with Valkey in production, who want configs that are verified to parse correctly before they reach a GPU host.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - KV Cache Sharing](02-kv-cache-sharing.md)
- A Valkey cluster (self-managed or ElastiCache) for the production configs below — a local standalone Valkey is enough to follow along
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

For production workloads, a single Valkey node is a bottleneck. Cluster mode distributes KV cache chunks across multiple shards.

### Configuration (Endpoint-Based)

For managed services like ElastiCache, connect via the configuration endpoint:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 10.0
remote_url: "valkey://my-cluster.abc123.clustercfg.us-east-1.cache.amazonaws.com:6379"
remote_serde: "cachegen"
pre_caching_hash_algorithm: sha256_cbor_64bit
extra_config:
  valkey_mode: "cluster"
  valkey_num_workers: 32
```

The GLIDE client auto-discovers cluster topology from the seed node — no need to list every shard.

### TLS / ElastiCache Serverless

ElastiCache Serverless requires TLS:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 10.0
remote_url: "valkey://my-serverless-cache.abc123.serverless.us-east-1.cache.amazonaws.com:6379"
remote_serde: "cachegen"
pre_caching_hash_algorithm: sha256_cbor_64bit
extra_config:
  valkey_mode: "cluster"
  tls_enable: true
  valkey_num_workers: 32
```

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
assert config.extra_config["tls_enable"] is True
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
  --l2-adapter '{"type": "valkey", "cluster_mode": true, "startup_nodes": "my-cluster.endpoint:6379", "num_workers": 16}'
```

Generate this exact config with the sample script:

```bash
python sample/production_deployment.py --mode mp --host my-cluster.endpoint:6379 --cluster-mode
```

`--l2-adapter` is a JSON object. Key fields:

- `startup_nodes`: `"host:port[,host:port...]"` seed nodes
- `cluster_mode`: `true` for `GlideClusterClient`, `false` (default) for standalone
- `tls_enable`: required for managed services like ElastiCache Serverless
- `num_workers`: size of the internal worker thread pool (the real I/O concurrency knob)

vLLM then connects to the LMCache server instead of using an in-process connector:

```bash
vllm serve meta-llama/Llama-3.1-70B-Instruct \
  --kv-transfer-config '{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both","kv_connector_extra_config":{"lmcache.mp.host":"tcp://localhost","lmcache.mp.port":6555}}'
```

> **Note:** MP-mode Valkey support is new — the adapter was added to LMCache only a few weeks
> before this cookbook was written. It's the direction the project is heading, but it has far less
> production track record than the in-process connector above. Evaluate accordingly.

## Performance Tuning

### Worker Count

`valkey_num_workers` (in-process) / `num_workers` (MP mode) controls how many parallel connections LMCache maintains to Valkey. Each worker is a thread with its own GLIDE client.

| Model Size | Tensor Parallelism | Recommended Workers |
| ------------ | ------------------- | --------------------- |
| 7-8B | TP=1 | 8-16 |
| 13B | TP=2 | 16-24 |
| 70B | TP=8 | 32-64 |

### Chunk Size

| Chunk Size | Trade-off |
| ----------- | ----------- |
| 128 | Finer granularity, more Valkey keys, higher overhead per chunk |
| 256 (default) | Good balance for most workloads |
| 512 | Fewer keys, lower overhead, but less prefix-sharing granularity |

### Serialization

| Format | Throughput | Compression | Use Case |
| -------- | ----------- | ------------- | ---------- |
| `naive` | Highest | None | Same-rack, low-latency network |
| `cachegen` | Moderate | Meaningfully reduced | Cross-AZ, bandwidth-constrained |

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

Estimate Valkey memory requirements from the model's attention architecture — this is dimensional
analysis from the transformer's shape (layers × KV heads × head dimension), not a benchmarked
number, so it holds regardless of hardware:

```text
Memory per token ≈ 2 × num_layers × num_kv_heads × head_dim × bytes_per_element
Memory per chunk = chunk_size × memory_per_token
```

The leading `2` accounts for storing both the K and V tensors; `bytes_per_element` is 2 for FP16/BF16
KV caches (the common case), 1 for FP8.

For example, for a model with 36 layers, 8 KV heads, and head_dim 128, at FP16:

- Per token: 2 × 36 × 8 × 128 × 2 bytes = 147,456 bytes ≈ 144 KB
- Per chunk (256-token `chunk_size`): 256 × 144 KB ≈ 36 MB

`cachegen` serialization reduces this further before it hits the wire (see
[Serialization](#serialization) above) — by how much depends on your KV data's compressibility, so
measure it against your own model and traffic rather than assuming a fixed ratio.

Plan Valkey capacity based on your expected unique prompt-prefix count × chunk size, then add
10-15% overhead for Valkey's own internal data structures (hash table entries, key metadata).

## Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| `ConnectionError` on startup | Valkey unreachable | Check `remote_url`/`startup_nodes`, security groups, TLS settings |
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
| `tls_enable` | both | `false` | Enable TLS (required for ElastiCache Serverless) |
| `valkey_username` / `valkey_password` (in-process); `username` / `password` (MP) | both | `""` | Authentication credentials |
| `valkey_database` (in-process only) | in-process | None | Database ID (standalone mode only) |
| `request_timeout` | in-process | 5.0 | GLIDE request timeout in seconds |
| `connection_timeout` | in-process | 10.0 | Initial connection timeout in seconds |

---

[← 02 - KV Cache Sharing](02-kv-cache-sharing.md)
