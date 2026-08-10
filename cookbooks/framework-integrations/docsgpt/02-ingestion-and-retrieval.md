# Document Ingestion and Retrieval

> Use the `ValkeyStore` class directly to ingest documents, perform filtered KNN searches, and manage chunks — understanding the internals of DocsGPT's Valkey integration.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers who have completed the Getting Started guide and want to understand DocsGPT's ingestion pipeline, HNSW indexing, source isolation, and search mechanics at the code level.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running with the search module loaded
- DocsGPT dependencies installed

## Concepts

### ValkeyStore Architecture

`ValkeyStore` extends `BaseVectorStore` and implements:

| Method | Purpose |
| --- | --- |
| `search(query, k)` | KNN vector search filtered by `source_id` |
| `add_texts(texts, metadatas)` | Bulk ingest documents with embeddings |
| `add_chunk(text, metadata)` | Add a single document chunk |
| `get_chunks()` | List all chunks for the current source |
| `delete_chunk(chunk_id)` | Remove a specific chunk by its ID |
| `delete_index()` | Drop the vector index |

### Data Model

Each document chunk is stored as a Valkey HASH:

```text
Key:    doc:<uuid>
Fields: content     → "The document text..."
        source_id   → "my-source"
        metadata    → '{"source": "file.pdf", "page": 1}'
        embedding   → <768 float32 bytes>
```

The search index schema:

```text
FT.CREATE docsgpt ON HASH PREFIX 1 doc:
  SCHEMA
    content   TEXT
    source_id TAG
    embedding VECTOR HNSW 6
      TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE
```

## Step 1: Create a ValkeyStore Instance

```python
"""Create a ValkeyStore instance for direct interaction."""
from __future__ import annotations

import os

os.environ["VECTOR_STORE"] = "valkey"
os.environ["VALKEY_HOST"] = "localhost"
os.environ["VALKEY_PORT"] = "6379"

from application.vectorstore.valkey import ValkeyStore

# Each source_id isolates a set of documents
store = ValkeyStore(source_id="my-docs", embeddings_key="embeddings")
```

`ValkeyStore` supports context manager usage for automatic connection cleanup:

```python
with ValkeyStore(source_id="my-docs", embeddings_key="embeddings") as store:
    results = store.search("How does vector search work?", k=3)
# Connection is released automatically when the block exits
```

On creation, `ValkeyStore`:

1. Connects to Valkey using the synchronous GLIDE client
2. Creates an HNSW index (if it doesn't exist) with the schema above
3. Probes the embedding model to determine vector dimensions

## Step 2: Ingest Documents

### Bulk ingestion with `add_texts`

```python
"""Bulk ingest documents into the vector store."""
from __future__ import annotations

texts = [
    "Valkey is a high-performance in-memory data store.",
    "Vector search uses HNSW algorithm for approximate nearest neighbors.",
    "DocsGPT supports multiple vector store backends including Valkey.",
    "The GLIDE client provides sync and async interfaces for Valkey.",
]

metadatas = [
    {"source": "valkey-docs.pdf", "page": 1},
    {"source": "valkey-docs.pdf", "page": 5},
    {"source": "docsgpt-readme.md", "page": 1},
    {"source": "glide-docs.md", "page": 1},
]

doc_ids = store.add_texts(texts, metadatas)
print(f"Ingested {len(doc_ids)} documents: {doc_ids}")
```

Each call to `add_texts`:

1. Generates embeddings for all texts in a batch
2. Creates a UUID for each document
3. Packs the embedding as `struct.pack('<Nf', *floats)` (little-endian float32 bytes)
4. Stores each document as a HASH via `HSET`

### Single chunk with `add_chunk`

```python
"""Add a single chunk to the vector store."""
from __future__ import annotations

chunk_id = store.add_chunk(
    text="Valkey Search supports KNN queries with pre-filtering.",
    metadata={"source": "search-guide.md", "section": "queries"},
)
print(f"Added chunk: {chunk_id}")
```

## Step 3: Search by Semantic Similarity

```python
"""Perform semantic similarity search."""
from __future__ import annotations

results = store.search("How does vector search work?", k=3)

for doc in results:
    print(f"Content: {doc.page_content[:80]}...")
    print(f"Metadata: {doc.metadata}")
    print()
```

Under the hood, this:

1. Embeds the query text into a vector
2. Executes: `FT.SEARCH docsgpt "@source_id:{my-docs} =>[KNN 3 @embedding $BLOB AS score]"`
3. Returns documents ranked by cosine similarity

### Source Isolation

Each `source_id` is a TAG field filter. Multiple document sources share the same index but never mix in search results:

```python
"""Demonstrate source isolation with separate ValkeyStore instances."""
from __future__ import annotations

# These two stores share the same index but are isolated by source_id
store_a = ValkeyStore(source_id="project-a", embeddings_key="embeddings")
store_b = ValkeyStore(source_id="project-b", embeddings_key="embeddings")

# Searches are completely isolated
results_a = store_a.search("deployment guide", k=5)
results_b = store_b.search("deployment guide", k=5)
```

### Search Limits

`ValkeyStore` caps `k` at 100 to prevent server memory exhaustion on large indexes. If you need more results, paginate with multiple queries using different source filters.

## Step 4: Manage Chunks

### List all chunks for a source

```python
"""List and manage stored chunks."""
from __future__ import annotations

chunks = store.get_chunks()
print(f"Total chunks: {len(chunks)}")
for chunk in chunks:
    print(f"  ID: {chunk['doc_id']}, Text: {chunk['text'][:50]}...")
```

### Delete a specific chunk

```python
success = store.delete_chunk(doc_ids[0])
print(f"Deleted: {success}")  # True
```

### Delete all chunks for a source

```python
store.delete_index()
# All documents with source_id="my-docs" are removed
# The index itself remains for other sources
```

> **Note:** `delete_index` does not catch exceptions internally — any errors from Valkey propagate directly to the caller.

## Step 5: Understanding the KNN Query

The full `FT.SEARCH` query that `ValkeyStore.search()` builds:

```text
FT.SEARCH docsgpt
  "@source_id:{my\\-docs} =>[KNN 5 @embedding $BLOB AS __score]"
  PARAMS 2 BLOB <768_floats_as_bytes>
  LIMIT 0 5
  RETURN 3 content source_id metadata
  SORTBY __score ASC
```

Key details:

- **TAG escaping** — Special characters in `source_id` values are escaped (e.g., `-` → `\-`)
- **KNN pre-filtering** — The `@source_id:{...}` filter runs *before* the vector search, reducing the candidate set
- **Score direction** — Lower cosine distance = more similar (ascending sort)
- **RETURN fields** — Only fetches the fields needed, avoiding full HASH reads

## Performance Characteristics

| Operation | Complexity |
| --- | --- |
| `add_texts` (per doc) | O(log n) HNSW insert |
| `search` (KNN) | O(log n) HNSW search |
| `delete_chunk` | O(1) key delete |
| `get_chunks` | O(n) paginated scan |
| `delete_index` | O(n) scan + batch delete |

## What's Next

- [Production Deployment](./03-production.md) — Docker Compose, TLS, persistence, monitoring, and scaling

---

[← Back to cookbook index](./README.md)
