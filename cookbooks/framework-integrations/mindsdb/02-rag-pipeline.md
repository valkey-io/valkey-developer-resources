# RAG Pipeline with Vector Search

**Intermediate** · Python · ~20 min

## What You'll Build

A complete RAG (Retrieval-Augmented Generation) pipeline using the MindsDB Valkey handler. You'll store document embeddings in Valkey with HNSW indexing, perform KNN similarity searches, filter by metadata, and manage the document lifecycle — all through the handler's Python API.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module (`valkey/valkey-bundle:latest`)
- `valkey-glide` and `numpy` installed

## Step 1: Project Setup

All code in this cookbook lives in the `example/` directory and can be run directly:

```bash
cd cookbooks/framework-integrations/mindsdb/example
pip install valkey-glide numpy
python main.py
```

## Step 2: Create the Handler and Index

```python
"""Create a ValkeyHandler and vector index."""
import numpy as np
import pandas as pd
from mindsdb.integrations.handlers.valkey_handler.valkey_handler import ValkeyHandler
from mindsdb.integrations.libs.vectordatabase_handler import FilterCondition, FilterOperator, TableField

# Initialize the handler with 384-dimensional vectors (matches all-MiniLM-L6-v2)
handler = ValkeyHandler(
    name="rag_valkey",
    connection_data={
        "host": "localhost",
        "port": 6379,
        "vector_dimension": 384,
        "distance_metric": "COSINE",
        "prefix": "doc:",
    },
)

# Verify connection
status = handler.check_connection()
assert status.success, f"Connection failed: {status.error_message}"
print("Connected to Valkey!")

# Create the vector index
INDEX_NAME = "rag_documents"
handler.create_table(INDEX_NAME, if_not_exists=True)
print(f"Index '{INDEX_NAME}' ready")
```

## Step 3: Insert Documents with Embeddings

```python
"""Insert documents with vector embeddings."""

# In production, embeddings come from a model like sentence-transformers.
# Here we use random vectors for demonstration.
VECTOR_DIM = 384

documents = [
    {
        "id": "doc_001",
        "content": "Valkey is a high-performance in-memory data store that supports vector similarity search.",
        "metadata": {"source": "valkey_docs", "category": "overview"},
    },
    {
        "id": "doc_002",
        "content": "HNSW indexes provide approximate nearest neighbor search with sub-millisecond latency.",
        "metadata": {"source": "valkey_docs", "category": "indexing"},
    },
    {
        "id": "doc_003",
        "content": "MindsDB brings machine learning into databases using a SQL-like interface.",
        "metadata": {"source": "mindsdb_docs", "category": "overview"},
    },
    {
        "id": "doc_004",
        "content": "The valkey-glide client uses a Rust core for high-throughput async operations.",
        "metadata": {"source": "valkey_docs", "category": "client"},
    },
    {
        "id": "doc_005",
        "content": "Knowledge bases in MindsDB use vector stores for semantic document retrieval.",
        "metadata": {"source": "mindsdb_docs", "category": "rag"},
    },
]

# Generate embeddings (in production, use a real embedding model)
np.random.seed(42)
for doc in documents:
    doc["embeddings"] = np.random.randn(VECTOR_DIM).astype(np.float32).tolist()

# Create DataFrame for insertion
df = pd.DataFrame(documents)
handler.insert(INDEX_NAME, df)
print(f"Inserted {len(documents)} documents into '{INDEX_NAME}'")
```

## Step 4: KNN Vector Similarity Search

```python
"""Perform KNN vector search — find documents most similar to a query vector."""

# Generate a query vector (in production, embed the user's question)
query_vector = np.random.randn(VECTOR_DIM).astype(np.float32).tolist()

# Search for top 3 most similar documents
conditions = [
    FilterCondition(
        column=TableField.SEARCH_VECTOR.value,
        op=FilterOperator.EQUAL,
        value=query_vector,
    )
]

results = handler.select(
    table_name=INDEX_NAME,
    columns=["id", "content", "distance"],
    conditions=conditions,
    limit=3,
)

print(f"\nKNN Search Results (top 3):")
print(f"{'─' * 60}")
for _, row in results.iterrows():
    print(f"  [{row.get('distance', 'N/A'):.4f}] {row['id']}")
    print(f"    {row['content'][:80]}...")
    print()
```

## Step 5: Select by ID

