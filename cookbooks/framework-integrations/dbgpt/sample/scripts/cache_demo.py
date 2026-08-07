"""LLM cache demo using Valkey.

Demonstrates the Valkey patterns used by DB-GPT's ValkeyCacheStorage:
- Key-value storage for LLM response caching
- TTL-based expiration
- Cache-aside pattern with hash-based keys
- Async get/set operations

No paid API keys required — uses mock LLM responses.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from typing import Any

from glide import GlideClient, GlideClientConfiguration, NodeAddress

CACHE_PREFIX = "llm_cache:"


def make_cache_key(prompt: str, model: str, params: dict[str, Any] | None = None) -> str:
    """Generate a deterministic cache key from prompt + model + parameters."""
    key_data = json.dumps(
        {"prompt": prompt, "model": model, "params": params or {}},
        sort_keys=True,
    )
    return f"{CACHE_PREFIX}{hashlib.sha256(key_data.encode()).hexdigest()}"


async def demo_basic_cache(client: GlideClient) -> None:
    """Demonstrate basic cache set/get operations."""
    print("--- Basic Cache Operations ---\n")

    key = make_cache_key("What is Valkey?", "ollama/llama3")
    value = json.dumps({
        "response": "Valkey is a high-performance key-value store...",
        "model": "ollama/llama3",
        "tokens": 42,
    })

    # SET — cache a response
    await client.set(key, value)
    print(f"  ✓ Cached response (key: {key[:30]}...)")

    # GET — retrieve from cache
    cached = await client.get(key)
    if cached is not None:
        parsed = json.loads(cached)
        print(f"  ✓ Cache hit: {parsed['response'][:50]}...")
    else:
        print("  ✗ Cache miss (unexpected)")

    # EXISTS check
    exists = await client.exists([key])
    print(f"  ✓ Key exists: {exists > 0}")

    # Cleanup
    await client.delete([key])
    print(f"  ✓ Cleaned up key")


async def demo_ttl_cache(client: GlideClient) -> None:
    """Demonstrate TTL-based cache expiration."""
    print("\n--- TTL Cache Expiration ---\n")

    key = make_cache_key("ephemeral query", "ollama/llama3")
    value = "This response expires in 2 seconds"

    # SET with TTL (EX = seconds)
    await client.set(key, value)
    await client.expire(key, 2)
    print(f"  ✓ Cached with TTL=2s")

    # Verify TTL is set
    ttl = await client.ttl(key)
    print(f"  ✓ TTL remaining: {ttl}s")

    # Read before expiry
    cached = await client.get(key)
    print(f"  ✓ Before expiry: {cached is not None}")

    # Wait for expiry
    print("  ⏳ Waiting 2.5s for expiry...")
    await asyncio.sleep(2.5)

    # Read after expiry
    expired = await client.get(key)
    print(f"  ✓ After expiry: {expired is None} (key expired)")


async def demo_cache_aside(client: GlideClient) -> None:
    """Demonstrate cache-aside pattern for LLM calls."""
    print("\n--- Cache-Aside Pattern ---\n")

    queries = [
        "What is vector similarity search?",
        "How does HNSW work?",
        "What is vector similarity search?",  # duplicate — should hit cache
        "Explain cosine distance",
        "How does HNSW work?",  # duplicate — should hit cache
    ]

    hits = 0
    misses = 0

    for query in queries:
        key = make_cache_key(query, "ollama/llama3")
        cached = await client.get(key)

        if cached is not None:
            hits += 1
            print(f"  [HIT]  {query[:40]}")
        else:
            misses += 1
            # Simulate LLM call (mock response)
            response = json.dumps({
                "response": f"Mock answer for: {query}",
                "tokens": len(query.split()) * 10,
            })
            await client.set(key, response)
            # Set TTL of 1 hour for demo
            await client.expire(key, 3600)
            print(f"  [MISS] {query[:40]} → cached")

    print(f"\n  Summary: {hits} hits, {misses} misses "
          f"(hit rate: {hits / len(queries) * 100:.0f}%)")

    # Cleanup: scan for cache keys and delete
    cursor = "0"
    deleted = 0
    while True:
        result = await client.custom_command(
            ["SCAN", cursor, "MATCH", f"{CACHE_PREFIX}*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys_found = result[1]
        if keys_found:
            key_list = [k if isinstance(k, str) else k.decode() for k in keys_found]
            await client.delete(key_list)
            deleted += len(key_list)
        if cursor == "0":
            break

    print(f"  ✓ Cleaned up {deleted} cache keys")


async def demo_batch_cache(client: GlideClient) -> None:
    """Demonstrate batch cache operations using pipeline pattern."""
    print("\n--- Batch Cache Operations ---\n")

    # Prepare batch of items to cache
    items = {
        make_cache_key(f"batch query {i}", "ollama/llama3"): json.dumps({
            "response": f"Batch response {i}",
            "index": i,
        })
        for i in range(10)
    }

    # Batch set
    start = time.perf_counter()
    for key, value in items.items():
        await client.set(key, value)
    elapsed_set = (time.perf_counter() - start) * 1000
    print(f"  ✓ Batch set {len(items)} items in {elapsed_set:.1f}ms")

    # Batch get
    start = time.perf_counter()
    results = []
    for key in items:
        result = await client.get(key)
        results.append(result)
    elapsed_get = (time.perf_counter() - start) * 1000
    found = sum(1 for r in results if r is not None)
    print(f"  ✓ Batch get {found}/{len(items)} items in {elapsed_get:.1f}ms")

    # Cleanup
    await client.delete(list(items.keys()))
    print(f"  ✓ Cleaned up {len(items)} keys")


async def main() -> int:
    """Run the cache demo."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dbgpt_cache_demo",
        request_timeout=5000,
    )

    try:
        client = await GlideClient.create(config)
    except Exception as exc:
        print(f"✗ Failed to connect to Valkey: {exc}")
        return 1

    try:
        print("=== DB-GPT ValkeyCacheStorage Pattern Demo ===\n")

        await demo_basic_cache(client)
        await demo_ttl_cache(client)
        await demo_cache_aside(client)
        await demo_batch_cache(client)

        print("\n✅ Cache demo complete!")
        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
