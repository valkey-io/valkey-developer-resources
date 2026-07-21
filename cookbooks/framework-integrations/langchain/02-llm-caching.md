# LLM Caching with LangChain + Valkey

> Use `ValkeyCache` to store and retrieve deterministic exact-key results without making a provider call.

**Intermediate** · Python · ~20 min

**Who is this for:** This page is for developers adding repeatable cache reads
and writes around LangChain work while keeping the local example independent of
a hosted model.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start the sample from its directory.
- Python 3.10 or newer and an active virtual environment.
- Docker Compose with the pinned Valkey bundle running.

From the sample directory, the setup is:

```bash
cd cookbooks/framework-integrations/langchain/sample
docker compose up -d
python -m pip install -r requirements.txt
```

## Step 1: Create a cache

`main.py` creates `ValkeyCache` with the connection, configured prefix, and default TTL from `Settings`:

```python
from langgraph_checkpoint_aws import ValkeyCache
from main import Settings, create_valkey_client

settings = Settings.from_env()
client = create_valkey_client(settings)
cache = ValkeyCache(
    client=client,
    prefix=settings.cache_prefix,
    ttl=settings.cache_ttl_seconds,
)
```

The default cache TTL is five minutes. The cache key is a tuple containing a namespace tuple and a string key, which is the shape expected by the package and by `run_cache_demo`.

## Step 2: Read and write one entry

The public async methods used by the sample are `aget` and `aset`:

```python
from main import run_cache_demo

key = (("langchain-cookbook", "lesson"), "answer-1")
value = {"answer": "Valkey is a data store for this exercise."}

first = run_cache_demo(cache, key=key, value=value)
second = run_cache_demo(
    cache,
    key=key,
    value={"answer": "This value is not written after a hit."},
)
print(first)
print(second)

client.close()
```

`run_cache_demo` calls `await cache.aget([key])`, then calls
`await cache.aset({key: (value, None)})` only on a miss. To use the public class
directly in an async application, the equivalent operations are:

The following helper is illustrative and assumes the `cache` from Step 1 and
the public `ValkeyCache` class:

```python
from langgraph_checkpoint_aws import ValkeyCache


async def lookup_or_store(cache: ValkeyCache, key, value):
    cached_values = await cache.aget([key])
    if key in cached_values:
        return cached_values[key]
    await cache.aset({key: (value, None)})
    return value
```

The `None` entry TTL delegates to the cache's configured default. A per-entry positive TTL can be supplied as the second element of the `(value, ttl)` tuple.

## Cache key design

Exact caching is only useful when equivalent requests produce the same key.
Include the model configuration and normalized prompt in the key so different
configurations do not collide:

```python
import hashlib

def cache_key(
    prompt: str,
    model_name: str = "local-deterministic",
    temperature: float = 0.0,
) -> tuple[tuple[str, ...], str]:
    content = f"{model_name}|temperature={temperature}|{prompt.strip()}"
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    return (("llm-responses",), digest)
```

## Wrap a model call

The cache can surround any async LangChain model call. The provider remains
outside the default sample:

This helper continues after the `cache_key` example and reuses that function:

```python
async def cached_response(cache, prompt: str, generate):
    key = cache_key(prompt)
    cached_values = await cache.aget([key])
    if key in cached_values:
        return {"value": cached_values[key], "cached": True}

    response = await generate(prompt)
    await cache.aset({key: (response, None)})
    return {"value": response, "cached": False}
```

`generate` can call a LangChain model such as a local or hosted provider. Keep
that provider choice and its data-handling policy separate from cache storage.

## Step 3: Run the local example

Run `main.py` to exercise the cache as part of the complete deterministic flow:

```bash
python main.py
```

The one-shot demo starts with an empty run namespace, prints the cache result,
and cleans that run's keys in `finally`. Run the focused test command to verify
a miss followed by a hit and explicit TTL behavior:

```bash
python -m pytest -q test_langchain.py
```

## Step 4: Apply cache safety rules

Use a prefix and namespace that identify the owning application. Do not cache
access tokens, credentials, personal data, or unreviewed provider output. Treat
cached values as data with the same retention and access requirements as the
source response. Keep the local Compose service on loopback and use approved
authentication, TLS, and network controls for shared Valkey deployments.

For explicit retention or namespace cleanup, use the public cache methods:

This example reuses the `cache`, `key`, and `value` created above:

```python
await cache.aset({key: (value, 300)})
await cache.aclear([("llm-responses",)])
```

## How It Works

`ValkeyCache` turns the tuple key into a namespaced cache key, checks for
existing values with `aget`, and serializes new values through `aset`. The
default TTL from `CACHE_TTL_SECONDS` applies when the entry does not provide its
own TTL. `cleanup_sample` removes only entries for the requested run under the
configured cache prefix.

Under the hood, the integration may map these operations to Valkey key-value
reads, writes with expiration, and scans during cleanup. Those command details
explain lifecycle behavior; application code should call `ValkeyCache.aget`,
`ValkeyCache.aset`, and `ValkeyCache.aclear` rather than issuing raw commands.

## Configuration Reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `VALKEY_URL` | `valkey://127.0.0.1:6379` when unset | Full Valkey URL; takes precedence over host and port. |
| `VALKEY_HOST` | `127.0.0.1` | Host fallback when `VALKEY_URL` is unset. |
| `VALKEY_PORT` | `6379` | Port fallback when `VALKEY_URL` is unset. |
| `VALKEY_SOCKET_TIMEOUT` | `5.0` | Socket and connection timeout in seconds. |
| `CHECKPOINT_TTL_SECONDS` | `3600` | Checkpoint lifetime in seconds. |
| `CACHE_TTL_SECONDS` | `300` | Default exact-cache lifetime in seconds. |
| `STORE_TTL_MINUTES` | `60` | Default store lifetime in minutes. |
| `VALKEY_CACHE_PREFIX` | `langchain:cache:` | Prefix used by `ValkeyCache`. |
| `VALKEY_STORE_COLLECTION` | `langchain_store_idx` | Search collection used by `ValkeyStore`. |
| `VALKEY_STORE_NAMESPACE` | `langchain-cookbook` | Namespace prefix used by the sample store. |

## Optional Bedrock/provider addendum

The default cache path does not call an LLM and does not require provider
credentials. An optional Bedrock-backed LangChain model can be placed before
`ValkeyCache.aset` in an application, but model selection, authentication,
request serialization, privacy review, and provider package installation are
outside this sample. Keep the provider path opt-in.

## Teardown

Close a client created by the sample after direct API experiments, then stop Valkey:

```python
client.close()
```

```bash
docker compose down --volumes
```

---

[Previous: 01 - Getting Started](01-getting-started.md) | [Back to LangChain + Valkey](README.md) | [Next: 03 - Semantic Search](03-semantic-search.md)
