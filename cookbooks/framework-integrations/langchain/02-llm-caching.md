# LLM Caching with LangChain + Valkey

> Cache repeatable LangChain results in Valkey so identical requests do not repeat the same work.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers adding exact-key response caching to a
LangChain application.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start the sample from its directory.
- Python 3.10 or newer with the pinned requirements installed
- A local Valkey Bundle running on `127.0.0.1:6379`

## The Problem

LLM API calls can be expensive and slow. Users often send identical or near-identical prompts:

- Multiple users asking the same FAQ
- Retry logic re-sending the same prompt
- Agents re-invoking the same tool with the same input

Exact-match caching eliminates redundant calls. (For meaning-based matching, see [Guide 03](03-semantic-search.md).)

**Upstream Contribution:** The `ValkeyCache` integration was contributed to `langchain-ai/langchain-aws` in [PR #717](<https://github.com/langchain-ai/langchain-aws/pull/717>) by the Valkey team.

## Step 1: Initialize ValkeyCache

```python
from langgraph_checkpoint_aws import ValkeyCache
from valkey import Valkey

# Create Valkey client
valkey_client = Valkey.from_url(
    "valkey://127.0.0.1:6379",
    decode_responses=False,
)

# Initialize cache with 1-hour TTL
cache = ValkeyCache(
    client=valkey_client,
    prefix="llm_cache:",
    ttl=3600,
)
```

## Step 2: Cache Key Generation

Generate deterministic keys from prompt + model + temperature so different model configs don't collide:

```python
import hashlib

def cache_key(prompt: str, model: str = "local-deterministic", temp: float = 0.0) -> tuple:
    content = f"{model}|temp={temp}|{prompt.strip()}"
    key = hashlib.sha256(content.encode()).hexdigest()[:16]
    return (("llm_responses",), key)
```

## Step 3: Cached Inference Function

The default path uses a deterministic local response. Replace
`generate_response` with an async LangChain model call when adding a provider
to an application; the Valkey cache operations stay the same.

```python
import time


async def generate_response(prompt: str) -> str:
    return f"Local response for: {prompt}"


async def cached_llm_call(prompt: str) -> dict:
    key = cache_key(prompt)

    # 1. Check cache
    start = time.time()
    cached = await cache.aget([key])
    cache_time = time.time() - start

    if key in cached:
        return {
            "response": cached[key]["response"],
            "cached": True,
            "latency_ms": cache_time * 1000,
        }

    # 2. Cache miss - generate a response
    start = time.time()
    response = await generate_response(prompt)
    llm_time = time.time() - start

    # 3. Store in cache
    await cache.aset({key: ({"response": response}, 3600)})

    return {
        "response": response,
        "cached": False,
        "latency_ms": llm_time * 1000,
    }
```

## Step 4: Verify a Cache Hit

```python
import asyncio


async def benchmark():
    prompt = "What is Valkey?"

    # First call - cache miss
    r1 = await cached_llm_call(prompt)
    print(f"Cache MISS: {r1['response']}")

    # Second call - cache hit
    r2 = await cached_llm_call(prompt)
    print(f"Cache HIT:  {r2['response']}")


asyncio.run(benchmark())
```

## Step 5: TTL Management

```python
# Default TTL (set at cache creation)
cache = ValkeyCache(client=valkey_client, ttl=3600)  # 1 hour

key = cache_key("What is Valkey?")
data = {"response": "Valkey is a data store."}

async def apply_ttl():
    # Custom TTL per entry
    await cache.aset({key: (data, 300)})  # 5 minutes for volatile data

    # Clear all cached entries
    await cache.aclear()


import asyncio


asyncio.run(apply_ttl())
```

**Valkey Commands Fired:**

```text
# Cache lookup
GET llm_cache:a1b2c3d4e5f6g7h8

# Cache store
SET llm_cache:a1b2c3d4e5f6g7h8 '{"response":"..."}' EX 3600

# Cache clear
SCAN 0 MATCH llm_cache:* COUNT 100
DEL llm_cache:a1b2c3d4e5f6g7h8 ...
```

The complete local sample uses the same public API and removes only its own
run-scoped cache entries. Do not cache access tokens, credentials, or
unreviewed provider output.

## Configuration Reference

| Option | Default | Description |
| --- | --- | --- |
| `prefix` | `llm_cache:` | Prefix used for cache keys. |
| `ttl` | `3600` | Default entry lifetime in seconds. |
| Per-entry TTL | — | Overrides the default for one `aset` call. |

## Teardown

Close the client created for direct experiments:

```python
valkey_client.close()
```

## Next Steps

Exact-match caching is useful when requests are identical. Next, we'll add semantic search to match by meaning.

---

[Previous: 01 Getting Started ←](01-getting-started.md) |
[Next: 03 Semantic Search with ValkeyStore →](03-semantic-search.md)
