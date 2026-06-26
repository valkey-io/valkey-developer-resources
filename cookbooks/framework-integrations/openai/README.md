# OpenAI + Valkey

> 2 cookbooks for using Valkey as a vector database with OpenAI embeddings. Demonstrates semantic vector search, hybrid (TAG filter + KNN) queries, and FLAT vs HNSW indexing over JSON documents via `valkey-glide`.

## What is OpenAI + Valkey?

[OpenAI embeddings](https://platform.openai.com/docs/guides/embeddings) turn text into dense vectors that capture meaning. [Valkey Search](https://valkey.io/topics/search/) is an open-source Valkey module that adds native vector similarity search and secondary indexing — delivering single-digit millisecond latency over Valkey Hash and JSON data.

Together they let you build semantic search and RAG workloads on a single, fast, open-source datastore: embed your text with OpenAI, store and index the vectors in Valkey, and query by meaning.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect to Valkey, create a JSON vector index, store documents, and run your first KNN vector search with OpenAI embeddings. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Search](02-vector-search.md)</nobr> | Hybrid search combining a TAG pre-filter with KNN, plus the HNSW index for fast approximate search on larger datasets. | Intermediate, ~20 min, Python |
