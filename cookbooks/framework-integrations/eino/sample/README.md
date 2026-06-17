# Eino + Valkey Sample

Runnable sample proving the cookbook code works end-to-end.

> **⚠️ Blocked on upstream:** This sample cannot build until the eino-ext Valkey components
> are [merged and released](https://github.com/cloudwego/eino-ext) (branch: `feat/valkey-indexer-retriever`).
> Once released, update `go.mod` to reference the published versions and regenerate `go.sum`:
> ```bash
> go get github.com/cloudwego/eino-ext/components/indexer/valkey@latest
> go get github.com/cloudwego/eino-ext/components/retriever/valkey@latest
> go mod tidy
> ```

## Prerequisites

1. Valkey 9.1+ with Search module:
   ```bash
   docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
   ```
   Or with podman:
   ```bash
   podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
   ```

2. Create the search index (`6` = count of the parameter tokens that follow: TYPE, FLOAT32, DIM, 4, DISTANCE_METRIC, COSINE):
   ```bash
   docker exec valkey valkey-cli FT.CREATE my_index ON HASH PREFIX 1 doc: SCHEMA \
     content TEXT vector_content VECTOR HNSW 6 TYPE FLOAT32 DIM 4 DISTANCE_METRIC COSINE
   ```

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
