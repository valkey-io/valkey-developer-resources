# Vector Store with DB-GPT and Valkey

> Use `ValkeyStore` as a vector database for RAG pipelines in DB-GPT, with HNSW indexing, document loading, similarity search, and metadata filtering.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers building RAG (Retrieval-Augmented Generation) applications with DB-GPT who want fast, local vector storage without external vector database dependencies.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running with the `valkey-search` module
- `dbgpt-ext[storage_valkey]==0.8.1` installed

## Concepts

### How ValkeyStore Works

`ValkeyStore` implements DB-GPT's `VectorStoreBase` interface:

1. **Index creation** — On first use, creates an `FT.CREATE` index with a VECTOR field (HNSW or FLAT algorithm) plus optional metadata fields (TAG, NUMERIC).
2. **Document loading** — `load_document(chunks)` stores each chunk as a Valkey HASH with the embedding bytes, text content, and metadata.
3. **Similarity search** — `similar_search(text, topk)` converts the query text to an embedding, then runs a KNN query via `FT.SEARCH`.
4. **Metadata filtering** — Combine vector similarity with attribute filters using `FT.SEARCH` filter expressions.

### ValkeyVectorConfig

The configuration dataclass controls index behavior:

| Parameter | Default | Description |
| --- | --- | --- |
| `host` | `"localhost"` | Valkey server hostname |
| `port` | `6379` | Valkey server port |
| `password` | `None` | Authentication password |
| `use_ssl` | `False` | Enable TLS |
| `index_type` | `"HNSW"` | Index algorithm: `HNSW` or `FLAT` |
| `distance_metric` | `"COSINE"` | Distance: `COSINE`, `L2`, or `IP` |
| `key_prefix` | `"dbgpt:"` | Key prefix for stored documents |
| `hnsw_m` | `16` | HNSW max connections per node |
| `hnsw_ef_construction` | `200` | HNSW construction search width |
| `hnsw_ef_runtime` | `10` | HNSW query-time search width |
| `metadata_schema` | `None` | Dict defining filterable metadata fields |

## Step 1: Configure the Vector Store

```python
"""Configure ValkeyStore for document storage and retrieval."""
from __future__ import annotations

from dbgpt_ext.storage.vector_store.valkey_store import ValkeyStore, ValkeyVectorConfig

config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    index_type="HNSW",
    distance_metric="COSINE",
    hnsw_m=16,
    hnsw_ef_construction=200,
    hnsw_ef_runtime=10,
    metadata_schema={
        "category": "tag",
        "year": "numeric",
    },
)

store = ValkeyStore(config)
```

The `metadata_schema` declares which metadata fields are indexed for filtering:

- `"tag"` — Exact-match filtering (categories, labels, IDs)
- `"numeric"` — Range filtering (years, scores, prices)

## Step 2: Load Documents

DB-GPT represents documents as `Chunk` objects. Load them into the vector store:

```python
"""Load document chunks into ValkeyStore."""
from __future__ import annotations

from dbgpt.core import Chunk
from dbgpt_ext.storage.vector_store.valkey_store import ValkeyStore, ValkeyVectorConfig

config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    index_type="HNSW",
    distance_metric="COSINE",
    metadata_schema={
        "category": "tag",
        "year": "numeric",
    },
)
store = ValkeyStore(config)

# Create document chunks with metadata
chunks = [
    Chunk(
        content="Valkey is a high-performance key-value store forked from Redis.",
        metadata={"category": "database", "year": 2024},
    ),
    Chunk(
        content="HNSW indexes provide approximate nearest neighbor search with sub-linear query time.",
        metadata={"category": "algorithms", "year": 2023},
    ),
    Chunk(
        content="DB-GPT supports multiple vector store backends including Valkey, Chroma, and Milvus.",
        metadata={"category": "database", "year": 2024},
    ),
    Chunk(
        content="Cosine similarity measures the angle between two vectors, ignoring magnitude.",
        metadata={"category": "algorithms", "year": 2022},
    ),
]

# Load chunks — this creates the HNSW index and stores embeddings
store.load_document(chunks)
print(f"✓ Loaded {len(chunks)} chunks into ValkeyStore")
```

> **Note:** `load_document` uses your configured DB-GPT embedding model to generate vectors.
> For local development without paid APIs, configure DB-GPT to use an Ollama embedding model
> (e.g., `nomic-embed-text`) or see the sample scripts which use mock embeddings for testing.

## Step 3: Similarity Search

Query the store for semantically similar documents:

