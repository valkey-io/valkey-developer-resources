# Production Configuration for AgentScope + Valkey

> Configure cluster mode, TLS, HNSW tuning parameters, metadata filtering, and batch operations for production deployments.

**Intermediate** · Python · ~15 min

This cookbook covers the configuration options you'll need when moving from local development to production: cluster mode for horizontal scaling, TLS for security, HNSW parameter tuning for recall/performance trade-offs, and operational patterns for managing large document collections.

## Cluster Mode

For high-availability deployments, connect to a Valkey cluster:

```python
from agentscope.rag import ValkeyStore

store = ValkeyStore(
    host="valkey-cluster.example.com",
    port=6379,
    index_name="production_idx",
    prefix="prod:doc:",
    dimensions=1536,
    distance="COSINE",
    use_cluster=True,
)
```

When `use_cluster=True`, the store uses `GlideClusterClient` which handles slot-based routing and automatic failover.

## TLS Encryption

Enable TLS for encrypted connections:

```python
store = ValkeyStore(
    host="valkey.example.com",
    port=6380,
    index_name="secure_idx",
    prefix="secure:doc:",
    dimensions=1536,
    distance="COSINE",
    use_tls=True,
)
```

For custom TLS configuration (client certificates, CA bundles), pass additional options via `client_kwargs`:

```python
store = ValkeyStore(
    host="valkey.example.com",
    port=6380,
    index_name="secure_idx",
    prefix="secure:doc:",
    dimensions=1536,
    distance="COSINE",
    use_tls=True,
    use_cluster=True,
    client_kwargs={
        "client_cert": "/path/to/client.crt",
        "client_key": "/path/to/client.key",
    },
)
```

## HNSW Tuning

The HNSW algorithm has three key parameters that control the recall/performance trade-off:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `hnsw_m` | 16 | Max edges per node. Higher = better recall, more memory |
| `hnsw_ef_construction` | 200 | Vectors examined during indexing. Higher = better recall, slower writes |
| `hnsw_ef_runtime` | 10 | Vectors examined during search. Higher = better recall, slower reads |

### High-Recall Configuration

For use cases where accuracy matters more than latency (e.g., legal document search):

```python
store = ValkeyStore(
    host="localhost",
    port=6379,
    index_name="high_recall_idx",
    prefix="hr:doc:",
    dimensions=1536,
    distance="COSINE",
    hnsw_m=16,
    hnsw_ef_construction=200,
    hnsw_ef_runtime=20,
)
```

### High-Throughput Configuration

For use cases where latency matters more than perfect recall (e.g., semantic caching):

```python
store = ValkeyStore(
    host="localhost",
    port=6379,
    index_name="fast_idx",
    prefix="fast:doc:",
    dimensions=1536,
    distance="COSINE",
    hnsw_m=8,
    hnsw_ef_construction=100,
    hnsw_ef_runtime=5,
    initial_cap=100000,  # Pre-allocate for expected document count
)
```

The `initial_cap` parameter pre-allocates memory for the expected number of vectors, avoiding resizing during bulk ingestion.

## Metadata Filtering

ValkeyStore indexes `doc_id` as a Tag field and `chunk_id` as a Numeric field. Use these in filter expressions during search:

### Filter by Document ID

```python
results = await store.search(
    query_embedding=query_vec,
    limit=10,
    filter_expression="@doc_id:{user_manual}",
)
```

### Filter by Multiple Document IDs

Run separate queries per doc_id and combine results:

```python
results = []
for doc_id in ["user_manual", "api_reference"]:
    r = await store.search(
        query_embedding=query_vec,
        limit=10,
        filter_expression=f"@doc_id:{{{doc_id}}}",
    )
    results.extend(r)
```

> **Note:** The pipe-separated OR syntax (`@doc_id:{a | b}`) is not supported in all versions of the Valkey Search module. Use separate queries for compatibility.

### Filter by Chunk Range

```python
# Only search the first 5 chunks of each document (e.g., introductions)
results = await store.search(
    query_embedding=query_vec,
    limit=10,
    filter_expression="@chunk_id:[0 4]",
)
```

### Combine Filters

```python
results = await store.search(
    query_embedding=query_vec,
    limit=10,
    filter_expression="@doc_id:{user_manual} @chunk_id:[0 10]",
)
```

## Batch Ingestion

For large document collections, add documents in batches to manage memory:

```python
import asyncio
from agentscope.rag import ValkeyStore, Document, DocMetadata
from agentscope.message import TextBlock

BATCH_SIZE = 100


async def ingest_large_corpus(store: ValkeyStore, all_documents: list[Document]):
    """Ingest documents in batches."""
    for i in range(0, len(all_documents), BATCH_SIZE):
        batch = all_documents[i:i + BATCH_SIZE]
        await store.add(batch)
        print(f"Ingested {min(i + BATCH_SIZE, len(all_documents))}/{len(all_documents)}")
```

## Managing Indexes

### Drop and Recreate

When you need to change the schema (dimensions, distance metric, or indexed fields):

```python
async def recreate_index(store: ValkeyStore):
    """Drop the existing index and let ValkeyStore recreate it on next use."""
    await store.drop_index()
    # The index will be recreated on the next add() or search() call
```

> **Note:** `drop_index()` removes the search index but does not delete the underlying Hash keys. Documents remain in Valkey and will be re-indexed when a new index is created with the same prefix.

### Access the Underlying Client

For advanced operations not covered by the ValkeyStore API:

```python
async def get_index_info(store: ValkeyStore):
    """Get information about the current index."""
    client = await store._get_client()
    info = await client.custom_command(["FT.INFO", store.index_name])
    return info
```

## Connection Lifecycle

Always close the store when done to release the connection:

```python
async def main():
    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="my_idx",
        prefix="my:doc:",
        dimensions=1536,
        distance="COSINE",
    )
    try:
        await store.add(documents)
        results = await store.search(query_embedding, limit=5)
    finally:
        await store.close()
```

For web applications, create the store once at startup and close it on shutdown:

```python
# FastAPI example
from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="app_idx",
        prefix="app:doc:",
        dimensions=1536,
        distance="COSINE",
    )
    yield
    await app.state.store.close()

app = FastAPI(lifespan=lifespan)
```

---

[← 02 - RAG Pipeline](02-rag-pipeline.md)
