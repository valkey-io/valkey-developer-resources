# AnythingLLM + Valkey

> 3 cookbooks for using Valkey as the vector database in [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm). Document ingestion, KNN retrieval, similarity-threshold filtering, pinned-source exclusion, and production operations via the `valkey-search` module and `@valkey/valkey-glide`.

## What is AnythingLLM?

[AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) is a full-stack, local-first application for building private RAG chat over your own documents. It pairs any LLM with a pluggable **vector database** provider, an embedding engine, and a document pipeline. Selecting `VECTOR_DB=valkey` makes AnythingLLM store and search embeddings in Valkey using the [`valkey-search`](https://github.com/valkey-io/valkey-search) module (`FT.CREATE` / `FT.SEARCH`, HNSW graph index, COSINE distance) through the official [`@valkey/valkey-glide`](https://github.com/valkey-io/valkey-glide) client.

The integration keeps one search index per workspace **namespace** (`allm_idx_{namespace}`) over `allm:{namespace}:` HASH keys. Each chunk is a HASH with a FLOAT32 little-endian `vector` field plus `text` and `metadata`. These cookbooks reproduce that design with small, runnable GLIDE scripts so you can understand and operate the provider without standing up the whole app.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure `VECTOR_DB=valkey`, understand the namespace storage model, and run a GLIDE mirror that creates an index, stores a chunk, and runs a KNN search. | Beginner, ~15 min, JavaScript |
| 02 | <nobr>[Vector Search & Retrieval](02-vector-search.md)</nobr> | Reproduce the retrieval path: KNN with bound PARAMS, COSINE distance to similarity, threshold + topN filtering, and pinned-source exclusion. | Intermediate, ~20 min, JavaScript |
| 03 | <nobr>[Production Operations](03-production.md)</nobr> | TLS/auth, request timeouts, the dimension-change guard, namespace deletion, bounded SCAN cleanup, reset, and cluster considerations. | Advanced, ~20 min, JavaScript |

## Runnable Sample

The [`sample/`](sample/) directory contains three Node.js scripts (one per cookbook) that run against a local Valkey. See [sample/README.md](sample/README.md) to get started.
