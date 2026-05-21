# LLM Response Caching

**Intermediate** · Python · ~20 min

## What You'll Build

A caching layer that stores LLM responses in Valkey, reducing repeat-query latency from seconds to sub-millisecond and cutting inference costs. DB-GPT's `ValkeyCacheStorage` handles serialization, TTL, and both sync/async operations.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running (plain `valkey/valkey:latest` is sufficient — no search module needed for caching)
- DB-GPT installed with cache support: `pip install "dbgpt-ext[cache_valkey]"`

## Step 1: Understand the Cache Architecture

DB-GPT's cache system has a layered design:

```
┌─────────────────────────────────┐
│       LLMCacheClient            │  ← Application layer (key generation)
├─────────────────────────────────┤
│       CacheManager              │  ← Routing + policies
├─────────────────────────────────┤
│       CacheStorage (ABC)        │  ← Storage interface
├──────────┬──────────┬───────────┤
│ Memory   │  Disk    │  Valkey   │  ← Implementations
└──────────┴──────────┴───────────┘
```

`ValkeyCacheStorage` implements the `CacheStorage` interface:
- `get(key)` → retrieve a cached response
- `set(key, value)` → store a response with optional TTL
- `aget(key)` / `aset(key, value)` → async variants
- `exists(key)` → check cache hit without deserializing

## Step 2: Basic Cache Usage

```python
"""Basic ValkeyCacheStorage usage."""
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

# Create the cache with 1-hour TTL
cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,       # Entries expire after 1 hour
    key_prefix="dbgpt_cache:",  # Namespace for cache keys
)

# Verify connection
print(f"Cache connected: {cache.client is not None}")
```

## Step 3: Cache LLM Responses

```python
"""Store and retrieve LLM responses."""
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.cache.llm_cache import LLMCacheKey, LLMCacheValue
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


# Initialize cache
cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,
)

# Create a cache key from the LLM request parameters
# DB-GPT's LLMCacheClient builds these automatically in production
cache_key = LLMCacheKey(
    prompt="What is Valkey?",
    model_name="gpt-4",
    temperature=0.7,
)

# Create a cache value wrapping the model output
cache_value = LLMCacheValue(
    output=ModelOutput(
        error_code=0,
        text="Valkey is a high-performance, open-source in-memory data store "
             "that originated as a fork of Redis. It supports data structures "
             "like strings, hashes, lists, sets, and sorted sets, along with "
             "vector search capabilities via the valkey-search module.",
    )
)

# Both key and value need a serializer for the cache to serialize them
import json
from dbgpt.core.interface.serialization import Serializer


class JsonSerializer(Serializer):
    def serialize(self, obj):
        return json.dumps(obj.to_dict()).encode()

    def deserialize(self, data, cls):
        return cls(**json.loads(data))


cache_key.set_serializer(JsonSerializer())
cache_value.set_serializer(JsonSerializer())

# Store in cache
cache.set(cache_key, cache_value)
print("Cached LLM response")

# Retrieve from cache (sub-millisecond!)
result = cache.get(cache_key)
if result:
    print(f"Cache HIT: {result.value.get_value()}")
else:
    print("Cache MISS")

# Clean up
cache.close()
```

## Step 4: Async Cache Operations

`ValkeyCacheStorage` supports native async for use in DB-GPT's async pipelines:

```python
"""Async cache operations — reuses JsonSerializer from Step 3."""
import asyncio
import time
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.cache.llm_cache import LLMCacheKey, LLMCacheValue
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


async def demo_async_cache():
    cache = ValkeyCacheStorage(
        host="localhost",
        port=6379,
        ttl_seconds=1800,  # 30 minutes
    )

    key = LLMCacheKey(prompt="Explain HNSW indexing", model_name="claude-3")
    key.set_serializer(JsonSerializer())

    value = LLMCacheValue(
        output=ModelOutput(error_code=0, text="HNSW (Hierarchical Navigable Small World) is...")
    )
    value.set_serializer(JsonSerializer())

    # Async set
    start = time.perf_counter()
    await cache.aset(key, value)
    write_ms = (time.perf_counter() - start) * 1000
    print(f"Async write: {write_ms:.2f}ms")

    # Async get
    start = time.perf_counter()
    result = await cache.aget(key)
    read_ms = (time.perf_counter() - start) * 1000
    print(f"Async read:  {read_ms:.2f}ms")

    cache.close()


asyncio.run(demo_async_cache())
```

## Step 5: Benchmark Cache vs No-Cache

