# Getting Started with DB-GPT and Valkey

> Install DB-GPT's Valkey extensions, start a Valkey instance with the search module, and verify connectivity from Python.

**Beginner** · Python · ~15 min

**Who is this for:** Developers using DB-GPT who want to add Valkey as a vector store or LLM cache backend without deploying a separate vector database.

## Prerequisites

- Python 3.10+
- Docker (for running Valkey)
- Basic familiarity with DB-GPT concepts (agents, knowledge bases)

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## How It Works

DB-GPT connects to Valkey through two extension components:

| Component | Purpose | Valkey Module Required |
| --- | --- | --- |
| `ValkeyStore` | Vector storage for RAG (embeddings, similarity search, metadata filtering) | `valkey-search` |
| `ValkeyCacheStorage` | LLM response caching (key-value with optional TTL) | None (core Valkey) |

**Architecture:**

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  DB-GPT App │────▶│  dbgpt-ext       │────▶│  Valkey Server  │
│             │     │  (valkey-glide)   │     │  + Search Module│
└─────────────┘     └──────────────────┘     └─────────────────┘
```

- **Vector Store path:** DB-GPT → `ValkeyStore` → valkey-glide → `FT.CREATE` / `FT.SEARCH` / `HSET`
- **Cache path:** DB-GPT → `ValkeyCacheStorage` → valkey-glide → `SET` / `GET` with optional TTL

## Step 1: Start Valkey with the Search Module

DB-GPT's vector store requires the `valkey-search` module for `FT.CREATE` and `FT.SEARCH` commands. Use the `valkey-bundle` image which includes it:

```bash
docker run -d --name valkey-dbgpt \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

Verify the search module is loaded:

```bash
docker exec valkey-dbgpt valkey-cli MODULE LIST
# Should show "search" in the output
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Install DB-GPT Extensions

Install the Valkey extensions for vector store and cache:

```bash
pip install "dbgpt-ext[storage-valkey]==0.8.1"
```

This installs:

- `dbgpt-ext` — the DB-GPT extensions package (includes `ValkeyCacheStorage`)
- `valkey-glide` — the official async Valkey client (pulled in by the `storage-valkey` extra)
- Dependencies for vector store (`ValkeyStore`) and cache (`ValkeyCacheStorage`)

> **Note:** The `storage-valkey` extra installs `valkey-glide`, which is the only
> additional dependency needed. `ValkeyCacheStorage` is included in the base
> `dbgpt-ext` package and requires no separate extra.

## Step 3: Verify Connectivity

Create a simple script to verify the connection works:

```python
"""Verify Valkey connectivity for DB-GPT extensions."""
from __future__ import annotations

import asyncio
import struct

from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def main() -> None:
    """Connect to Valkey and verify the search module is available."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dbgpt_connectivity_check",
    )
    client = await GlideClient.create(config)

    # Basic connectivity
    pong = await client.ping()
    print(f"✓ Connected to Valkey: {pong}")

    # Verify search module via FT.CREATE + FT.DROP
    test_index = "__dbgpt_connectivity_test__"
    await client.custom_command(
        ["FT.CREATE", test_index, "ON", "HASH", "PREFIX", "1", "__test__:",
         "SCHEMA", "vec", "VECTOR", "FLAT", "6",
         "TYPE", "FLOAT32", "DIM", "3", "DISTANCE_METRIC", "COSINE"]
    )
    print("✓ valkey-search module is available (FT.CREATE succeeded)")

    # Clean up test index
    await client.custom_command(["FT.DROPINDEX", test_index])
    print("✓ Cleanup complete (FT.DROPINDEX succeeded)")

    # Verify basic HASH operations (used by both vector store and cache)
    test_key = "__dbgpt_test_hash__"
    embedding = [0.1, 0.2, 0.3]
    vector_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
    await client.hset(test_key, {"vector": vector_bytes, "content": "test"})
    result = await client.hget(test_key, "content")
    assert result == b"test", f"Expected b'test', got {result}"
    await client.delete([test_key])
    print("✓ HASH operations work (vector store pattern)")

    await client.close()
    print("\n✅ All checks passed — Valkey is ready for DB-GPT!")


if __name__ == "__main__":
    asyncio.run(main())
```

Run the connectivity check:

```bash
python scripts/getting_started.py
```

Expected output:

```text
✓ Connected to Valkey: PONG
✓ valkey-search module is available (FT.CREATE succeeded)
✓ Cleanup complete (FT.DROPINDEX succeeded)
✓ HASH operations work (vector store pattern)

✅ All checks passed — Valkey is ready for DB-GPT!
```

## Step 4: Verify DB-GPT Import

Confirm the DB-GPT extensions are importable:

```python
"""Verify DB-GPT Valkey extensions are importable."""
from dbgpt_ext.storage.vector_store.valkey_store import ValkeyStore, ValkeyVectorConfig
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

print(f"✓ ValkeyStore: {ValkeyStore}")
print(f"✓ ValkeyVectorConfig: {ValkeyVectorConfig}")
print(f"✓ ValkeyCacheStorage: {ValkeyCacheStorage}")
print("\n✅ All DB-GPT Valkey extensions imported successfully!")
```

## Authentication Options

| Method | Configuration | Use Case |
| --- | --- | --- |
| No auth | Default (local dev) | Development and testing only |
| Password | `password` parameter or `VALKEY_PASSWORD` env var | Simple single-user deployments |
| ACL | `user` + `password` parameters | Multi-tenant / production |
| TLS | `use_ssl=True` | Encrypted connections (cloud, cross-network) |

## Troubleshooting

| Problem | Cause | Fix |
| --- | --- | --- |
| `ConnectionError` | Valkey not running | Start Valkey: `docker compose up -d` |
| `MODULE LIST` shows no `search` | Wrong image | Use `valkey/valkey-bundle:9.1.0` (not plain `valkey/valkey`) |
| `ImportError: No module named 'glide'` | Missing dependency | `pip install "dbgpt-ext[storage-valkey]==0.8.1"` |
| `FT.CREATE` returns error | Search module not loaded | Ensure using `valkey-bundle` image with search module |
| `ValueError: embedding_fn is required` | ValkeyStore needs an embedding function | Pass `embedding_fn=` when constructing `ValkeyStore` |

## What's Next

- [Vector Store](./02-vector-store.md) — Load documents, build HNSW indexes, and perform similarity search with metadata filtering
- [LLM Caching](./03-llm-caching.md) — Cache LLM responses to reduce latency and API costs

---

[← Back to cookbook index](./README.md)
