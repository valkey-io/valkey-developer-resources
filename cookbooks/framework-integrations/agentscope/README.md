# AgentScope + Valkey

> 3 cookbooks for using Valkey as the vector store backend for AgentScope's RAG pipeline — HNSW-indexed vector search, document storage, and metadata filtering via the valkey-glide async client.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `agentscope[valkey]`, connect to Valkey, store document embeddings, and run your first vector similarity search. | Beginner, ~15 min, Python |
| 02 | <nobr>[RAG Pipeline](02-rag-pipeline.md)</nobr> | Chunk documents, generate embeddings, store them in Valkey, and retrieve relevant context for an AgentScope LLM agent. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Configuration](03-production.md)</nobr> | Configure cluster mode, TLS, HNSW tuning (M, ef_construction, ef_runtime), metadata filtering, and batch operations. | Intermediate, ~15 min, Python |
