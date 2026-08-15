# KV Cache Sharing Across Instances

> Two simulated LMCache instances sharing a KV cache chunk through a centralized Valkey store — no second GPU required to see how the sharing mechanism works.

**Intermediate** · Python · ~15 min

**Who is this for:** Python developers who want to understand how LMCache's Valkey key format enables cross-instance cache reuse before deploying multiple vLLM instances.

## Why Share KV Caches?

In production LLM serving, multiple vLLM instances often handle the same system prompts, few-shot
examples, or frequently asked questions. Without sharing, each instance recomputes identical KV
caches independently — wasting GPU cycles.

With Valkey as a centralized L2 store:

```text
Instance A computes KV cache for prompt → stores to Valkey
Instance B receives same prompt → loads from Valkey, skips prefill
```

This works because `CacheEngineKey.to_string()` (see [01 - Getting Started](01-getting-started.md))
is a pure function of `(model_name, world_size, worker_id, chunk_hash, dtype)`. Two instances that
compute the same chunk hash for the same prompt produce the identical Valkey key — whichever
instance stores first, every other instance reads instead of recomputing.

## Prerequisites

- Docker installed
- Completed [01 - Getting Started](01-getting-started.md)
- No second GPU needed for this cookbook — see the [sample code](sample/) for what's simulated versus what a real deployment requires

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:8.1.1
```

## Step 2: Two Independent Connections

Simulate two vLLM+LMCache instances as two independent GLIDE clients talking to the same Valkey:

```python
import asyncio
from glide import (
    AdvancedGlideClientConfiguration,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

async def make_client():
    return await GlideClient.create(
        GlideClientConfiguration(
            addresses=[NodeAddress("localhost", 6379)],
            request_timeout=5000,
            advanced_config=AdvancedGlideClientConfiguration(connection_timeout=5000),
        )
    )
```

## Step 3: Instance A Computes and Stores

```python
import torch
from lmcache.utils import CacheEngineKey

def make_key(chunk_hash: int) -> str:
    return CacheEngineKey(
        model_name="Qwen/Qwen3-8B",
        world_size=1,
        worker_id=0,
        chunk_hash=chunk_hash,
        dtype=torch.float16,
    ).to_string()

async def instance_a_stores(chunk_hash: int, chunk_bytes: bytes):
    client = await make_client()
    try:
        key = make_key(chunk_hash)
        await client.set(key, chunk_bytes)
        print(f"Instance A stored under: {key}")
    finally:
        await client.close()
```

## Step 4: Instance B Reads Without Recomputing

```python
async def instance_b_reads(chunk_hash: int):
    client = await make_client()
    try:
        # Computed independently — Instance B never talked to Instance A.
        key = make_key(chunk_hash)
        if await client.exists([key]):
            data = await client.get(key)
            print(f"Instance B loaded {len(data)} bytes from Valkey — no recompute needed.")
        else:
            print("Cache miss — Instance B would compute and store instead.")
    finally:
        await client.close()
```

Because both instances compute the same `chunk_hash` for the same prompt content, they arrive at the identical key — the second instance's `EXISTS` check finds what the first instance stored.

## Run It

```bash
python sample/kv_cache_sharing.py
```

## Architecture

```text
┌──────────────┐     ┌──────────────┐
│  Simulated    │     │  Simulated    │
│  Instance A   │     │  Instance B   │
└──────┬────────┘     └──────┬────────┘
       │  store               │  load
       ▼                      ▼
┌─────────────────────────────────────┐
│            Valkey (L2)              │
│   Shared KV cache storage           │
│   valkey://localhost:6379            │
└─────────────────────────────────────┘
```

## What This Does and Doesn't Show

This cookbook demonstrates the **key-sharing mechanism** — identical inputs produce identical
Valkey keys, so a second process can read what a first process wrote. It does not reproduce
LMCache's **token-level prefix chunking**, where two prompts that share only a common prefix (not
the whole prompt) still share cache for that prefix. Real prefix-level sharing requires tokenizing
with the actual model and hashing per-chunk (see `lmcache/v1/token_database.py` in the LMCache
source) — out of scope for a GPU-free cookbook, but the underlying principle (same hash → same key
→ shared cache) is identical to what's shown here.

## Serialization Options

| Format | Speed | Size | Best For |
| ------ | ----- | ---- | -------- |
| `naive` | Fastest | Largest | Single-instance, local network |
| `cachegen` | Moderate | Meaningfully smaller | Cross-instance, bandwidth-constrained |

For multi-instance sharing over a network, `cachegen` typically wins because the reduced transfer
size more than compensates for compression overhead. (This is LMCache's own documented guidance —
this cookbook's demo uses `naive` since it doesn't transfer real KV tensors across a network.)

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
