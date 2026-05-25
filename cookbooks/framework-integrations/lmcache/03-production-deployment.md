# Production Deployment

> Deploy LMCache with Valkey in production: cluster mode for horizontal scaling, TLS for security, ElastiCache Serverless for managed infrastructure, and tuning for maximum throughput.

**Advanced** · Python · ~20 min

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - KV Cache Sharing](02-kv-cache-sharing.md)
- A Valkey cluster (self-managed or ElastiCache)
- Familiarity with vLLM deployment

## Cluster Mode

For production workloads, a single Valkey node is a bottleneck. Cluster mode distributes KV cache chunks across multiple shards, scaling both memory capacity and throughput linearly.

### Configuration (Endpoint-Based)

For managed services like ElastiCache, connect via the configuration endpoint:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://my-cluster.abc123.clustercfg.us-east-1.cache.amazonaws.com:6379"
remote_serde: "naive"
extra_config:
  valkey_mode: "cluster"
  valkey_num_workers: 32
```

The GLIDE client auto-discovers cluster topology from the seed node — no need to list every shard.

### Configuration (Direct Nodes)

For self-managed clusters where nodes are addressed by IP:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://172.0.0.1:7001, 172.0.0.2:7002, 172.0.0.3:7003"
remote_serde: "naive"
extra_config:
  valkey_mode: "cluster"
  valkey_num_workers: 32
```

## TLS / ElastiCache Serverless

ElastiCache Serverless requires TLS. Enable it with `tls_enable`:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://my-serverless-cache.abc123.serverless.us-east-1.cache.amazonaws.com:6379"
remote_serde: "naive"
extra_config:
  valkey_mode: "cluster"
  tls_enable: true
  valkey_num_workers: 32
```

For authenticated clusters, add credentials:

```yaml
extra_config:
  valkey_mode: "cluster"
  tls_enable: true
  valkey_username: "${VALKEY_USERNAME}"
  valkey_password: "${VALKEY_PASSWORD}"
  valkey_num_workers: 32
```

> **Security:** Never hardcode credentials in config files. Use environment variables or a secrets manager. LMCache reads these values at startup.

## Performance Tuning

### Worker Count

The `valkey_num_workers` setting controls how many parallel connections LMCache maintains to Valkey. Each worker is a thread with its own GLIDE client, enabling true parallel I/O.

| Model Size | Tensor Parallelism | Recommended Workers |
|------------|-------------------|---------------------|
| 7-8B | TP=1 | 8-16 |
| 13B | TP=2 | 16-24 |
| 70B | TP=8 | 32-64 |

More workers = higher throughput for concurrent store/load operations, at the cost of more Valkey connections.

### Chunk Size

The `chunk_size` determines how many tokens are grouped into a single KV cache chunk:

| Chunk Size | Trade-off |
|-----------|-----------|
| 128 | Finer granularity, more Valkey keys, higher overhead per chunk |
| 256 (default) | Good balance for most workloads |
| 512 | Fewer keys, lower overhead, but less prefix-sharing granularity |

Smaller chunks improve cache hit rates for partially-overlapping prompts but increase the number of Valkey operations.

### Serialization

| Format | Throughput | Compression | Use Case |
|--------|-----------|-------------|----------|
| `naive` | Highest | None | Same-rack, low-latency network |
| `cachegen` | Moderate | ~4× reduction | Cross-AZ, bandwidth-constrained |

For production with network constraints, `cachegen` reduces Valkey memory usage and network transfer at the cost of CPU cycles for compression/decompression.

### Hash Algorithm for TP > 1

When using tensor parallelism greater than 1, enable consistent hashing:

```yaml
pre_caching_hash_algorithm: sha256_cbor_64bit
```

This ensures all TP ranks produce the same chunk keys for the same prompt prefix.

## Monitoring Cache Hits

### Valkey-Side Metrics

Monitor cache effectiveness using Valkey's built-in stats:

```bash
valkey-cli INFO stats | grep keyspace
# keyspace_hits:142857
# keyspace_misses:3201
```

Calculate hit rate:

```bash
valkey-cli INFO stats | awk -F: '/keyspace_hits/{hits=$2} /keyspace_misses/{misses=$2} END{printf "Hit rate: %.1f%%\n", hits/(hits+misses)*100}'
```

### Memory Usage

Track how much Valkey memory is consumed by KV caches:

```bash
valkey-cli INFO memory | grep used_memory_human
# used_memory_human:2.34G
```

### LMCache Logs

LMCache logs cache hit/miss information per request:

```
# Cache hit — tokens loaded from Valkey
LMCache INFO: Reqid: ..., Total tokens 512, LMCache hit tokens: 480, need to load: 8

# Cache miss — tokens computed and stored
LMCache INFO: Storing KV cache for 512 out of 512 tokens for request ...
```

Monitor the ratio of "hit tokens" to "Total tokens" to gauge effectiveness.

## Capacity Planning

Estimate Valkey memory requirements:

```
Memory per token ≈ 2 × num_layers × hidden_dim × 2 bytes (FP16)
Memory per chunk = chunk_size × memory_per_token
```

For Qwen3-8B (32 layers, hidden_dim 4096):
- Per token: 2 × 32 × 4096 × 2 = 512 KB
- Per chunk (256 tokens): ~128 MB

With `cachegen` compression (~4× reduction): ~32 MB per chunk.

Plan Valkey capacity based on your expected unique prompt prefix count × chunk size.

## Full Production Configuration

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 10.0
remote_url: "valkey://my-cluster.abc123.clustercfg.us-east-1.cache.amazonaws.com:6379"
remote_serde: "cachegen"
pre_caching_hash_algorithm: sha256_cbor_64bit
extra_config:
  valkey_mode: "cluster"
  tls_enable: true
  valkey_username: "${VALKEY_USERNAME}"
  valkey_password: "${VALKEY_PASSWORD}"
  valkey_num_workers: 32
  request_timeout: 5.0
  connection_timeout: 10.0
```

Launch vLLM:

```bash
PYTHONHASHSEED=0 \
LMCACHE_CONFIG_FILE=lmcache_config.yaml \
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 8 \
    --gpu-memory-utilization 0.9 \
    --kv-transfer-config \
    '{"kv_connector":"LMCacheConnectorV1", "kv_role":"kv_both"}'
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConnectionError` on startup | Valkey unreachable | Check `remote_url`, security groups, TLS settings |
| 0% cache hits across instances | Different `PYTHONHASHSEED` | Export `PYTHONHASHSEED=0` on all instances |
| Low hit rate with TP > 1 | Missing hash algorithm | Add `pre_caching_hash_algorithm: sha256_cbor_64bit` |
| High latency on cache load | Network bandwidth saturated | Switch to `cachegen` serde, increase `valkey_num_workers` |
| Valkey OOM | Too many cached chunks | Increase cluster size or set Valkey `maxmemory` with `allkeys-lru` eviction |
| `TimeoutError` on large models | Default timeout too short | Increase `request_timeout` in `extra_config` |

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `valkey_num_workers` | 8 | Parallel GLIDE client threads |
| `valkey_mode` | `standalone` | `standalone` or `cluster` |
| `tls_enable` | false | Enable TLS (required for ElastiCache Serverless) |
| `valkey_username` | `""` | Authentication username |
| `valkey_password` | `""` | Authentication password |
| `valkey_database` | None | Database ID (standalone only) |
| `request_timeout` | 5.0 | GLIDE request timeout in seconds |
| `connection_timeout` | 10.0 | Initial connection timeout in seconds |

---

[← 02 - KV Cache Sharing](02-kv-cache-sharing.md)