```python
"""Compare latency: cached vs uncached LLM calls.
Uses JsonSerializer from Step 3.
"""
import time
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.cache.llm_cache import LLMCacheKey, LLMCacheValue
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


cache = ValkeyCacheStorage(host="localhost", port=6379, ttl_seconds=3600)

# Store 100 cached responses
for i in range(100):
    key = LLMCacheKey(prompt=f"Question {i}", model_name="gpt-4")
    key.set_serializer(JsonSerializer())
    value = LLMCacheValue(output=ModelOutput(error_code=0, text=f"Answer {i}" * 50))
    value.set_serializer(JsonSerializer())
    cache.set(key, value)

# Benchmark cache reads
latencies = []
for i in range(100):
    key = LLMCacheKey(prompt=f"Question {i}", model_name="gpt-4")
    key.set_serializer(JsonSerializer())
    start = time.perf_counter()
    result = cache.get(key)
    elapsed = (time.perf_counter() - start) * 1000
    latencies.append(elapsed)
    assert result is not None

avg_ms = sum(latencies) / len(latencies)
p99_ms = sorted(latencies)[98]

print(f"Cache read latency (100 queries):")
print(f"  Average: {avg_ms:.3f}ms")
print(f"  P99:     {p99_ms:.3f}ms")
print(f"  vs typical LLM call: ~2000-5000ms")
print(f"  Speedup: ~{2000/avg_ms:.0f}x")

cache.close()
```

Expected output:
```
Cache read latency (100 queries):
  Average: 0.50ms
  P99:     0.75ms
  vs typical LLM call: ~2000-5000ms
  Speedup: ~4000x
```

## Step 6: TTL and Eviction Strategies

```python
"""Configure TTL for different cache tiers."""
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

# Short-lived cache for fast-changing data (e.g., real-time queries)
hot_cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=300,            # 5 minutes
    key_prefix="dbgpt_hot:",
)

# Long-lived cache for stable responses (e.g., documentation queries)
cold_cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=86400,          # 24 hours
    key_prefix="dbgpt_cold:",
)

# No-TTL cache for permanent entries (manual invalidation only)
permanent_cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=None,           # Never expires
    key_prefix="dbgpt_perm:",
)
```

## Step 7: Using with DB-GPT's Cache Manager

In production, configure via DB-GPT's cache manager:

```python
"""Integration with DB-GPT's cache management system."""
from dbgpt.storage.cache.manager import initialize_cache
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


# Option 1: Direct initialization
cache_storage = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,
)

# Option 2: Via DB-GPT's cache manager (reads from config)
# This is how DB-GPT initializes caching internally when storage_type="valkey"
# cache_manager = initialize_cache(storage_type="valkey")
```

## Step 8: Context Manager Pattern

Use context managers for clean resource management:

```python
"""Context manager for automatic cleanup.
Uses JsonSerializer from Step 3.
"""
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.cache.llm_cache import LLMCacheKey, LLMCacheValue
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


# Sync context manager
with ValkeyCacheStorage(host="localhost", port=6379, ttl_seconds=3600) as cache:
    key = LLMCacheKey(prompt="Hello", model_name="gpt-4")
    key.set_serializer(JsonSerializer())

    value = LLMCacheValue(output=ModelOutput(error_code=0, text="Hi there!"))
    value.set_serializer(JsonSerializer())

    cache.set(key, value)

    result = cache.get(key)
    print(f"Got: {result.value.get_value()}")
# Connection automatically closed here
```

## How It Works Under the Hood

| Operation | Valkey Command | Typical Latency |
|-----------|---------------|-----------------|
| Cache write | `SET dbgpt_cache:<hash> <serialized_item>` | ~0.1ms |
| Cache write + TTL | `SET dbgpt_cache:<hash> <serialized_item> EX 3600` | ~0.1ms |
| Cache read (hit) | `GET dbgpt_cache:<hash>` | ~0.1ms |
| Cache read (miss) | `GET dbgpt_cache:<hash>` → nil | ~0.05ms |
| Existence check | `EXISTS dbgpt_cache:<hash>` | ~0.05ms |

### Key Generation

Cache keys are hashed from the request parameters:

```python
# CacheKey hashes the data dict to produce a deterministic key
key = CacheKey(data={"prompt": "What is X?", "model": "gpt-4", "temperature": 0.7})
# → dbgpt_cache:a3f2b1c9d8e7...  (hex of hash bytes)
```

This means identical prompts with the same model and parameters always hit the same cache entry.

## Cost Savings Estimate

| Scenario | Without Cache | With Valkey Cache (80% hit rate) |
|----------|--------------|----------------------------------|
| 10,000 queries/day | $30-50/day (GPT-4) | $6-10/day |
| Average latency | 2-5 seconds | ~0.1ms (hits) / 2-5s (misses) |
| P99 latency | 8-12 seconds | ~3 seconds |

## Comparison with Other Cache Backends

| Feature | Memory | Disk | Valkey |
|---------|--------|------|--------|
| Persistence | ❌ Lost on restart | ✅ Survives restart | ✅ Survives restart |
| Shared across nodes | ❌ | ❌ | ✅ |
| TTL/auto-expiry | ❌ | ❌ | ✅ Native |
| Latency | ~0.001ms | ~1-5ms | ~0.1ms |
| Memory limit handling | OOM risk | Disk space | Eviction policies |

**Key advantage of Valkey**: The cache is shared across all DB-GPT nodes in a cluster. Node A caches a response, Node B can serve it — no duplicate LLM calls.

[← Previous: 02 Vector Store](02-vector-store.md)
