# Vector Store for RAG

**Intermediate** · Python · ~20 min

## What You'll Build

A complete RAG (Retrieval-Augmented Generation) pipeline using Valkey as the vector store in DB-GPT. You'll store document embeddings with HNSW indexing and perform sub-millisecond similarity searches to ground LLM responses in your own data.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module (`valkey/valkey-bundle:latest`)
- An embedding model configured (OpenAI, Bedrock, or HuggingFace)

## Step 1: Understand ValkeyStore

DB-GPT's `ValkeyStore` implements the `VectorStoreBase` interface, providing:

| Method | What It Does |
|--------|--------------|
| `load_document(chunks)` | Embeds and stores document chunks with metadata |
| `similar_search(text, topk)` | Find the most similar documents by meaning |
| `similar_search_with_scores(text, topk, threshold)` | Search with relevance score filtering |
| `delete_by_ids(ids)` | Remove specific documents |
| `vector_name_exists()` | Check if the index already exists and has data |
| `delete_vector_name(name)` | Drop the index and all associated keys |

Under the hood, it uses:
- **HSET** to store documents as Valkey hashes (content + embedding + metadata fields)
- **FT.CREATE** to build a vector index (HNSW or FLAT) over the hash fields
- **FT.SEARCH** with KNN queries for similarity search

## Step 2: Configure ValkeyVectorConfig

```python
from dbgpt_ext.storage.vector_store.valkey_store import ValkeyVectorConfig

config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    # password="your-password",   # or set VALKEY_PASSWORD env var
    index_type="HNSW",             # "HNSW" (fast, approximate) or "FLAT" (exact)
    distance_metric="COSINE",      # "COSINE", "L2", or "IP"
    key_prefix="dbgpt_vec:",       # prefix for all keys in Valkey
    # HNSW tuning parameters
    hnsw_m=16,                     # connections per node (higher = more accurate)
    hnsw_ef_construction=200,      # build-time quality factor
    hnsw_ef_runtime=10,            # query-time quality factor
    # Optional: define metadata fields for filtered search
    metadata_schema={
        "source": "tag",           # string field (exact match filtering)
        "page": "numeric",         # numeric field (range filtering)
    },
)
```

Or use TOML configuration:

```toml
[rag.storage.vector]
type = "valkey"
host = "localhost"
port = 6379
index_type = "HNSW"
distance_metric = "COSINE"
hnsw_m = 16
hnsw_ef_construction = 200
hnsw_ef_runtime = 10
```

## Step 3: Create the ValkeyStore

```python
"""Create a ValkeyStore with an embedding function."""
from dbgpt_ext.storage.vector_store.valkey_store import ValkeyStore, ValkeyVectorConfig


# You need an embedding function — here's a simple example using OpenAI
# In production, use DB-GPT's configured embedding model
from dbgpt.core import Embeddings


class OpenAIEmbeddings(Embeddings):
    """Simple OpenAI embeddings wrapper."""

    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# Create the config
config = ValkeyVectorConfig(
    host="localhost",
    port=6379,
    index_type="HNSW",
    distance_metric="COSINE",
    metadata_schema={"source": "tag", "page": "numeric"},
)

# Create the store
embedding_fn = OpenAIEmbeddings()
store = ValkeyStore(
    vector_store_config=config,
    name="my_knowledge_base",  # Collection/index name
    embedding_fn=embedding_fn,
)
```

## Step 4: Load Documents

```python
"""Load document chunks into the Valkey vector store."""
from dbgpt.core import Chunk

# Create document chunks (in production, these come from DB-GPT's text splitter)
chunks = [
    Chunk(
        content="Valkey is a high-performance in-memory data store forked from Redis.",
        metadata={"source": "valkey_docs", "page": 1},
        chunk_id="chunk_001",
    ),
    Chunk(
        content="HNSW indexes provide approximate nearest neighbor search with "
                "sub-millisecond latency and high recall.",
        metadata={"source": "valkey_docs", "page": 5},
        chunk_id="chunk_002",
    ),
    Chunk(
        content="DB-GPT supports multiple vector stores including ChromaDB, Milvus, "
                "Elasticsearch, and Valkey.",
        metadata={"source": "dbgpt_docs", "page": 12},
        chunk_id="chunk_003",
    ),
    Chunk(
        content="The valkey-search module enables full-text search, vector similarity "
                "search, and geospatial queries on Valkey data structures.",
        metadata={"source": "valkey_docs", "page": 8},
        chunk_id="chunk_004",
    ),
]

# Load into Valkey — this embeds the text and stores everything
stored_ids = store.load_document(chunks)
print(f"Stored {len(stored_ids)} chunks: {stored_ids}")
```

This single call:
1. Creates the HNSW index if it doesn't exist (auto-detects embedding dimension)
2. Generates embeddings for all chunk content
3. Stores each chunk as a Valkey hash with content, metadata, and vector fields

> **Note**: Steps 5–7 below assume you still have the `store` instance open from Step 4. When you're done searching, call `store.close()` as shown in Step 8.

## Step 5: Similarity Search

