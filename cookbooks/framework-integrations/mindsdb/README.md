# MindsDB + Valkey Vector Store

> 2 cookbooks for using Valkey as a vector store in MindsDB — the open-source AI platform for building AI applications with enterprise data. Demonstrates connecting Valkey as a vector database, storing embeddings with HNSW indexing, and performing KNN similarity search via `valkey-glide`.

## What is MindsDB?

[MindsDB](https://github.com/mindsdb/mindsdb) is an open-source AI platform that brings machine learning into databases using a SQL-like interface. The Valkey handler integrates as a **vector store backend**, enabling:

- **Sub-millisecond vector search** — HNSW indexing with cosine, L2, or inner product distance
- **SQL interface** — create indexes, insert embeddings, and search using familiar SQL syntax
- **Knowledge Base support** — use Valkey as the vector store for MindsDB Knowledge Bases
- **valkey-glide client** — high-performance async Rust-core client with Python bindings

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect MindsDB to Valkey, create a vector index, insert documents, and run your first similarity search — all via SQL. | Beginner, ~15 min, Python/SQL |
| 02 | <nobr>[RAG Pipeline with Vector Search](02-rag-pipeline.md)</nobr> | Build a complete RAG pipeline: embed documents, store in Valkey with HNSW indexing, query with KNN vector search, and use metadata filtering. | Intermediate, ~20 min, Python |
