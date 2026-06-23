# Unstructured + Valkey

> 3 cookbooks for using Valkey as a vector store destination for document ingestion pipelines — transform PDFs, HTML, and Word docs into searchable vector embeddings stored in Valkey with HNSW indexes.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `unstructured-ingest[valkey]`, start Valkey, and configure the Valkey destination connector. | Beginner, ~10 min, Python |
| 02 | <nobr>[Document Ingestion & Search](02-ingestion-and-search.md)</nobr> | End-to-end pipeline: partition a PDF, embed chunks, store in Valkey, and query with KNN vector search. | Intermediate, ~25 min, Python |
| 03 | <nobr>[Production Deployment](03-production.md)</nobr> | Deploy with ElastiCache, TLS, TTL lifecycle, HNSW tuning, cluster mode, and monitoring. | Advanced, ~20 min, Python |
