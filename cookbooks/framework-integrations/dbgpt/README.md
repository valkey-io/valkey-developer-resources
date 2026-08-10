# DB-GPT + Valkey Cookbook

> Use Valkey as a vector store and LLM cache backend for [DB-GPT](https://github.com/eosphoros-ai/DB-GPT), an open-source AI-native data application development framework, via the `dbgpt-ext` extensions package.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Install dependencies, start Valkey, verify connectivity (~15 min) |
| [Vector Store](./02-vector-store.md) | Intermediate | ValkeyStore for RAG with HNSW indexing, document loading, similarity search, and metadata filtering (~20 min) |
| [LLM Caching](./03-llm-caching.md) | Intermediate | ValkeyCacheStorage for LLM response caching with TTL support (~20 min) |

## Prerequisites

- **Python 3.10+**
- **Valkey 8.1+** with the `valkey-search` module (use `valkey/valkey-bundle` image)
- **Docker** and **Docker Compose**

## How DB-GPT Uses Valkey

DB-GPT integrates with Valkey through two extension packages in `dbgpt-ext`:

- **Vector Store** (`dbgpt-ext[storage-valkey]`) — `ValkeyStore` implements DB-GPT's `VectorStoreBase`, storing embeddings as Valkey HASH keys with HNSW or FLAT indexes and KNN search with metadata filtering.

- **LLM Cache** (included in base `dbgpt-ext`) — `ValkeyCacheStorage` implements DB-GPT's `CacheStorage` interface for caching LLM responses with TTL support, reducing redundant API calls and latency.

Both use `valkey-glide` (the official Valkey Python client) for async connectivity.

## Quick Start

```bash
# Start Valkey with the search module
docker run -d --name valkey-dbgpt \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0

# Install DB-GPT extensions
pip install "dbgpt-ext[storage-valkey]==0.8.1"
```

```python
from dbgpt_ext.storage.vector_store.valkey_store import ValkeyStore, ValkeyVectorConfig

config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    index_type="HNSW",
    distance_metric="COSINE",
)
store = ValkeyStore(vector_store_config=config, embedding_fn=embedding_fn)
```

---

[← Back to Valkey Samples](../../../README.md)
