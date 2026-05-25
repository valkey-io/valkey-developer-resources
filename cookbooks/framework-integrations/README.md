# Framework Integrations

Production-ready integrations for popular AI agent frameworks. Checkpointing, caching, vector search, and memory - all backed by Valkey.

| Framework | Description |
| --- | --- |
| <nobr>[Mem0](mem0/)</nobr> | Intelligent memory layer for AI agents with a dedicated `valkey` provider. Per-user memories, vector search, and HNSW indexing. |
| <nobr>[LangChain / LangGraph](langchain/)</nobr> | Use Valkey as the complete persistence layer for LangGraph agents - checkpointing, semantic caching, and vector search - through the official `langgraph-checkpoint-aws` package. |
| <nobr>[CrewAI](crewai/)</nobr> | Give CrewAI agents persistent, searchable memory backed by Valkey. Custom `ValkeyStorage` backend with GLIDE client, vector search, and Amazon Bedrock embeddings. |
| <nobr>[Strands Agents](strands/)</nobr> | Use the official `strands-valkey-session-manager` community package to back Strands agents with Valkey - persisting conversation history, session metadata, and agent state across invocations. |
| <nobr>[Haystack](haystack/)</nobr> | Use `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack pipeline components for sub-millisecond RAG retrieval. |
| <nobr>[DB-GPT](dbgpt/)</nobr> | Use Valkey as a vector store for RAG pipelines and an LLM response cache in DB-GPT. HNSW indexing, metadata filtering, and sub-millisecond cache reads via `valkey-glide`. |
| <nobr>[DocsGPT](docs-gpt/)</nobr> | Use Valkey as the vector store backend in DocsGPT for document retrieval (RAG). HNSW indexing, source isolation via TAG filtering, and bulk ingestion with `valkey-glide`. |
| <nobr>[CocoIndex](cocoindex/)</nobr> | Build incremental RAG pipelines with Valkey as the vector store target. Declarative indexing with automatic HNSW search, incremental sync (only Δ reprocessed), and semantic queries via `valkey-glide`. |
| <nobr>[BetterDB](betterdb-agent-cache/)</nobr> | Two packages for Valkey-backed LLM caching. `@betterdb/semantic-cache` — Valkey-native vector similarity cache. `@betterdb/agent-cache` — multi-tier LLM, tool, and session cache with LangGraph support. |
