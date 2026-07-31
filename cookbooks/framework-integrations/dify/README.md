# Dify + Valkey Vector Store Cookbook

> Use Valkey as a vector database backend for knowledge base embeddings and retrieval in [Dify](https://dify.ai/), an open-source LLM application development platform.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Configure Dify to use Valkey as its vector store for RAG knowledge bases |

## Prerequisites

- **Valkey 9.1+** with the `valkey-search` module (use `valkey/valkey-bundle` image)
- **Docker** and **Docker Compose**
- **Dify** (self-hosted via Docker Compose)

## How Dify Uses Valkey

Dify integrates with Valkey through the `dify-vdb-valkey` provider plugin, using `valkey-glide` (the official Valkey Python client) and the `valkey-search` module for vector similarity search:

- **Vector storage** — Documents are stored as Valkey HASH keys containing the embedding (FLOAT32 bytes), page content, JSON metadata, and group/document IDs.
- **HNSW index** — An `FT.CREATE` index per collection enables fast KNN similarity search with configurable distance metrics (COSINE, L2, IP).
- **Full-text search** — The same index includes a TEXT field on `page_content` for keyword-based retrieval.
- **Key pattern** — `doc:{collection_name}:{doc_id}` with TAG fields for filtering by `group_id`, `doc_id`, and `document_id`.

## Upstream Status

> **Note:** The Valkey vector store backend is introduced in
> PR [langgenius/dify#35337](https://github.com/langgenius/dify/pull/35337)
> (currently OPEN). This cookbook documents the integration so it's ready when
> the feature ships. The sample project tests validate the underlying Valkey
> patterns independently using `valkey-glide`.

## Quick Start

```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    client_name="dify_vector_store",
)
client = await GlideClient.create(config)

# Store a document as a HASH (same pattern Dify uses internally)
import struct, json

embedding = [0.1, 0.2, 0.3]  # your vector
vector_bytes = struct.pack(f"<{len(embedding)}f", *embedding)

await client.hset("doc:my_collection:doc_001", {
    "vector": vector_bytes,
    "page_content": "Valkey is a high-performance key-value store.",
    "metadata": json.dumps({"source": "docs"}),
    "group_id": "dataset_123",
})
```

---

[← Back to Valkey Samples](../../../README.md)
