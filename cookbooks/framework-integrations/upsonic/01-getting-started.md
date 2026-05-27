# Getting Started with Upsonic + Valkey

> Connect Upsonic's vector database layer to Valkey, store document embeddings, and run your first similarity search — all in under 10 minutes.

**Beginner** · Python · ~10 min

[Upsonic](https://github.com/Upsonic/Upsonic) is a Python framework for building autonomous AI agents. Its pluggable vector database layer supports multiple backends — Valkey provides ultra-low-latency in-memory vector search with native hybrid capabilities (vector + full-text + tag filtering in a single query).

## Prerequisites

- Docker installed (for Valkey)
- Python 3.10+

## Step 1: Start Valkey

The Valkey Search module is required for vector indexing. Use `valkey/valkey-bundle` which includes it:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1
```

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should include: name search
```

## Step 2: Install Dependencies

```bash
pip install "upsonic[valkey]"
```

This installs Upsonic with the `valkey-glide` client library.

## Step 3: Configure and Connect

```python
import asyncio
from upsonic.vectordb import ValkeyProvider, ValkeyConfig
from upsonic.vectordb.config import ConnectionConfig, Mode, DistanceMetric

config = ValkeyConfig(
    vector_size=384,              # Must match your embedding model's dimensions
    collection_name="my_docs",    # Name for the FT index
    key_prefix="doc:",           # Prefix for hash keys in Valkey
    connection=ConnectionConfig(
        mode=Mode.LOCAL,
        host="localhost",
        port=6379,
    ),
    distance_metric=DistanceMetric.COSINE,
)

provider = ValkeyProvider(config)
```

## Step 4: Create the Index and Upsert Documents

```python
async def index_documents():
    await provider.aconnect()
    await provider.acreate_collection()

    # Upsert documents (vectors would come from your embedding model)
    await provider.aupsert(
        vectors=[
            [0.1] * 384,
            [0.2] * 384,
            [0.3] * 384,
        ],
        ids=["chunk_1", "chunk_2", "chunk_3"],
        chunks=[
            "Valkey is a high-performance in-memory data store",
            "Vector search enables semantic similarity matching",
            "HNSW provides fast approximate nearest neighbor search",
        ],
        document_ids=["doc_1", "doc_1", "doc_2"],
        document_names=["valkey_intro.md", "valkey_intro.md", "vector_search.md"],
    )
    print("Indexed 3 chunks")
    await provider.adisconnect()

asyncio.run(index_documents())
```

Each chunk is stored as a Valkey Hash key (`doc:chunk_1`, `doc:chunk_2`, etc.) with fields for the vector, content, and metadata. The FT index enables search across all of them.

## Step 5: Search by Vector Similarity

```python
async def search():
    await provider.aconnect()

    query_vector = [0.15] * 384  # Replace with your embedded query
    results = await provider.adense_search(
        query_vector=query_vector,
        top_k=2,
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.id}: {r.text}")

    await provider.adisconnect()

asyncio.run(search())
```

Output:

```
[0.998] chunk_1: Valkey is a high-performance in-memory data store
[0.994] chunk_2: Vector search enables semantic similarity matching
```

## Sync API

Every async method has a sync counterpart (drop the `a` prefix). Useful for scripts and notebooks:

```python
provider = ValkeyProvider(config)
provider.connect()
provider.create_collection()

provider.upsert(
    vectors=[[0.1] * 384],
    ids=["chunk_1"],
    chunks=["Valkey is a high-performance in-memory data store"],
    document_ids=["doc_1"],
    document_names=["valkey_intro.md"],
)

import time
time.sleep(0.3)  # Valkey Search indexes asynchronously; brief pause ensures results are searchable

results = provider.dense_search(query_vector=[0.15] * 384, top_k=2)
for r in results:
    print(f"[{r.score:.3f}] {r.id}: {r.text}")

provider.delete_collection()
provider.disconnect()
```

## What's Happening in Valkey?

After indexing, you can inspect the data directly:

```bash
# List all FT indexes
docker exec valkey valkey-cli FT._LIST

# Inspect the index schema
docker exec valkey valkey-cli FT.INFO my_docs

# View a stored document
docker exec valkey valkey-cli HGETALL doc:chunk_1
```

Each hash key contains:
- `vector` — float32 binary blob (the embedding)
- `content` — full text of the chunk (full-text indexed)
- `chunk_id`, `document_id`, `document_name` — TAG fields for filtering
- `chunk_content_hash` — MD5 for deduplication

## Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vector_size` | — | Embedding dimensions (must match your model) |
| `collection_name` | — | FT index name |
| `key_prefix` | `"doc:"` | Prefix for hash keys |
| `distance_metric` | `COSINE` | `COSINE`, `EUCLIDEAN`, or `DOT_PRODUCT` |
| `index` | HNSW(m=16, ef_construction=200) | Index type and parameters |
| `batch_size` | 100 | Max documents per upsert batch |
| `cluster_mode` | false | Use `GlideClusterClient` |
| `request_timeout` | None | GLIDE request timeout (ms) |
| `rrf_k` | 60 | Reciprocal Rank Fusion constant for hybrid search |
| `ef_runtime` | None | HNSW query-time search width (overrides default for FT.SEARCH) |

---

[02 - Search Strategies →](02-search-strategies.md)
