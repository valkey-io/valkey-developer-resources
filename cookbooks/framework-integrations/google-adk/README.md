# Google ADK + Valkey

> 3 cookbooks for using Valkey as the vector memory backend for Google ADK agents. Demonstrates semantic memory storage, KNN retrieval, and production deployment via `valkey-glide`.

## What is Google ADK?

[Google Agent Development Kit (ADK)](https://github.com/google/adk-python) is an open-source framework for building AI agents with tool use, multi-turn conversations, and persistent memory. The [adk-python-community](https://github.com/google/adk-python-community) repo provides community-contributed extensions including the `ValkeyMemoryService`.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `google-adk-community[valkey]`, connect to Valkey, and store your first agent memories with vector embeddings. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Memory Search](02-vector-memory-search.md)</nobr> | Build a semantic memory retrieval pipeline with KNN search, TAG pre-filtering, distance thresholds, and batch ingestion. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Patterns](03-production.md)</nobr> | TTL-based expiry, cluster mode, TLS, monitoring, and performance tuning for production ADK + Valkey deployments. | Advanced, ~15 min, Python |
