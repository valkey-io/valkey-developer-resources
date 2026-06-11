# Vector Store for RAG

**Intermediate** · Python · ~20 min

## What You'll Build

A complete RAG vector store backed by Valkey for MetaGPT. You'll configure `ValkeyVectorStore`, store document embeddings as JSON documents with an HNSW index, run KNN similarity search via `FT.SEARCH`, and manage the index lifecycle (delete by source document, drop index). Every operation uses the **synchronous** `glide_sync` client — no `await`, no `asyncio`.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search + json modules (`valkey/valkey-bundle:latest`)
- MetaGPT installed from the Valkey feature branch (see cookbook 01)
- An embedding model that produces fixed-dimension vectors (e.g. OpenAI `text-embedding-3-small` → 1536 dims)

## Step 1: Understand ValkeyVectorStore

`ValkeyVectorStore` implements llama-index's `BasePydanticVectorStore`, so it slots into MetaGPT's RAG engine like any other vector store:

| Method | What It Does |
|--------|--------------|
| `ensure_index()` | Create the `FT.SEARCH` index if it doesn't already exist |
| `add(nodes)` | Store embedding nodes as JSON documents in atomic batches |
| `query(VectorStoreQuery)` | KNN similarity search, returns nodes + scores |
| `delete(ref_doc_id)` | Remove all chunks belonging to a source document |
| `drop_index()` | Drop the index and clean up all prefixed keys |
| `scan_all_docs()` | List all stored document keys (via `SCAN`, never `KEYS`) |

Under the hood it uses:
- **`JSON.SET`** to store each node as a JSON document (`text`, `doc_id`, `ref_doc_id`, `metadata`, `vector`)
- **`FT.CREATE`** to build a vector index (HNSW or FLAT) over the JSON path `$.vector`
- **`FT.SEARCH`** with a `KNN` clause for similarity search

## Step 2: Configure the Store

`ValkeyStoreConfig` holds every connection and index option. These are the defaults from the integration:

| Option | Default | Meaning |
|--------|---------|---------|
| `host` | `"localhost"` | Valkey server host |
| `port` | `6379` | Valkey server port |
| `password` | `None` | Auth password (omit for local) |
| `use_tls` | `False` | Enable TLS (set `True` off localhost) |
| `request_timeout` | `5000` | Request timeout in ms (GLIDE default is 250ms — too low for non-local) |
| `index_name` | `"metagpt_rag"` | Name of the `FT.SEARCH` index |
| `prefix` | `"metagpt:rag:"` | Key prefix for stored documents |
| `vector_dimensions` | `1536` | Embedding dimension — must match your model |
| `distance_metric` | `"COSINE"` | `COSINE`, `L2`, or `IP` |
| `vector_algorithm` | `"HNSW"` | `HNSW` (fast, approximate) or `FLAT` (exact) |
| `client_name` | `"metagpt_rag_client"` | Connection name shown in `CLIENT LIST` |

```python
from metagpt.rag.schema import ValkeyStoreConfig

store_config = ValkeyStoreConfig(
    host="localhost",
    port=6379,
    index_name="metagpt_rag",
    prefix="metagpt:rag:",
    vector_dimensions=1536,    # match your embedding model's output dimension
    distance_metric="COSINE",  # COSINE, L2, or IP
    vector_algorithm="HNSW",   # HNSW for production, FLAT for exact/small datasets
)
```

## Step 3: Use Valkey Through the MetaGPT RAG Engine

The idiomatic path is to hand a `ValkeyRetrieverConfig` to MetaGPT's `SimpleEngine`. The engine builds the index, embeds your documents, and wires up retrieval.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

> **Note**: This snippet is illustrative — it assumes you have a real document at `docs/valkey_overview.md` and an embedding model configured in MetaGPT (`config2.yaml`). Adjust the path and config to your project before running.

```python
"""Build a RAG engine backed by Valkey."""
from metagpt.rag.engines import SimpleEngine
from metagpt.rag.schema import ValkeyRetrieverConfig, ValkeyStoreConfig

store_config = ValkeyStoreConfig(
    index_name="metagpt_rag",
    vector_dimensions=1536,  # must match the embedding model configured in MetaGPT
)

# from_docs() embeds each document and stores it in Valkey via JSON.SET,
# then creates the FT.SEARCH index if needed.
engine = SimpleEngine.from_docs(
    input_files=["docs/valkey_overview.md"],  # replace with your own document(s)
    retriever_configs=[ValkeyRetrieverConfig(store_config=store_config, similarity_top_k=3)],
)

# Retrieve the most relevant chunks for a query (KNN search via FT.SEARCH)
nodes = engine.retrieve("What indexing algorithms does Valkey support?")
for node in nodes:
    print(f"[{node.score:.4f}] {node.text[:80]}...")
```

`similarity_top_k=3` returns the three closest chunks. Raise it for more recall, lower it for tighter, faster results. `SimpleEngine` manages the underlying store's connection internally; when you drive `ValkeyVectorStore` yourself (next step), close it explicitly with `disconnect()`.

## Step 4: Use ValkeyVectorStore Directly

