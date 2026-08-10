# DocsGPT + Valkey Cookbook

> Use Valkey as the vector store backend for [DocsGPT](https://github.com/arc53/DocsGPT),
> an open-source AI assistant platform for document retrieval (RAG),
> via `valkey-glide-sync` and the valkey-search module.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Start Valkey, configure DocsGPT, verify connectivity (~15 min) |
| [Ingestion & Retrieval](./02-ingestion-and-retrieval.md) | Intermediate | Chunking, embedding storage, HNSW indexing, filtered KNN search (~20 min) |
| [Production Deployment](./03-production.md) | Advanced | Docker Compose, TLS, persistence, monitoring, scaling (~20 min) |

## Prerequisites

- **Python 3.10+**
- **Valkey 8.1+** with the `valkey-search` module (use `valkey/valkey-bundle` image)
- **Docker** and **Docker Compose**

## How DocsGPT Uses Valkey

DocsGPT integrates with Valkey through a `ValkeyStore` class that implements the `BaseVectorStore` interface using the synchronous GLIDE client (`valkey-glide-sync`):

- **Document ingestion** — Chunks documents, generates embeddings, and stores each chunk as a Valkey HASH with fields: `content`, `source_id`, `metadata`, `embedding`.
- **HNSW index** — Creates an `FT.CREATE` index with HNSW algorithm for approximate nearest neighbor search.
- **Filtered KNN search** — `FT.SEARCH` with `@source_id:{id}` pre-filtering isolates results by document source.
- **Source isolation** — Each document source gets its own namespace via TAG field filtering on a shared index.

## Quick Start

```bash
# Start Valkey with the search module
docker run -d --name valkey-docsgpt \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0

# Install the client library
pip install "valkey-glide-sync==2.3.1"
```

```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    addresses=[NodeAddress(host="localhost", port=6379)]
)
client = GlideClient.create(config)
print(client.ping())  # b'PONG'
```

---

[← Back to Valkey Samples](../../../README.md)
