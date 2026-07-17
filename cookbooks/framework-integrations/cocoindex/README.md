# CocoIndex + Valkey

> 2 cookbooks for using Valkey as an incremental vector store target in
> CocoIndex — the open-source framework for building continuously-fresh data
> pipelines for AI agents. Demonstrates declarative indexing with HNSW vector
> search, incremental updates (only the Δ is reprocessed), and semantic search
> queries via `valkey-glide`.

**Who is this for:** Python developers building RAG pipelines who want
incremental document updates and Valkey Search without adding a hosted service.

## What is CocoIndex?

[CocoIndex](https://github.com/cocoindex-io/cocoindex) is an open-source
Python framework for building incremental data pipelines that keep AI agent
context fresh. It tracks source changes and only reprocesses the delta, which
is useful for RAG pipelines where documents change frequently. Valkey
integrates as a **vector store target** with HNSW vector search.

The default path uses the local sample in [`sample/`](sample/), SQLite for
CocoIndex state, the public `all-MiniLM-L6-v2` embedding model, and
`valkey/valkey-bundle:9.1.1`. It does not require an API key or cloud account.
The sample is an integration example, not a benchmark.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install CocoIndex with Valkey support, start Valkey with the search module, configure the connector, and run your first incremental indexing pipeline. | Beginner, ~15 min, Python |
| 02 | <nobr>[RAG Pipeline with Incremental Sync](02-rag-pipeline.md)</nobr> | Build a full RAG pipeline: chunk documents, embed with sentence-transformers, store in Valkey with HNSW indexing, and query with KNN vector search — all with incremental updates. | Intermediate, ~20 min, Python |
