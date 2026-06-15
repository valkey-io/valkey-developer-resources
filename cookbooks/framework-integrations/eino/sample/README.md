# Eino + Valkey Sample

Runnable sample proving the cookbook code works end-to-end.

> **⚠️ Pre-merge note:** This sample uses `replace` directives in `go.mod` pointing to a local
> checkout of [eino-ext](https://github.com/cloudwego/eino-ext) on the `feat/valkey-indexer-retriever`
> branch. Before merging this PR, update `go.mod` to reference the released versions and run
> `go mod tidy` to generate a proper `go.sum`.

## Prerequisites

1. Valkey 9.1+ with Search module:
   ```bash
   docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
   ```

2. Create the search index:
   ```bash
   docker exec valkey valkey-cli FT.CREATE my_index ON HASH PREFIX 1 doc: SCHEMA \
     content TEXT vector_content VECTOR HNSW 6 TYPE FLOAT32 DIM 4 DISTANCE_METRIC COSINE
   ```

3. Clone [eino-ext](https://github.com/cloudwego/eino-ext) and checkout `feat/valkey-indexer-retriever`:
   ```bash
   git clone https://github.com/cloudwego/eino-ext.git
   cd eino-ext && git checkout feat/valkey-indexer-retriever
   ```
   Then update the `replace` paths in `go.mod` to point to your local clone.

## Run

```bash
CGO_ENABLED=1 go run .
```

Expected output:

```
✓ Indexed 3 documents: [1 2 3]

Query: "What is Valkey?"
---
  ID: doc:1 | Distance: 2 | Valkey is a high-performance in-memory data store forked from Redis.
  ID: doc:2 | Distance: 2 | Vector search enables finding semantically similar documents.
  ID: doc:3 | Distance: 0 | Eino is a Go framework for building AI applications by CloudWeGo.
```

> **Note:** This sample uses a deterministic hash-based mock embedder. Distances are not
> semantically meaningful — the point is to prove the index/retrieve pipeline works. Replace
> `mockEmbedder` with a real embedding model (e.g., OpenAI, Ollama) for meaningful results.
> See the cookbook's getting-started guide for real-embedder examples.
