# Valkey with Upsonic

> Use Valkey as the vector database backend for Upsonic AI agents. Dense search, full-text search, and hybrid retrieval — all in one in-memory store.

> **⚠️ Blocked:** This cookbook depends on [Upsonic PR #607](https://github.com/Upsonic/Upsonic/pull/607) which adds the Valkey Search provider. Do not merge until that PR lands and `pip install "upsonic[valkey]"` is available on PyPI.

> **✅ Tested:** Sample code validated against Valkey 9.1 with valkey-search module v1.2.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install, connect, create an index, upsert documents, and run your first vector search. | Beginner, ~10 min, Python |
| 02 | <nobr>[Search Strategies](02-search-strategies.md)</nobr> | Dense KNN, full-text, hybrid (RRF), and tag-filtered search with tuning guidance. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Production Deployment](03-production-deployment.md)</nobr> | Cluster mode, ElastiCache, batch sizing, deduplication, and monitoring. | Advanced, ~15 min, Python |