```python
"""Perform similarity search against stored documents."""
from __future__ import annotations

# Basic similarity search — returns top-k most similar chunks
results = store.similar_search("What is Valkey?", topk=3)

for i, chunk in enumerate(results, 1):
    print(f"{i}. [{chunk.metadata.get('category')}] {chunk.content[:80]}...")

# Search with scores — includes similarity scores for ranking
scored_results = store.similar_search_with_scores(
    "nearest neighbor algorithms",
    topk=3,
    score_threshold=0.5,  # Filter out results below this similarity
)

for chunk, score in scored_results:
    print(f"  Score: {score:.4f} | {chunk.content[:60]}...")
```

### Distance Metrics

| Metric | Range | Best For |
| --- | --- | --- |
| `COSINE` | 0.0–1.0 (lower = more similar) | Text embeddings (most common) |
| `L2` | 0.0–∞ (lower = more similar) | Image feature vectors |
| `IP` | −∞–∞ (higher = more similar) | Normalized embeddings, recommendations |

## Step 4: Metadata Filtering

Combine vector similarity with attribute filters to narrow results:

```python
"""Filter search results by metadata attributes."""
from __future__ import annotations

# Filter by TAG — exact category match
# FT.SEARCH syntax: @field:{value}
database_results = store.similar_search(
    "high performance storage",
    topk=5,
    filters={"category": "database"},
)

# Filter by NUMERIC range — year between 2023 and 2024
# FT.SEARCH syntax: @field:[min max]
recent_results = store.similar_search(
    "vector search algorithms",
    topk=5,
    filters={"year": [2023, 2024]},
)

# Combined filters
filtered = store.similar_search(
    "data storage",
    topk=5,
    filters={
        "category": "database",
        "year": [2024, 2024],  # exact year match as range
    },
)
```

### Filter Syntax Reference

Under the hood, DB-GPT translates filters to `FT.SEARCH` filter expressions:

| Python Filter | FT.SEARCH Expression | Matches |
| --- | --- | --- |
| `{"category": "database"}` | `@category:{database}` | Exact tag match |
| `{"year": [2023, 2024]}` | `@year:[2023 2024]` | Numeric range (inclusive) |
| `{"category": "database", "year": [2024, 2024]}` | `@category:{database} @year:[2024 2024]` | Combined AND |

> **Security note:** Never interpolate user input directly into filter expressions.
> The `ValkeyStore` implementation handles escaping, but if you construct raw `FT.SEARCH` queries,
> always escape special characters (`,.{}[]()|-*?+$^\\`) in user-supplied values.

## Step 5: Document Management

Manage stored documents — delete by ID or clean up entire collections:

```python
"""Manage documents in the vector store."""
from __future__ import annotations

# Check if the vector store index exists
exists = store.vector_name_exists()
print(f"Index exists: {exists}")

# Delete specific documents by their IDs
store.delete_by_ids(["doc_001", "doc_002"])

# Delete the entire vector store index and all documents
store.delete_vector_name("my_collection")

# Always close the store when done to release connections
store.close()
```

## Step 6: HNSW Tuning

Tune HNSW parameters based on your workload:

| Parameter | Higher Value | Trade-off |
| --- | --- | --- |
| `hnsw_m` | More connections per node | Better recall, more memory |
| `hnsw_ef_construction` | Wider build-time search | Better index quality, slower builds |
| `hnsw_ef_runtime` | Wider query-time search | Better recall, slower queries |

### Guidelines

- **Small dataset (<10K docs):** Defaults are fine (`m=16`, `ef_construction=200`, `ef_runtime=10`)
- **Medium dataset (10K–100K):** Consider `ef_runtime=50` for better recall
- **Large dataset (>100K):** Increase `m=32`, `ef_construction=400`, `ef_runtime=100`
- **Recall-critical:** Maximize `ef_runtime` (up to `ef_construction` value)
- **Latency-critical:** Keep `ef_runtime` low (10–20) and accept slightly lower recall

```python
"""High-recall configuration for larger datasets."""
from __future__ import annotations

from dbgpt_ext.storage.vector_store.valkey_store import ValkeyVectorConfig

high_recall_config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    index_type="HNSW",
    distance_metric="COSINE",
    hnsw_m=32,
    hnsw_ef_construction=400,
    hnsw_ef_runtime=100,
)
```

## What's Next

- [LLM Caching](./03-llm-caching.md) — Cache LLM responses to reduce latency and API costs
- Explore combining vector search with DB-GPT's agent framework for multi-step RAG

---

[← Back to cookbook index](./README.md)
