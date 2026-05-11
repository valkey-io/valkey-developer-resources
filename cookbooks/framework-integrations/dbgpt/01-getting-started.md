# Getting Started with DB-GPT + Valkey

**Beginner** · Python · ~15 min

## What is DB-GPT + Valkey?

[DB-GPT](https://github.com/eosphoros-ai/DB-GPT) is an open-source framework for building AI-native data applications with multi-model management, RAG pipelines, and multi-agent orchestration. Valkey plugs in as:

- **Vector Store** — sub-millisecond similarity search for RAG via HNSW indexes
- **LLM Cache** — cache model responses to slash latency and inference costs

DB-GPT uses a plugin system with `@register_resource` decorators and a registry, making Valkey a drop-in backend alongside ChromaDB, Milvus, and others.

## Prerequisites

- Python 3.10+
- Docker (for running Valkey)
- An embedding model (OpenAI, Bedrock, or local)

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image includes it:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

> **Note**: If you only need the cache (no vector store), plain `valkey/valkey:latest` works — no search module required.

## Step 2: Install DB-GPT with Valkey Support

```bash
# Install DB-GPT with Valkey vector store support
pip install "dbgpt-ext[storage_valkey]"

# Or install the cache separately (in dbgpt-ext)
pip install "dbgpt-ext[cache_valkey]"

# Or install everything
pip install "dbgpt-ext[storage_valkey,cache_valkey]"
```

This pulls in `valkey-glide>=2.3.0`, the official Valkey client with a Rust core and Python bindings.

## Step 3: Verify the Connection

```python
"""Quick connectivity check."""
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def check_connection():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)]
    )
    client = await GlideClient.create(config)

    result = await client.ping()
    print(f"Valkey says: {result}")  # b"PONG"

    # Check search module is loaded (needed for vector store)
    from glide import ft
    indexes = await ft.list(client)
    print(f"Search module loaded! ({len(indexes)} indexes found)")

    print("Connected successfully!")
    await client.close()


asyncio.run(check_connection())
```

## Step 4: Configure DB-GPT to Use Valkey

DB-GPT uses TOML configuration. Add Valkey as your vector store:

```toml
# In your DB-GPT config file (e.g., .env or config.toml)
[rag.storage.vector]
type = "valkey"
host = "localhost"
port = 6379
# password = "your-password"  # uncomment if auth is enabled
index_type = "HNSW"
distance_metric = "COSINE"
```

For the cache, set the storage type:

```toml
[cache]
storage_type = "valkey"
```

Or configure programmatically:

```python
from dbgpt_ext.storage.cache.valkey_cache import ValkeyCacheStorage

cache = ValkeyCacheStorage(
    host="localhost",
    port=6379,
    ttl_seconds=3600,  # 1 hour TTL
)
```

## Step 5: Understand the Architecture

```
┌──────────────────────────────────────────┐
│              DB-GPT Application           │
├──────────────┬───────────────────────────┤
│  RAG Pipeline │    LLM Cache Manager     │
│              │                           │
│  ValkeyStore │    ValkeyCacheStorage     │
│  (vector)    │    (key-value)            │
├──────────────┴───────────────────────────┤
│           valkey-glide client            │
├──────────────────────────────────────────┤
│         Valkey Server + Search Module    │
└──────────────────────────────────────────┘
```

| Component | Purpose | Valkey Features Used |
|-----------|---------|---------------------|
| ValkeyStore | RAG embeddings + similarity search | FT.CREATE, FT.SEARCH, HSET, JSON.SET |
| ValkeyCacheStorage | LLM response caching | GET, SET, EXPIRE |

## What's Next

- [02 - Vector Store for RAG →](02-vector-store.md) — load documents, create HNSW indexes, and run similarity searches
- [03 - LLM Response Caching →](03-llm-caching.md) — cache expensive LLM calls with automatic TTL

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `pip install "valkey-glide>=2.3.0"` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` image (includes search module) |
| `NOAUTH Authentication required` | Set `password` in config or `VALKEY_PASSWORD` env var |

[Next: 02 Vector Store for RAG →](02-vector-store.md)