For full control you can drive the store yourself. This is also the clearest way to see the synchronous API. The store opens its GLIDE connection lazily on the first operation, so wrap usage in `try/finally` and call `disconnect()` when done.

```python
"""Direct ValkeyVectorStore usage — add, query, delete."""
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import VectorStoreQuery
from metagpt.rag.vector_stores.valkey import ValkeyVectorStore

# In real code, embeddings come from your model. These 4-dim vectors are
# illustrative only; set vector_dimensions to match whatever you pass in.
store = ValkeyVectorStore(
    host="localhost",
    port=6379,
    index_name="metagpt_demo",
    prefix="metagpt:demo:",
    vector_dimensions=4,
    distance_metric="COSINE",
    vector_algorithm="HNSW",
)

try:
    store.ensure_index()  # creates the FT.SEARCH index if absent

    # --- Add nodes (stored as JSON documents in atomic batches of 100) ---
    nodes = [
        TextNode(text="Valkey supports HNSW and FLAT vector indexes.",
                 embedding=[1.0, 0.0, 0.0, 0.0], id_="doc1"),
        TextNode(text="FT.SEARCH runs KNN similarity queries.",
                 embedding=[0.9, 0.1, 0.0, 0.0], id_="doc2"),
        TextNode(text="Unrelated content about the weather.",
                 embedding=[0.0, 0.0, 1.0, 1.0], id_="doc3"),
    ]
    ids = store.add(nodes)
    print(f"Stored {len(ids)} documents")

    # --- KNN query (top_k nearest by cosine similarity) ---
    result = store.query(
        VectorStoreQuery(query_embedding=[1.0, 0.0, 0.0, 0.0], similarity_top_k=2)
    )
    for node, score in zip(result.nodes, result.similarities):
        print(f"[{score:.4f}] {node.text}")

    # --- Delete every chunk belonging to a source document ---
    store.delete("doc3")
finally:
    store.disconnect()  # closes the GLIDE client
```

Because the client is synchronous, `store.add(...)` and `store.query(...)` block until Valkey responds — there are no coroutines to await.

## Step 5: Manage the Index Lifecycle

`drop_index()` removes the `FT.SEARCH` index and cleans up every key under the configured prefix using `SCAN` (it never calls the blocking `KEYS` command):

```python
"""Drop the index and clean up all stored documents."""
from metagpt.rag.vector_stores.valkey import ValkeyVectorStore

store = ValkeyVectorStore(index_name="metagpt_demo", prefix="metagpt:demo:", vector_dimensions=4)
try:
    store.drop_index()  # FT.DROPINDEX + SCAN/DELETE of orphaned keys
    print("Index dropped and keys cleaned up")
finally:
    store.disconnect()
```

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
|-----------|---------------|-------|
| `ensure_index()` | `FT.CREATE metagpt_rag ON JSON PREFIX 1 metagpt:rag: SCHEMA $.vector AS vector VECTOR HNSW ...` | Built over JSON documents |
| `add(nodes)` | `JSON.SET metagpt:rag:<doc_id> $ <json>` (atomic `MULTI`/`EXEC` batches of 100) | All-or-nothing per batch |
| `query(...)` | `FT.SEARCH metagpt_rag "*=>[KNN 3 @vector $query_vec AS score]" PARAMS 2 query_vec <bytes>` | Vector packed with `struct.pack` |
| `delete(ref_doc_id)` | `SCAN` + `JSON.GET` to match, then `DEL` | Removes all chunks of a source |
| `drop_index()` | `FT.DROPINDEX` + `SCAN`/`DEL` | Cleans orphaned keys too |

The KNN query string `*=>[KNN 3 @vector $query_vec AS score]` asks for the 3 nearest neighbors of `$query_vec` along the `vector` field, returning the distance as `score`. For `COSINE` the store converts distance to similarity as `1.0 - score`.

## HNSW vs FLAT Index

| Aspect | HNSW (default) | FLAT |
|--------|----------------|------|
| Speed | Sub-millisecond | Scales linearly with data |
| Accuracy | Approximate (high recall) | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Production (>1000 docs) | Small datasets or testing |

Switch by setting `vector_algorithm="FLAT"` in `ValkeyStoreConfig`. The backend selects the matching field attributes automatically, so a FLAT index is never built with HNSW parameters.

## Choosing a Distance Metric

| Metric | Use When | Similarity Conversion |
|--------|----------|----------------------|
| `COSINE` | Normalized embeddings (most LLM models) | `similarity = 1.0 - score` |
| `L2` | Euclidean distance matters | `similarity = -score` |
| `IP` | Inner product / dot-product models | `similarity = -score` |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'glide_sync'` | Install the sync client: `pip install "valkey-glide-sync>=2.1.0,<3.0.0"` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` (includes the search module) |
| `Query embedding dimension N does not match index dimension` | Set `vector_dimensions` to your embedding model's output size |
| `Request timed out` | Increase `request_timeout` (default 5000ms) for non-local servers |
| Empty query results right after `add()` | Valkey indexing is near-real-time; poll `FT.INFO` or retry briefly |

[← Previous: 01 Getting Started](01-getting-started.md)