```python
"""Search for documents similar to a query."""

# Basic similarity search — returns top 3 most relevant chunks
results = store.similar_search("What is Valkey?", topk=3)

print(f"Found {len(results)} results:\n")
for chunk in results:
    print(f"  Score: {chunk.score:.4f}")
    print(f"  Content: {chunk.content[:80]}...")
    print(f"  Metadata: {chunk.metadata}")
    print()
```

## Step 6: Search with Score Threshold

```python
"""Search with a minimum relevance score."""

# Only return results with similarity score >= 0.7
results = store.similar_search_with_scores(
    text="vector similarity search performance",
    topk=5,
    score_threshold=0.7,
)

print(f"Results above threshold (score >= 0.7): {len(results)}\n")
for chunk in results:
    print(f"  [{chunk.score:.4f}] {chunk.content[:60]}...")
```

## Step 7: Metadata Filtering

Filter search results by metadata fields (requires `metadata_schema` in config):

```python
"""Search with metadata filters."""
from dbgpt.storage.vector_store.filters import MetadataFilters, MetadataFilter, FilterOperator

# Filter: only search documents from "valkey_docs" source
filters = MetadataFilters(
    filters=[
        MetadataFilter(key="source", value="valkey_docs", operator=FilterOperator.EQ),
    ]
)

results = store.similar_search("search capabilities", topk=3, filters=filters)
print(f"Filtered results (source=valkey_docs): {len(results)}")
for chunk in results:
    print(f"  [{chunk.score:.4f}] {chunk.content[:60]}...")
    assert chunk.metadata.get("source") == "valkey_docs"


# Filter: pages greater than 5
page_filter = MetadataFilters(
    filters=[
        MetadataFilter(key="page", value=5, operator=FilterOperator.GT),
    ]
)

results = store.similar_search("Valkey features", topk=3, filters=page_filter)
print(f"\nFiltered results (page > 5): {len(results)}")
for chunk in results:
    print(f"  [{chunk.score:.4f}] page={chunk.metadata.get('page')} {chunk.content[:50]}...")
```

## Step 8: Manage the Store

```python
"""Collection management operations."""

# Check if the index exists and has data
exists = store.vector_name_exists()
print(f"Index has data: {exists}")

# Delete specific chunks by ID
deleted = store.delete_by_ids("chunk_001,chunk_002")
print(f"Deleted: {deleted}")

# Truncate all data (keeps the index, removes documents)
store.truncate()

# Delete the entire index and all keys
store.delete_vector_name("my_knowledge_base")

# Clean up the client connection
store.close()
```

## How It Works Under the Hood

| Operation | Valkey Command | Typical Latency |
|-----------|---------------|-----------------|
| Store document | `HSET dbgpt_vec:my_kb:chunk_001 content "..." vector <bytes> metadata "{...}"` | ~0.1ms |
| Create index | `FT.CREATE idx:my_kb ON HASH PREFIX 1 dbgpt_vec:my_kb: SCHEMA vector VECTOR HNSW ...` | ~1ms |
| KNN search | `FT.SEARCH idx:my_kb "*=>[KNN 5 @vector $vec]" PARAMS 2 vec <bytes>` | ~0.5ms |
| Filtered search | `FT.SEARCH idx:my_kb "@meta_source:{valkey_docs}=>[KNN 5 @vector $vec]" ...` | ~0.5ms |
| Delete doc | `DEL dbgpt_vec:my_kb:chunk_001` | ~0.1ms |
| Drop index | `FT.DROPINDEX idx:my_kb` | ~0.1ms |

## HNSW vs FLAT Index

| Parameter | HNSW (default) | FLAT |
|-----------|----------------|------|
| Speed | Sub-millisecond | Scales linearly with data |
| Accuracy | Approximate (~99%+ recall) | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Production (>1000 docs) | Small datasets or testing |

To switch to FLAT index:

```python
config = ValkeyVectorConfig(
    index_type="FLAT",
    # ... other settings
)
```

## HNSW Tuning Guide

| Parameter | Default | Effect |
|-----------|---------|--------|
| `hnsw_m` | 16 | More connections = better recall, more memory |
| `hnsw_ef_construction` | 200 | Higher = slower build, better index quality |
| `hnsw_ef_runtime` | 10 | Higher = slower queries, better recall |

For most RAG workloads, the defaults work well. Increase `hnsw_ef_runtime` to 50-100 if you need higher recall at the cost of latency.

## Environment Variables

All config values can be set via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | localhost | Valkey server host |
| `VALKEY_PORT` | 6379 | Valkey server port |
| `VALKEY_PASSWORD` | None | Authentication password |
| `VALKEY_INDEX_TYPE` | HNSW | Index algorithm |
| `VALKEY_DISTANCE_METRIC` | COSINE | Distance metric |
| `VALKEY_KEY_PREFIX` | dbgpt_vec: | Key prefix |
| `VALKEY_REQUEST_TIMEOUT` | 5000 | Timeout in ms |

[← Previous: 01 Getting Started](01-getting-started.md) | [Next: 03 LLM Caching →](03-llm-caching.md)
