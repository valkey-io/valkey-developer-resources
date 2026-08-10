# Vector Store for RAG

> Store document embeddings as JSON documents with an HNSW index, run KNN similarity search via `FT.SEARCH`, and manage the index lifecycle — all runnable today via this cookbook's standalone sample.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who have completed [01 - Getting Started](01-getting-started.md) and want to understand `ValkeyVectorStore`'s schema, batch-write, and query mechanics in depth.

## What You'll Build

A complete RAG vector store backed by Valkey, following the design proposed for MetaGPT in [PR #2063](https://github.com/FoundationAgents/MetaGPT/pull/2063). You'll configure a `ValkeyVectorStore`,
store document embeddings as JSON documents with an HNSW index, run KNN similarity search via `FT.SEARCH`, and manage the index lifecycle (delete by source document, drop index). Every operation uses
the **synchronous** `glide_sync` client — no `await`, no `asyncio`.

> **Runnable today:** Steps 2 and 3 below describe the config surface proposed in PR #2063 (`ValkeyStoreConfig`, `SimpleEngine`) for reference against that PR — they are illustrative, not runnable,
since MetaGPT is not installed. Steps 4 and 5 use this cookbook's standalone [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py), which reproduces the same Valkey behavior and **is**
runnable now.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search + json modules (`valkey/valkey-bundle:9.1.0`)
- Python 3.10+ with this cookbook's [`sample/requirements.txt`](sample/requirements.txt) installed
- An embedding model that produces fixed-dimension vectors (e.g. OpenAI `text-embedding-3-small` → 1536 dims) — not required to run the sample, which uses a deterministic local embedding function

## Step 1: Understand ValkeyVectorStore

`ValkeyVectorStore` implements llama-index's `BasePydanticVectorStore` in the real upstream integration, so it slots into MetaGPT's RAG engine like any other vector store:

| Method | What It Does |
| --- | --- |
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

This cookbook's [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py) implements the same six methods against real Valkey, verified against the upstream implementation at the PR's head
commit — it just doesn't subclass `BasePydanticVectorStore`, since that base class only matters for plugging into MetaGPT's RAG engine (Step 3), which needs MetaGPT installed.

## Step 2: Configure the Store

`ValkeyStoreConfig` holds every connection and index option in the proposed upstream integration. These are the defaults from PR #2063, verified against `metagpt/rag/schema.py` at the PR head:

| Option | Default | Meaning |
| --- | --- | --- |
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
# Illustrative — requires MetaGPT installed with the Valkey RAG backend from
# PR #2063 merged and released. Not runnable against this cookbook's sample.
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

This cookbook's standalone `ValkeyVectorStore` (Step 4) takes the exact same options as constructor keyword arguments, so this configuration table doubles as its reference too.

## Step 3: Use Valkey Through the MetaGPT RAG Engine

The idiomatic path, once PR #2063 is merged and released, is to hand a `ValkeyRetrieverConfig` to MetaGPT's `SimpleEngine`. The engine builds the index, embeds your documents, and wires up retrieval.

> **Import paths**: in the proposed integration, the config classes (`ValkeyStoreConfig`, `ValkeyRetrieverConfig`) live in `metagpt.rag.schema`, while the store implementation itself is in
`metagpt.rag.vector_stores.valkey` (this cookbook's [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py) is a standalone, independently runnable reimplementation of that module).

<!-- -->

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

<!-- -->

> **Note**: This snippet is illustrative — it requires MetaGPT installed with the Valkey RAG backend from PR #2063 merged and released, a real document at `docs/valkey_overview.md`, and an embedding
model configured in MetaGPT (`config2.yaml`). It is not runnable against this cookbook's sample.

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

`similarity_top_k=3` returns the three closest chunks. Raise it for more recall, lower it for tighter, faster results. `SimpleEngine` manages the underlying store's connection internally; when you
drive `ValkeyVectorStore` yourself (next step), close it explicitly with `disconnect()`.

## Step 4: Use ValkeyVectorStore Directly

For full control you can drive the store yourself. This is also the clearest way to see the synchronous API — **and it is runnable today** against this cookbook's
[`sample/valkey_vector_store.py`](sample/valkey_vector_store.py). The store opens its GLIDE connection lazily on the first operation, so wrap usage in `try/finally` and call `disconnect()` when done.

> **`ValkeyStoreConfig` vs direct kwargs**: in the proposed upstream integration, the RAG engine (Step 3) wraps configuration in a `ValkeyStoreConfig` object, while driving `ValkeyVectorStore`
directly (below) takes the same options as keyword arguments to the constructor. This cookbook's standalone `ValkeyVectorStore` (below) only supports the direct-kwargs form, since it doesn't plug into
a `ValkeyRetrieverConfig` / RAG engine that MetaGPT would supply.

```python
"""Direct ValkeyVectorStore usage — add, query, delete.

Run this from cookbooks/framework-integrations/metagpt/sample/ with
`pip install -r requirements.txt` and Valkey running (see 01 - Getting Started).
"""
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import VectorStoreQuery

from valkey_vector_store import ValkeyVectorStore

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
    # delete() matches stored docs on ref_doc_id OR doc_id. These nodes set only
    # id_; add() stores ref_doc_id = doc_id as a fallback, so passing "doc3"
    # removes the matching document. Pass the source ref_doc_id when your nodes
    # set one explicitly (the usual case for chunked documents).
    store.delete("doc3")
finally:
    store.disconnect()  # closes the GLIDE client
```

Because the client is synchronous, `store.add(...)` and `store.query(...)` block until Valkey responds — there are no coroutines to await.

This exact sequence (plus more assertions and a full lifecycle) runs in [`sample/main.py`](sample/main.py) — run `python sample/main.py` to see it live.

## Step 5: Manage the Index Lifecycle

`drop_index()` removes the `FT.SEARCH` index and cleans up every key under the configured prefix using `SCAN` (it never calls the blocking `KEYS` command). This is also runnable today via the
standalone sample:

```python
"""Drop the index and clean up all stored documents."""
from valkey_vector_store import ValkeyVectorStore

store = ValkeyVectorStore(index_name="metagpt_demo", prefix="metagpt:demo:", vector_dimensions=4)
try:
    store.drop_index()  # FT.DROPINDEX + SCAN/DELETE of orphaned keys
    print("Index dropped and keys cleaned up")
finally:
    store.disconnect()
```

`drop_index()` is safe to call on the first run before any index exists: it checks `FT._LIST` first and skips `FT.DROPINDEX` when the index is absent, then runs the `SCAN`/`DEL` cleanup (a no-op when
there are no keys). That makes it a reliable idempotent reset at the top of a script —
[`sample/test_valkey_vector_store.py`](sample/test_valkey_vector_store.py) asserts this explicitly via
`test_drop_index_is_safe_on_first_run_before_any_index_exists`.

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
| --- | --- | --- |
| `ensure_index()` | `FT.CREATE metagpt_rag ON JSON PREFIX 1 metagpt:rag: SCHEMA $.vector AS vector VECTOR HNSW ...` | Built over JSON documents |
| `add(nodes)` | `JSON.SET metagpt:rag:<doc_id> $ <json>` batched via GLIDE's `Batch(is_atomic=True)` (up to 100 writes per batch, `client.exec(batch, raise_on_error=True)`) | All-or-nothing per batch, one round trip |
| `query(...)` | `FT.SEARCH metagpt_rag "*=>[KNN 3 @vector $query_vec AS score]" PARAMS 2 query_vec <bytes>` | Vector packed with `struct.pack` |
| `delete(ref_doc_id)` | `SCAN` + `JSON.GET` to match, then `DEL` | Removes all chunks of a source |
| `drop_index()` | `FT.DROPINDEX` + `SCAN`/`DEL` | Cleans orphaned keys too |

The KNN query string `*=>[KNN 3 @vector $query_vec AS score]` asks for the 3 nearest neighbors of `$query_vec` along the `vector` field, returning the distance as `score`. For `COSINE` the store
converts distance to similarity as `1.0 - score`.

> ⚠️ **Query injection**: the query above is safe because the filter is hardcoded (`*`) and the vector is passed as a bound parameter (`$query_vec`) via `FtSearchOptions(params=...)`, never
interpolated into the query string. Never interpolate unsanitized user input into an `FT.SEARCH` query string. The `=>` token separates the filter expression from the KNN clause, so a crafted filter
like `@category:{user_input}=>[KNN ...]` can be exploited for injection. Verified against `query()` in both the upstream `metagpt/rag/vector_stores/valkey.py` and this cookbook's
`sample/valkey_vector_store.py` — the filter portion is always the hardcoded `*`.

<!-- -->

> **Cluster mode**: `add()` writes each batch as an atomic GLIDE `Batch(is_atomic=True)` — a single round-trip transaction, all-or-nothing. In Valkey Cluster, every key in a transaction must hash to
the same slot, but the document keys (`metagpt:rag:<doc_id>`) carry no hash tags and will scatter across slots. The atomic-batch path therefore works in **standalone mode only**; run Valkey
standalone for this integration unless the keys are given a common hash tag. Verified against the key-building logic in both `add()` implementations — `key = f"{self.prefix}{doc_id}"`, with no
hash-tag braces.

## HNSW vs FLAT Index

| Aspect | HNSW (default) | FLAT |
| --- | --- | --- |
| Search strategy | Approximate nearest-neighbor, optimized for low-latency search on large datasets | Exact nearest-neighbor; work scales with the number of stored vectors |
| Accuracy | Approximate (high recall) | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Production (>1000 docs) | Small datasets or testing (<1000 docs) |

Switch by setting `vector_algorithm="FLAT"` in `ValkeyStoreConfig` (or, for the standalone sample, the `ValkeyVectorStore` constructor). The backend selects the matching field attributes
automatically, so a FLAT index is never built with HNSW parameters.

## Choosing a Distance Metric

| Metric | Use When | Similarity Conversion |
| --- | --- | --- |
| `COSINE` | Normalized embeddings (most LLM models) | `similarity = 1.0 - score` |
| `L2` | Euclidean distance matters | `similarity = -score` |
| `IP` | Inner product / dot-product models | `similarity = -score` |

For `L2` and `IP`, the store negates the raw distance (`similarity = -score`) rather than mapping it into `[0, 1]`. This is deliberate: negating preserves the correct ranking order (smaller
distance → larger similarity) so results sort consistently across all three metrics. The absolute values are not normalized — treat them as relative scores for ranking, not as calibrated
probabilities.

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | — | `localhost` | Valkey server host |
| `port` | — | `6379` | Valkey server port |
| `password` | — | `None` | Auth password (omit for local) |
| `use_tls` | — | `False` | Enable TLS (set `True` off localhost) |
| `request_timeout` | — | `5000` | Request timeout in milliseconds |
| `index_name` | — | `metagpt_rag` | Name of the `FT.SEARCH` index |
| `prefix` | — | `metagpt:rag:` | Key prefix for stored documents |
| `vector_dimensions` | — | `1536` | Embedding dimension — must match your model |
| `distance_metric` | — | `COSINE` | `COSINE`, `L2`, or `IP` |
| `vector_algorithm` | — | `HNSW` | `HNSW` (fast, approximate) or `FLAT` (exact) |
| `client_name` | — | `metagpt_rag_client` | Connection name shown in `CLIENT LIST` |

## Troubleshooting

| Issue | Solution |
| --- | --- |
| `ModuleNotFoundError: No module named 'glide_sync'` | Install the sync client: `pip install valkey-glide-sync==2.5.0` (or `pip install -r sample/requirements.txt`) |
| `ModuleNotFoundError: No module named 'llama_index'` | Run `pip install -r sample/requirements.txt`; confirm you're on Python 3.10+ |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:9.1.0` (includes the search module) |
| `Query embedding dimension N does not match index dimension` | Set `vector_dimensions` to your embedding model's output size |
| `Request timed out` | Increase `request_timeout` (default 5000ms) for non-local servers |
| Empty query results right after `add()` | Valkey indexing is near-real-time; poll `FT.INFO` or retry briefly |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production →](03-production.md)
