# LLM Caching with DB-GPT and Valkey

> Use `ValkeyCacheStorage` to cache LLM responses in Valkey, reducing latency and API costs for repeated or similar queries.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers using DB-GPT who want to avoid redundant LLM API calls by caching responses locally with configurable TTL.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running (plain Valkey is sufficient — no search module required for caching)
- `dbgpt-ext[storage-valkey]==0.8.1` installed

## Concepts

### How ValkeyCacheStorage Works

`ValkeyCacheStorage` implements DB-GPT's `CacheStorage` interface:

1. **Key-value storage** — LLM prompts are hashed into `CacheKey` objects; serialized responses become `CacheValue` objects stored as binary in Valkey.
2. **TTL support** — Cached entries expire automatically after a configurable time-to-live.
3. **Async operations** — `aget(key)` and `aset(key, value)` for non-blocking I/O in async pipelines.
4. **Sync wrappers** — `get(key)` and `set(key, value)` for synchronous usage.

### Why Cache LLM Responses?

| Benefit | Impact |
| --- | --- |
| **Cost reduction** | Avoid paying per-token for repeated queries |
| **Lower latency** | Cache hits avoid network round-trips to LLM providers |
| **Rate limit safety** | Reduce requests to stay within provider quotas |
| **Offline resilience** | Serve cached answers when the LLM API is unavailable |

### ValkeyCacheStorage Configuration

| Parameter | Default | Description |
| --- | --- | --- |
| `host` | `"localhost"` (env: `VALKEY_HOST`) | Valkey server hostname |
| `port` | `6379` (env: `VALKEY_PORT`) | Valkey server port |
| `password` | `None` (env: `VALKEY_PASSWORD`) | Authentication password |
| `use_ssl` | `False` | Enable TLS |
| `key_prefix` | `"dbgpt_cache:"` | Prefix for all cache keys in Valkey |
| `ttl_seconds` | `None` (no expiry) | Time-to-live for cache entries in seconds |
| `request_timeout` | `5000` | Request timeout in milliseconds |

## Step 1: Configure the Cache

```python
"""Configure ValkeyCacheStorage for LLM response caching."""
from __future__ import annotations

from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

# Basic configuration — entries never expire
cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
)

# With TTL — entries expire after 1 hour
cache_with_ttl = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,
)
```

## Step 2: How DB-GPT Uses the Cache Internally

`ValkeyCacheStorage` works with DB-GPT's internal `CacheKey` and `CacheValue` protocol. When DB-GPT's caching layer invokes the cache, it uses `LLMCacheKey` and `LLMCacheValue` objects:

```python
"""How DB-GPT's cache manager interacts with ValkeyCacheStorage."""
from __future__ import annotations

from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.cache.llm_cache import LLMCacheKey, LLMCacheValue

# DB-GPT constructs a cache key from the prompt + model + parameters
key = LLMCacheKey(prompt="What is Valkey?", model_name="gpt-4")

# The LLM response is wrapped in a CacheValue with a ModelOutput
value = LLMCacheValue(output=ModelOutput(error_code=0, text="Valkey is..."))

# ValkeyCacheStorage serializes these and stores them:
#   cache.set(key, value)   → serializes key to hash, value to bytes, SET in Valkey
#   cache.get(key)          → deserializes bytes back to LLMCacheValue
```

You typically don't call `get`/`set` directly — DB-GPT's `CacheManager` handles this transparently when configured.
The key hashing ensures that identical prompts with the same model and parameters always hit the same cache entry.

## Step 3: Understanding the Underlying Pattern

The sample code demonstrates the **raw Valkey operations** that `ValkeyCacheStorage` performs internally. This helps you understand what happens at the Valkey level:

