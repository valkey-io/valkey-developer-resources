# LangChain + Valkey

> 4 cookbooks for using Valkey as the complete persistence layer for LangGraph agents - checkpointing, semantic caching, and vector search through the official langgraph-checkpoint-aws package.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `langgraph-checkpoint-aws[valkey]`, connect to Valkey, and persist your first LangGraph agent with `ValkeySaver`. | Beginner, ~15 min, Python |
| 02 | <nobr>[LLM Response Caching](02-llm-caching.md)</nobr> | Cache repeatable LangChain results with `ValkeyCache`, including per-entry TTLs. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Semantic Search with ValkeyStore](03-semantic-search.md)</nobr> | Store documents with local embeddings and search by meaning using HNSW indexes and `ValkeyStore`. | Intermediate, ~20 min, Python |
| 04 | <nobr>[Full Agent - All Three Components](04-full-agent.md)</nobr> | Wire `ValkeySaver` + `ValkeyStore` + `ValkeyCache` together in a local LangGraph flow with semantic caching and checkpointing. | Advanced, ~25 min, Python |
