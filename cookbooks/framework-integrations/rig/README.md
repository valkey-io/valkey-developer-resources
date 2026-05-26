# Rig + Valkey

> 3 cookbooks for using the `rig-redis` vector store crate to power Rig agents with Valkey-backed vector similarity search — storing embeddings, running KNN queries, and filtering results.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `rig-redis`, create a `RedisVectorStore`, connect to Valkey, and run your first KNN similarity search. | Beginner, ~15 min, Rust |
| 02 | <nobr>[Vector Search](02-vector-search.md)</nobr> | Insert documents with embeddings, query with `top_n` and `top_n_ids`, apply score thresholds, and build a RAG pipeline with Rig agents. | Intermediate, ~20 min, Rust |
| 03 | <nobr>[Filters & Production](03-filters-and-production.md)</nobr> | Use RediSearch filter syntax for metadata filtering, combine filters with AND/OR/NOT, and configure for production with connection management and TLS. | Intermediate, ~15 min, Rust |