```python
"""Cache-aside pattern showing the underlying Valkey operations."""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from glide import GlideClient, GlideClientConfiguration, NodeAddress


def make_cache_key(prompt: str, model: str, params: dict[str, Any]) -> str:
    """Generate a deterministic cache key from prompt + model + parameters.

    This mirrors how ValkeyCacheStorage hashes CacheKey objects.
    """
    key_data = json.dumps(
        {"prompt": prompt, "model": model, "params": params},
        sort_keys=True,
    )
    return f"dbgpt_cache:{hashlib.sha256(key_data.encode()).hexdigest()}"


async def cached_llm_call(
    client: GlideClient,
    prompt: str,
    model: str = "ollama/llama3",
    params: dict[str, Any] | None = None,
) -> str:
    """Call LLM with cache-aside pattern (raw Valkey operations)."""
    params = params or {}
    cache_key = make_cache_key(prompt, model, params)

    # Try cache first (mirrors ValkeyCacheStorage.get → client.get)
    cached = await client.get(cache_key)
    if cached is not None:
        print(f"  [CACHE HIT] {prompt[:40]}...")
        return json.loads(cached)["response"]

    # Cache miss — call LLM (mocked here)
    print(f"  [CACHE MISS] {prompt[:40]}...")
    response = f"Mock LLM response for: {prompt}"

    # Store in cache (mirrors ValkeyCacheStorage.set → client.set)
    value = json.dumps({"response": response, "model": model})
    await client.set(cache_key, value)
    return response


async def main() -> None:
    """Demonstrate cache-aside pattern."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="cache_demo",
    )
    client = await GlideClient.create(config)

    # First call — cache miss
    await cached_llm_call(client, "What is vector similarity search?")

    # Second call — cache hit (no API call needed)
    await cached_llm_call(client, "What is vector similarity search?")

    # Different prompt — cache miss
    await cached_llm_call(client, "How does HNSW work?")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 4: TTL-Based Expiration

Cache entries can expire automatically. When using `ValkeyCacheStorage(ttl_seconds=3600)`, every entry gets a 1-hour TTL. At the Valkey level, this uses the `EXPIRE` command:

```python
"""TTL-based cache expiration demonstration."""
from __future__ import annotations

import asyncio

from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def demo_ttl() -> None:
    """Show how TTL expiration works at the Valkey level."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="ttl_demo",
    )
    client = await GlideClient.create(config)

    key = "dbgpt_cache:ttl_example"

    # Store with TTL (ValkeyCacheStorage does this internally)
    await client.set(key, "cached response value")
    await client.expire(key, 2)  # 2 seconds for demo

    # Verify TTL is set
    ttl = await client.ttl(key)
    print(f"TTL remaining: {ttl}s")

    # Still available immediately
    result = await client.get(key)
    print(f"Before expiry: {result is not None}")  # True

    # Wait for expiry
    await asyncio.sleep(2.5)

    # Gone after TTL
    result = await client.get(key)
    print(f"After expiry: {result is None}")  # True

    await client.close()


if __name__ == "__main__":
    asyncio.run(demo_ttl())
```

## Step 5: Monitoring Cache Effectiveness

Track cache usage to verify the cache is working:

```python
"""Monitor cache stats using Valkey INFO and SCAN."""
from __future__ import annotations

import asyncio

from glide import GlideClient, GlideClientConfiguration, InfoSection, NodeAddress


async def check_cache_stats() -> None:
    """Print Valkey keyspace and memory stats for cache monitoring."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="cache_monitor",
    )
    client = await GlideClient.create(config)

    # Get keyspace and memory info
    info = await client.info(sections=[InfoSection.KEYSPACE, InfoSection.MEMORY])
    print("=== Cache Statistics ===")
    print(info)

    # Count cache keys using SCAN (never KEYS in production)
    cache_key_count = 0
    cursor = "0"
    while True:
        result = await client.custom_command(
            ["SCAN", cursor, "MATCH", "dbgpt_cache:*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        cache_key_count += len(result[1])
        if cursor == "0":
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
- Add a **prefix** (`dbgpt_cache:`) to namespace cache keys

### TTL Strategy

| Use Case | Recommended TTL | Rationale |
| --- | --- | --- |
| Factual Q&A | 24–72 hours | Facts change slowly |
| Creative writing | 1–4 hours | Users expect variety |
| Code generation | 12–24 hours | Code patterns are stable |
| Real-time data | 5–15 minutes | Answers go stale quickly |
| Embeddings | 7–30 days | Rarely change for same input |

Configure TTL when initializing `ValkeyCacheStorage`:

```python
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

# Factual Q&A cache — 24 hour TTL
factual_cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=86400,
)

# Creative writing cache — 1 hour TTL
creative_cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,
)
```

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
