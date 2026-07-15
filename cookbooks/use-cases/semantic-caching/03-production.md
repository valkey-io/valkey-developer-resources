# Production Patterns

> Similarity threshold tuning, cache hit rate monitoring, eviction strategies, TTL management, and cost tracking for production semantic caches.

**Advanced** · Python · ~25 min

**Who is this for:** Platform engineers and ML ops teams deploying semantic caches in production who need to tune similarity thresholds, monitor hit rates, manage memory, and implement cache invalidation.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Completed [02 - Multi-Turn Caching](02-multiturn-caching.md)
- Valkey running with the search module

> **Note:** This cookbook builds on functions defined in 01 (`semantic_cache_lookup`, `cache_response`,
> `get_embedding`). Run the code from 01 first in the same Python session, or copy those functions
> into your script.

## Step 1: Similarity Threshold Tuning

The threshold controls the trade-off between hit rate and answer quality:

| Threshold (COSINE) | Hit Rate | Quality Risk | Best For |
|---|---|---|---|
| `0.05` (very strict) | Low (~20%) | Very low | Medical, legal, financial |
| `0.15` (balanced) | Medium (~50%) | Low | General chatbots |
| `0.30` (relaxed) | High (~70%) | Medium | FAQ bots, support |
| `0.50` (very relaxed) | Very high (~85%) | High — stale answers | Not recommended |

> **Note:** These hit rate percentages are approximate and depend heavily on query diversity in your workload. Start at 0.15 and tune using the evaluation function below.

```python
def evaluate_threshold(test_pairs: list, threshold: float):
    """Evaluate cache quality at a given threshold.

    test_pairs: list of (query, expected_should_match_cache: bool)
    """
    hits = 0
    false_positives = 0

    for query, expected_similar in test_pairs:
        result = semantic_cache_lookup(query)
        if result["hit"] and result["score"] < threshold:
            hits += 1
            if not expected_similar:
                false_positives += 1

    total = len(test_pairs)
    hit_rate = hits / total
    fp_rate = false_positives / max(1, hits)
    print(f"Threshold {threshold}: hit_rate={hit_rate:.1%}, fp_rate={fp_rate:.1%}")
```

## Step 2: Cache Hit Rate Monitoring

```python
import valkey
from datetime import datetime

client = valkey.Valkey(host="localhost", port=6379)


def record_cache_event(event_type: str):
    """Track cache hits and misses using atomic counters."""
    # Lifetime counter
    client.incr(f"cache:metrics:{event_type}")

    # Hourly counter for time-series analysis
    hour_key = datetime.now().strftime("%Y%m%d%H")
    counter_key = f"cache:metrics:{event_type}:{hour_key}"
    client.incr(counter_key)
    client.expire(counter_key, 86400 * 7)  # Keep 7 days


def get_cache_stats() -> dict:
    """Get current cache performance metrics."""
    hits = int(client.get("cache:metrics:hit") or 0)
    misses = int(client.get("cache:metrics:miss") or 0)
    total = hits + misses
    hit_rate = hits / total if total > 0 else 0

    return {
        "total_requests": total,
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hit_rate, 3),
    }


# Integration with ask_with_cache:
# if cache_hit: record_cache_event("hit")
# else: record_cache_event("miss")
```

## Step 3: TTL Strategies

```python
# Strategy 1: Fixed TTL — simple, predictable
client.expire(cache_key, 3600)  # 1 hour

# Strategy 2: Category-based TTL
TTL_MAP = {
    "factual": 86400,      # 24h — facts don't change fast
    "opinion": 3600,       # 1h — opinions evolve
    "real-time": 300,      # 5 min — stock prices, weather
    "conversation": 1800,  # 30 min — chat context
}

# Strategy 3: Sliding TTL — reset on each hit
def cache_hit_with_refresh(cache_key: str, ttl: int = 3600) -> str:
    """On cache hit, refresh the TTL to keep popular entries alive."""
    response = client.hget(cache_key, "response")
    client.expire(cache_key, ttl)  # Reset TTL
    return response
```

## Step 4: Memory Management

```python
# Set maxmemory policy for cache eviction.
# In valkey.conf or via CONFIG SET:
#   maxmemory 1gb
#   maxmemory-policy allkeys-lru
#
# LRU = Least Recently Used — evicts least-accessed cache entries first.
# This is ideal for semantic caching where popular queries should stay.

# Check memory usage
info = client.info("memory")
used_mb = info["used_memory"] / (1024 * 1024)
print(f"Memory: {used_mb:.1f} MB")

# Estimate cache capacity (nomic-embed-text, 768 dims):
# Each entry: ~3KB (768 dims * 4 bytes + prompt + response text)
# 1 GB ≈ ~350,000 cached entries
```

## Step 5: Cache Invalidation

```python
def invalidate_by_topic(topic_keyword: str):
    """Remove cached entries matching a topic (e.g., after a data update)."""
    results = client.execute_command(
        "FT.SEARCH", "cache_idx",
        f"@prompt:{{{topic_keyword}}}",
        "NOCONTENT",  # Only return keys, not fields
        "LIMIT", "0", "1000",
    )

    if results[0] > 0:
        keys = results[1:]
        for key in keys:
            k = key.decode() if isinstance(key, bytes) else key
            client.delete(k)
        print(f"Invalidated {len(keys)} cached entries for '{topic_keyword}'")


# Example: product info changed, invalidate related cache
invalidate_by_topic("pricing")
```

## Production Checklist

| Area | Recommendation |
|------|---------------|
| Threshold | Start at 0.15 (COSINE), tune with A/B testing |
| TTL | 1h for general, 24h for facts, 5min for real-time |
| Monitoring | Track hit rate, latency, cost savings hourly |
| Memory | Set `maxmemory-policy allkeys-lru` |
| Invalidation | Use TEXT search to find and delete stale entries |
| Isolation | TAG filters for multi-tenant deployments |
| Embeddings | Use `nomic-embed-text` (fast, local, 768 dims) or cloud embeddings |
| Index | HNSW with COSINE distance metric |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `maxmemory` | ✓ | — | Maximum memory Valkey can use before eviction |
| `maxmemory-policy` | ✓ | `noeviction` | Set to `allkeys-lru` for cache workloads |
| `SIMILARITY_THRESHOLD` | ✓ | `0.15` | COSINE distance cutoff — tune per workload |
| `CACHE_TTL` | — | `3600` | Default TTL in seconds |

---

[← 02 - Multi-Turn Caching](02-multiturn-caching.md)
