# Getting Started with AgentScope + Valkey

> Use ValkeyStore to give AgentScope agents vector similarity search backed by Valkey's Search module with HNSW indexing via the valkey-glide async client.

**Beginner** · Python · ~15 min

AgentScope is a multi-agent framework that supports RAG (Retrieval-Augmented Generation) through pluggable vector store backends. The `ValkeyStore` implementation uses Valkey's Search module with HNSW indexing for fast, scalable vector similarity search.

## What Gets Stored

Documents are stored as Valkey Hash keys with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `vector` | Binary (FLOAT32) | The embedding vector as a little-endian binary blob |
| `doc_id` | Tag | Document identifier for filtering and deletion |
| `chunk_id` | Numeric | Chunk index within a document |
| `metadata` | JSON string | Full document metadata including content |

Keys follow the pattern `{prefix}{uuid}` where the UUID is deterministically generated from the document content.

## Prerequisites

- Docker installed
- Python 3.10+
- An embedding model (Amazon Bedrock, HuggingFace, or any provider AgentScope supports)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

The `valkey-bundle` image includes the Search module required for vector indexing.

## Step 2: Install Dependencies

> **Note:** `ValkeyStore` is not yet in a released version of AgentScope. Until the [upstream PR](https://github.com/MatthiasHowellYopp/agentscope/pull/1) is merged, install from the feature branch:

```bash
pip install "agentscope[valkey] @ git+https://github.com/MatthiasHowellYopp/agentscope.git@feat/valkey-vector-store"
pip install "valkey-glide>=2.1.0,<2.4.0"
```

Once released, this will simplify to:

```bash
pip install agentscope[valkey]
```

## Step 3: Create a ValkeyStore

```python
import asyncio
from agentscope.rag import ValkeyStore

store = ValkeyStore(
    host="localhost",
    port=6379,
    index_name="my_docs",
    prefix="agentscope:doc:",
    dimensions=3,        # Match your embedding model's output dimensions
    distance="COSINE",   # COSINE, L2, or IP
)
```

The store lazily connects to Valkey and creates the search index on first use.

## Step 4: Add Documents

```python
from agentscope.rag import Document, DocMetadata
from agentscope.message import TextBlock

documents = [
    Document(
        embedding=[0.1, 0.2, 0.3],
        metadata=DocMetadata(
            content=TextBlock(type="text", text="Valkey is a high-performance key-value store."),
            doc_id="doc1",
            chunk_id=0,
            total_chunks=2,
        ),
    ),
    Document(
        embedding=[0.9, 0.1, 0.4],
        metadata=DocMetadata(
            content=TextBlock(type="text", text="Valkey supports vector similarity search."),
            doc_id="doc1",
            chunk_id=1,
            total_chunks=2,
        ),
    ),
]

asyncio.run(store.add(documents))
```

## Step 5: Search by Vector Similarity

```python
async def search_example():
    results = await store.search(
        query_embedding=[0.15, 0.25, 0.35],
        limit=3,
        score_threshold=0.8,
    )
    for doc in results:
        print(f"Score: {doc.score:.4f} — {doc.metadata.content['text']}")

asyncio.run(search_example())
```

Output:

```
Score: 0.9974 — Valkey is a high-performance key-value store.
```

The `score_threshold` filters out results below the given similarity score. For COSINE distance, scores range from 0 to 1 (higher = more similar).

## Step 6: Delete Documents

Delete all chunks belonging to a document by its `doc_id`:

```python
asyncio.run(store.delete(ids="doc1"))
```

> **Known issue:** On some versions of `valkey-glide`, `delete()` may fail with a "Missing `=>`" error due to how the underlying `FT.SEARCH` query is constructed. This is tracked in the [upstream PR](https://github.com/MatthiasHowellYopp/agentscope/pull/1) and will be fixed before release.

## Step 7: Clean Up

```python
async def cleanup():
    await store.drop_index()  # Remove the search index
    await store.close()       # Close the connection

asyncio.run(cleanup())
```

## Distance Metrics

| Metric | Score Interpretation | Best For |
|--------|---------------------|----------|
| `COSINE` | 1.0 = identical direction, 0.0 = orthogonal | Text embeddings (most common) |
| `L2` | Higher = more similar (inverted internally) | Image embeddings |
| `IP` | Higher = more similar | Normalized embeddings |

---

[02 - RAG Pipeline →](02-rag-pipeline.md)
