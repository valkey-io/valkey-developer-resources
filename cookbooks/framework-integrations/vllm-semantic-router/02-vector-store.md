# Vector Store Backend with Valkey

> Use Valkey as the vLLM Semantic Router's RAG vector store — a dedicated FT index per collection, KNN search with `file_id` TAG pre-filtering, and batched chunk ingestion through `valkey-glide`.

**Intermediate** · Go / YAML · ~20 min

**Who is this for:** Platform engineers running the vLLM Semantic Router who want retrieval-augmented generation
(RAG) document storage and per-file-scoped similarity search backed by Valkey instead of a separate vector database.

Beyond caching, the router can retrieve document chunks for Retrieval-Augmented Generation. The vector store backend
added in [PR #1671](https://github.com/vllm-project/semantic-router/pull/1671) lets Valkey hold those embeddings,
so the entire router can run on Valkey when memory is disabled. Each vector-store collection becomes its own
HNSW-indexed FT index, and searches can be scoped to a single source file.

## What You'll Build

A Valkey-backed vector store that:

- Creates and drops per-collection indexes (`CreateCollection` / `DeleteCollection`)
- Inserts embedded chunks as HASH documents (`InsertChunks`)
- Runs KNN similarity search with an optional `file_id` filter (`Search`)
- Deletes all chunks for a file in pages (`DeleteByFileID`)

## Prerequisites

- Completed [01 - Semantic Cache Backend](01-getting-started.md) (Valkey running with the Search module)
- **Go 1.24+** (for the sample)
- **Docker or Podman**
- The `github.com/valkey-io/valkey-glide/go/v2` client (pulled by the sample's `go.mod`)

If Valkey isn't running yet:

```bash
# Docker
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:9.1.0
```

```bash
# Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:9.1.0
```

## Step 1: Configure the Vector Store Backend

The vector store config is a flat block (no sub-sections) under `global.stores.vector_store`, matching the `ValkeyVectorStoreConfig` schema from PR #1671:

```yaml
global:
  stores:
    vector_store:
      enabled: true
      backend_type: valkey       # memory | milvus | llama_stack | valkey
      valkey:
        host: localhost
        port: 6379
        database: 0
        # password: ""           # omit or leave empty for no auth
        connect_timeout: 10       # connection timeout in seconds
        collection_prefix: "vsr_vs_"  # prefix for hash keys and index names
        metric_type: COSINE        # COSINE | L2 | IP
        index_m: 16                # HNSW M parameter
        index_ef_construction: 200 # HNSW efConstruction (build-time search width)
```

The `collection_prefix` keeps the router's vector-store keys and indexes namespaced. For a collection `store123`,
the backend derives:

- index name → `vsr_vs_store123_idx`
- key prefix → `vsr_vs_store123:`
- a chunk key → `vsr_vs_store123:<chunkID>`

## Step 2: The Per-Collection Index Schema

Creating a collection issues an `FT.CREATE` like this:

```text
FT.CREATE vsr_vs_store123_idx ON HASH PREFIX 1 vsr_vs_store123: SCHEMA
  id          TAG
  file_id     TAG
  filename    TAG
  content     TEXT
  chunk_index NUMERIC
  created_at  NUMERIC
  embedding   VECTOR HNSW 10 TYPE FLOAT32 DIM <dimension> DISTANCE_METRIC COSINE M 16 EF_CONSTRUCTION 200
```

`file_id` is a TAG field, which is what makes scoped retrieval and per-file deletion efficient — you can filter a KNN search to a single document.

## Step 3: KNN Search with a Metadata Filter

The backend builds a filtered KNN query by wrapping the filter expression in parentheses ahead of the KNN clause:

```text
FT.SEARCH vsr_vs_store123_idx "(@file_id:{f2})=>[KNN 3 @embedding $BLOB AS vector_distance]"
  PARAMS 2 BLOB <query-embedding-bytes>
  RETURN 5 file_id filename content chunk_index vector_distance
  LIMIT 0 3
  DIALECT 2
```

When no filter is supplied the expression is just `*`, giving a plain KNN over the whole collection. The returned
`vector_distance` is converted to a similarity score (`1 - d/2` for cosine); results below the `threshold` are
dropped during parsing, and the remaining matches are then sorted best-first.

## Step 4: Run the Vector Store Sample

The [`sample/`](sample/) program seeds a small collection of country facts, runs a few semantic searches, and then
a filtered search restricted to one file. It uses deterministic stub embeddings so it runs anywhere without a GPU
or model download.

```bash
cd sample
go run . vectorstore
```

Expected output (scores will vary slightly with the stub embeddings):

```text
✓ Connected to Valkey at localhost:6379
== vLLM Semantic Router — Valkey vector store demo ==
✓ Created collection "demo" (dimension=256)
✓ Inserted 5 chunks
→ Query: "capital of France"
  #1 [0.77] france.txt: The capital of France is Paris, known for the Eiffel Tower.
  #2 [0.71] japan.txt: Tokyo is the capital of Japan, one of the most populous c...
  #3 [0.69] germany.txt: Berlin is the capital of Germany, famous for the Brandenb...
→ Query: "German engineering"
  #1 [0.75] germany.txt: Germany is the largest economy in Europe and a leader in ...
  #2 [0.59] germany.txt: Berlin is the capital of Germany, famous for the Brandenb...
  #3 [0.57] france.txt: France is a country in Western Europe with a rich cultura...
→ Filtered query (file_id=f2 only): "capital city"
  #1 [0.64] germany.txt: Berlin is the capital of Germany, famous for the Brandenb...
  #2 [0.54] germany.txt: Germany is the largest economy in Europe and a leader in ...
✓ Deleted collection "demo"
```

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
|-----------|---------------|-------|
| Create collection | `FT.CREATE vsr_vs_<id>_idx ON HASH PREFIX 1 vsr_vs_<id>: SCHEMA ...` | One HNSW index per collection |
| Check existence | `FT.INFO vsr_vs_<id>_idx` | Errors with "not found" when absent |
| Insert chunk | `HSET vsr_vs_<id>:<chunkID> id ... file_id ... embedding <bytes>` | Embedding stored as little-endian FLOAT32 |
| Search | `FT.SEARCH ... "(<filter>)=>[KNN k @embedding $BLOB AS vector_distance]"` | Filter is `*` or `@file_id:{...}` |
| Delete by file | `FT.SEARCH @file_id:{<id>} ... LIMIT 0 1000` then `DEL` | Paged: re-query offset 0 until empty |
| Drop collection | `FT.DROPINDEX vsr_vs_<id>_idx` then SCAN + `DEL` | `valkey-search` has no `DD` flag, so keys are cleaned via SCAN |

Note the deletion pattern: because dropping the index does not delete the underlying HASH keys, the backend follows
up with a `SCAN` + `DEL` sweep over the collection prefix. It never uses `KEYS` (which would block the server) —
only cursor-based `SCAN`.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `FT.CREATE failed` on an existing collection | The index is already present. Use a new collection ID or call `DeleteCollection` first. |
| `invalid file_id filter: contains disallowed characters` (router only — not reproduced in this sample) | The full router backend rejects filter values with unsafe characters to prevent query injection. This sample instead escapes special characters via `escapeTagValue` (see [`keys.go`](sample/keys.go)) rather than rejecting them outright. |
| Search returns nothing right after insert | Indexing is asynchronous. Allow a short delay (the sample sleeps ~500 ms) before searching. |
| `ERR unknown command 'FT.CREATE'` | The Search module is not loaded — use `valkey/valkey-bundle`. |
| Wrong result ordering | The backend re-sorts by score descending after parsing, since Go map iteration over the GLIDE response loses FT.SEARCH's native order. |

---

[← 01 - Semantic Cache Backend](01-getting-started.md) · [03 - Agentic Memory Backend →](03-agentic-memory.md)
