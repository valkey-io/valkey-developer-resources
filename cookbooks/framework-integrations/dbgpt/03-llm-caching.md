# LLM Caching with DB-GPT and Valkey

> Use `ValkeyCacheStorage` to cache LLM responses in Valkey, reducing latency and API costs for repeated or similar queries.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers using DB-GPT who want to avoid redundant LLM API calls by caching responses locally with configurable TTL.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running (plain Valkey is sufficient — no search module required for caching)
- `dbgpt-ext[cache_valkey]==0.8.1` installed

## Concepts

### How ValkeyCacheStorage Works

`ValkeyCacheStorage` implements DB-GPT's `CacheStorage` interface:

1. **Key-value storage** — LLM prompts (or their hashes) serve as keys; serialized responses are values.
2. **TTL support** — Cached entries expire automatically after a configurable time-to-live.
3. **Async operations** — `aget(key)` and `aset(key, value)` for non-blocking I/O in async pipelines.
4. **Sync wrappers** — `get(key)` and `set(key, value)` for synchronous usage.

### Why Cache LLM Responses?

| Benefit | Impact |
| --- | --- |
| **Cost reduction** | Avoid paying per-token for repeated queries |
| **Lower latency** | Cache hits return in <1ms vs 500ms–5s for API calls |
| **Rate limit safety** | Reduce requests to stay within provider quotas |
| **Offline resilience** | Serve cached answers when the LLM API is unavailable |

## Step 1: Configure the Cache

```python
"""Configure ValkeyCacheStorage for LLM response caching."""
from __future__ import annotations

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
)
```

## Step 2: Basic Cache Operations (Sync)

```python
"""Synchronous cache get/set operations."""
from __future__ import annotations

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

cache = ValkeyCacheStorage(host="localhost", port=6379)

# Cache an LLM response
prompt_key = "What is Valkey?"
response_value = "Valkey is a high-performance key-value store..."

cache.set(prompt_key, response_value)
print(f"✓ Cached response for: {prompt_key!r}")

# Retrieve from cache
cached = cache.get(prompt_key)
if cached is not None:
    print(f"✓ Cache hit: {cached[:50]}...")
else:
    print("✗ Cache miss — would call LLM API")

# Check existence without retrieving
exists = cache.exists(prompt_key)
print(f"Key exists in cache: {exists}")

cache.close()
```

## Step 3: Async Cache Operations

For async DB-GPT pipelines, use the async interface:

```python
"""Async cache operations for non-blocking I/O."""
from __future__ import annotations

import asyncio

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


async def main() -> None:
    """Demonstrate async cache operations."""
    cache = ValkeyCacheStorage(host="localhost", port=6379)

    # Async set
    await cache.aset("async_prompt", "async_response_value")
    print("✓ Async set complete")

    # Async get
    result = await cache.aget("async_prompt")
    print(f"✓ Async get: {result}")

    # Pattern: check cache before calling LLM
    query = "Explain HNSW algorithm"
    cached_response = await cache.aget(query)

    if cached_response is not None:
        print(f"Cache hit — returning cached response")
        response = cached_response
    else:
        print("Cache miss — would call LLM API here")
        # response = await llm_client.generate(query)
        response = "HNSW is a graph-based ANN algorithm..."  # mock
        await cache.aset(query, response)
        print("✓ Response cached for future queries")

    cache.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 4: Cache-Aside Pattern for LLM Calls

Implement the cache-aside pattern to transparently cache LLM responses:

```python
"""Cache-aside pattern for LLM response caching."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage


def make_cache_key(prompt: str, model: str, params: dict[str, Any]) -> str:
    """Generate a deterministic cache key from prompt + model + parameters."""
    key_data = json.dumps(
        {"prompt": prompt, "model": model, "params": params},
        sort_keys=True,
    )
    return f"llm_cache:{hashlib.sha256(key_data.encode()).hexdigest()}"


def cached_llm_call(
    cache: ValkeyCacheStorage,
    prompt: str,
    model: str = "ollama/llama3",
    params: dict[str, Any] | None = None,
) -> str:
    """Call LLM with cache-aside pattern."""
    params = params or {}
    cache_key = make_cache_key(prompt, model, params)

    # Try cache first
    cached = cache.get(cache_key)
    if cached is not None:
        print(f"  [CACHE HIT] {prompt[:40]}...")
        return cached

    # Cache miss — call LLM (mocked here)
    print(f"  [CACHE MISS] {prompt[:40]}...")
    response = f"Mock LLM response for: {prompt}"  # Replace with actual LLM call

    # Store in cache
    cache.set(cache_key, response)
    return response


# Usage
cache = ValkeyCacheStorage(host="localhost", port=6379)

# First call — cache miss
result1 = cached_llm_call(cache, "What is vector similarity search?")

# Second call — cache hit (fast, no API call)
result2 = cached_llm_call(cache, "What is vector similarity search?")

# Different prompt — cache miss
result3 = cached_llm_call(cache, "How does HNSW work?")

cache.close()
```

## Step 5: Monitoring Cache Effectiveness

Track cache hit rates to verify the cache is working:

```python
"""Monitor cache hit/miss rates using Valkey INFO stats."""
from __future__ import annotations

import asyncio

from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def check_cache_stats() -> None:
    """Print Valkey keyspace and memory stats for cache monitoring."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="cache_monitor",
    )
    client = await GlideClient.create(config)

    # Get keyspace info
    info = await client.info(sections=["keyspace", "memory"])
    print("=== Cache Statistics ===")
    print(info)

    # Count cache keys using SCAN (never KEYS in production)
    cache_key_count = 0
    cursor = "0"
    while True:
        result = await client.custom_command(
            ["SCAN", cursor, "MATCH", "llm_cache:*", "COUNT", "100"]
        )
        cursor = result[0]
        cache_key_count += len(result[1])
        if cursor == b"0" or cursor == "0":
            break

    print(f"Total cached LLM responses: {cache_key_count}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(check_cache_stats())
```

## Best Practices

### Cache Key Design

- Include the **model name** in the key — different models produce different outputs
- Include **relevant parameters** (temperature, max_tokens) — same prompt with different params yields different results
- Use a hash for the key to keep it short and avoid special characters
- Add a **prefix** (`llm_cache:`) to namespace cache keys

### TTL Strategy

| Use Case | Recommended TTL | Rationale |
| --- | --- | --- |
| Factual Q&A | 24–72 hours | Facts change slowly |
| Creative writing | 1–4 hours | Users expect variety |
| Code generation | 12–24 hours | Code patterns are stable |
| Real-time data | 5–15 minutes | Answers go stale quickly |
| Embeddings | 7–30 days | Rarely change for same input |

### When NOT to Cache

- Queries that include user-specific context (PII leakage risk)
- Prompts with `temperature > 0` where variety is desired
- Streaming responses (cache the final assembled response instead)
- Security-sensitive queries (authentication, authorization decisions)

## What's Next

- Combine vector store and cache: use `ValkeyStore` for RAG retrieval and `ValkeyCacheStorage` for caching the final LLM-generated answers
- Explore DB-GPT's built-in cache integration to apply `ValkeyCacheStorage` transparently across all LLM calls in your application

---

[← Back to cookbook index](./README.md)
