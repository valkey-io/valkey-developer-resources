# KV-Aware Routing with Valkey

> Leverage Dynamo's KV router to direct requests toward workers with warm Valkey-backed caches, minimizing redundant prefill across the cluster.

**Intermediate** · Python · ~20 min

Dynamo's KV router doesn't just load-balance — it tracks which KV cache blocks exist on which workers and routes requests to maximize cache hits. When Valkey backs the L2 layer, the router considers both local (L1/GPU) and remote (Valkey) cache state to make optimal placement decisions.

## How KV-Aware Routing Works

```
Request: "Explain transformers..."
  │
  ▼
┌──────────────────────────────────────────────┐
│              Dynamo KV Router                 │
│                                              │
│  1. Hash prompt tokens                       │
│  2. Query index: which workers have overlap? │
│  3. Score: prefill_cost vs decode_cost       │
│  4. Route to worker with best cache overlap  │
└──────────────────────────────────────────────┘
  │
  ▼ routed to Worker with highest overlap
┌─────────────┐
│  Worker 1   │ → L1 hit (local CPU) or L2 hit (Valkey)
│  +LMCache   │ → skip prefill, decode immediately
└─────────────┘
```

The router evaluates:
- **Decode cost**: active blocks already on the target worker
- **Prefill cost**: new blocks that must be computed
- **KV cache overlap**: how many tokens are already cached (locally or in Valkey)

## Step 1: Enable the KV Router

Update your Dynamo graph to use the KV-aware router:

```python
from dynamo.sdk import service, depends, DynamoConfig
from dynamo.routers import KvRouter

FrontendConfig = DynamoConfig(
    name="frontend",
    port=8000,
    router=KvRouter(
        routing_strategy="prefix_aware",
        cache_aware=True,
    ),
)
```

The `prefix_aware` strategy uses token-level prefix matching to determine overlap.

## Step 2: Configure Router Cache Tracking

The router needs to know what's cached. Dynamo's Flash Indexer maintains a concurrent global index of cached KV blocks across all workers:

```python
from dynamo.routers import KvRouter, IndexConfig

router = KvRouter(
    routing_strategy="prefix_aware",
    cache_aware=True,
    index_config=IndexConfig(
        update_interval_ms=100,   # how often workers report cache state
        stale_threshold_ms=5000,  # consider entries stale after 5s
    ),
)
```

Workers periodically report which token sequences they have cached (in L1 or loaded from Valkey L2). The router uses this to make routing decisions.

## Step 3: Worker Configuration for Cache Reporting

Each worker must report its cache contents to the index. This happens automatically when LMCache is configured, but you can tune reporting:

```bash
# Add to lmcache.env
LMCACHE_CHUNK_SIZE=256
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=5.0
LMCACHE_REMOTE_URL=valkey://valkey:6379
LMCACHE_REMOTE_SERDE=naive

# Dynamo-specific: enable cache state reporting
DYNAMO_REPORT_CACHE_STATE=true
DYNAMO_REPORT_INTERVAL_MS=100
```

## Step 4: Observe Routing Decisions

Send multiple requests with shared prefixes:

```bash
# Request 1: full prompt
curl -s http://localhost:8000/v1/completions -d '{
  "model": "Qwen/Qwen3-8B",
  "prompt": "You are a helpful assistant. The user asks: What is attention?",
  "max_tokens": 50
}'

# Request 2: same system prompt, different user query
curl -s http://localhost:8000/v1/completions -d '{
  "model": "Qwen/Qwen3-8B",
  "prompt": "You are a helpful assistant. The user asks: What is backpropagation?",
  "max_tokens": 50
}'
```

Both share the prefix "You are a helpful assistant. The user asks: ". The router will:
1. Route Request 1 to any worker (cold)
2. Route Request 2 to the **same worker** (or one that loaded the prefix from Valkey) because it has the cached prefix

## Step 5: Monitor Routing Metrics

Dynamo exposes Prometheus metrics for routing decisions:

```bash
curl -s http://localhost:8000/metrics | grep kv_router
```

Key metrics:
- `dynamo_kv_router_cache_hit_ratio` — fraction of requests routed to workers with cache overlap
- `dynamo_kv_router_prefill_tokens_saved` — total tokens skipped due to cache hits
- `dynamo_kv_router_routing_latency_ms` — time to make routing decision

## The WORM Access Pattern

Agentic inference exhibits a Write-Once-Read-Many (WORM) pattern:
- System prompts and growing conversation prefixes are computed once
- Subsequent turns reuse the cached prefix (11.7× read/write ratio in NVIDIA's benchmarks)

With Valkey as L2, this cached prefix is available cluster-wide. The KV router ensures requests land on workers that already have the prefix warm — whether in L1 (local CPU) or loadable from L2 (Valkey) with minimal latency.

## Routing Strategy Comparison

| Strategy | Best For | Cache Utilization |
|----------|----------|-------------------|
| `round_robin` | Even load distribution | Low (ignores cache) |
| `least_loaded` | Prevent hotspots | Low (ignores cache) |
| `prefix_aware` | Multi-turn / shared prefixes | High |
| `prefix_aware` + `cache_aware` | Full cluster cache optimization | Highest |

Always use `prefix_aware` + `cache_aware=True` when Valkey is configured as L2 — it's the combination that maximizes the benefit of shared remote caching.

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
