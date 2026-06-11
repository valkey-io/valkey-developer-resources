# MetaGPT + Valkey

> 2 cookbooks for using Valkey as a RAG vector store backend in MetaGPT — the multi-agent framework where LLM-based roles collaborate like a software company.

## What is MetaGPT?

[MetaGPT](https://github.com/geekan/MetaGPT) is a multi-agent framework that assigns roles (product manager, architect, engineer) to LLMs so they collaborate on complex tasks. Its RAG module supports pluggable vector stores through a `ConfigBasedFactory` pattern (the same pattern used by FAISS, Chroma, and Elasticsearch). Valkey plugs in as a **vector store** for retrieval-augmented generation: store document embeddings with HNSW or FLAT indexing and run sub-millisecond KNN similarity search.

The integration uses the **synchronous** `valkey-glide` client (the `glide_sync` module, shipped as the `valkey-glide-sync` package) to stay consistent with MetaGPT's other synchronous RAG backends.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install MetaGPT with Valkey RAG support, start Valkey with the search module, and connect with the synchronous GLIDE client. | Beginner, ~15 min, Python |
| 02 | <nobr>[Vector Store for RAG](02-vector-store-rag.md)</nobr> | Use `ValkeyVectorStore` to store embeddings as JSON documents with an HNSW index and run KNN similarity search via `FT.SEARCH`. | Intermediate, ~20 min, Python |
