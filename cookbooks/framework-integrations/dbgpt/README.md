# DB-GPT + Valkey

> 3 cookbooks for using Valkey as a high-performance vector store and LLM response cache in DB-GPT — the open-source AI-native data application framework.

## What is DB-GPT?

[DB-GPT](https://github.com/eosphoros-ai/DB-GPT) is a production-ready framework for building AI-native data applications. It provides multi-model management, RAG pipelines, multi-agent orchestration, and a plugin system for storage backends. Valkey integrates as both a **vector store** (for RAG/semantic search) and an **LLM response cache** (for reducing inference latency and costs).

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install DB-GPT with Valkey support, start Valkey with the search module, and configure your first vector store. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Store for RAG](02-vector-store.md)</nobr> | Use `ValkeyStore` for embedding storage with HNSW indexing and similarity search in DB-GPT's RAG pipeline. | Intermediate, ~20 min, Python |
| 03 | <nobr>[LLM Response Caching](03-llm-caching.md)</nobr> | Use `ValkeyCacheStorage` to cache LLM responses with TTL, reducing inference latency from seconds to sub-millisecond. | Intermediate, ~20 min, Python |