```python
"""Look up specific documents by ID."""

# Single document lookup
conditions = [
    FilterCondition(
        column=TableField.ID.value,
        op=FilterOperator.EQUAL,
        value="doc_001",
    )
]

result = handler.select(
    table_name=INDEX_NAME,
    columns=["id", "content", "metadata"],
    conditions=conditions,
)
print(f"Single lookup: {result.iloc[0]['content'][:60]}...")

# Batch lookup by multiple IDs
conditions = [
    FilterCondition(
        column=TableField.ID.value,
        op=FilterOperator.IN,
        value=["doc_001", "doc_003", "doc_005"],
    )
]

results = handler.select(
    table_name=INDEX_NAME,
    columns=["id", "content"],
    conditions=conditions,
)
print(f"\nBatch lookup: {len(results)} documents found")
for _, row in results.iterrows():
    print(f"  {row['id']}: {row['content'][:50]}...")
```

## Step 6: Delete Documents

```python
"""Delete documents by ID."""

# Delete a single document
conditions = [
    FilterCondition(
        column=TableField.ID.value,
        op=FilterOperator.EQUAL,
        value="doc_005",
    )
]
handler.delete(INDEX_NAME, conditions)
print("Deleted doc_005")

# Delete multiple documents
conditions = [
    FilterCondition(
        column=TableField.ID.value,
        op=FilterOperator.IN,
        value=["doc_003", "doc_004"],
    )
]
handler.delete(INDEX_NAME, conditions)
print("Deleted doc_003 and doc_004")

# Verify remaining documents
tables = handler.get_tables()
print(f"\nRemaining indexes: {tables.data_frame['table_name'].tolist()}")
```

## Step 7: Drop the Index

```python
"""Clean up — drop the index and all associated data."""
handler.drop_table(INDEX_NAME)
print(f"Dropped index '{INDEX_NAME}' and all its documents")

handler.disconnect()
print("Disconnected from Valkey")
```

## How It Works Under the Hood

| Operation | Valkey Command | Typical Latency |
|-----------|---------------|-----------------|
| Create index | `FT.CREATE rag_documents ON HASH PREFIX 1 doc:rag_documents: SCHEMA content TEXT id TAG embeddings VECTOR HNSW ... metadata TEXT` | ~1ms |
| Insert document | `HSET doc:rag_documents:doc_001 id "doc_001" content "..." embeddings <bytes> metadata "{...}"` | ~0.1ms |
| KNN search | `FT.SEARCH rag_documents "*=>[KNN 3 @embeddings $query_vec]" PARAMS 2 query_vec <bytes> DIALECT 2` | ~0.5ms |
| ID lookup | `HGETALL doc:rag_documents:doc_001` | ~0.1ms |
| Delete | `UNLINK doc:rag_documents:doc_001` | ~0.1ms |
| Drop index | `FT.DROPINDEX rag_documents` + SCAN/UNLINK keys | ~1ms |

## HNSW vs FLAT Index

The handler creates HNSW indexes by default:

| Parameter | HNSW (default) | FLAT |
|-----------|----------------|------|
| Speed | Sub-millisecond | Scales linearly with data |
| Accuracy | Approximate (~99%+ recall) | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Production (>1000 docs) | Small datasets or testing |

## SQL Usage with MindsDB

When using the full MindsDB server, the same operations are available via SQL:

```sql
-- Create connection
CREATE DATABASE my_valkey
WITH ENGINE = 'valkey',
PARAMETERS = {"host": "localhost", "port": 6379, "vector_dimension": 384};

-- Vector similarity search
SELECT id, content, distance
FROM my_valkey.rag_documents
WHERE search_vector = (SELECT embeddings FROM my_model WHERE content = 'query text')
LIMIT 5;

-- Insert documents
INSERT INTO my_valkey.rag_documents (id, content, embeddings, metadata)
VALUES ('doc1', 'Hello world', '[0.1, 0.2, ...]', '{"source": "web"}');

-- Delete by ID
DELETE FROM my_valkey.rag_documents WHERE id = 'doc1';

-- Drop the index
DROP TABLE my_valkey.rag_documents;
```

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| Insert (single) | ~0.1ms | HSET one hash key |
| Insert (batch 1000) | ~50ms | Sequential HSET calls |
| KNN search (10K docs) | <1ms | HNSW approximate |
| KNN search (1M docs) | ~2-5ms | HNSW approximate |
| ID lookup | ~0.1ms | Direct HGETALL |
| Full scan (fallback) | ~10-100ms | SCAN + HGETALL per key |

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `RequestError: Index already exists` | Re-creating existing index | Use `if_not_exists=True` (default) |
| Empty search results | No documents or wrong index | Check with `get_tables()` and insert data |
| `Connection refused` | Valkey not running | Start Valkey: `podman start valkey-search` |
| High distance scores | Vectors not normalized | Use COSINE metric (handles normalization) |
| `NOAUTH` error | Password required | Add `password` to connection_data |

[← Back: 01 Getting Started](01-getting-started.md)
