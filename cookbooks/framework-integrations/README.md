# Framework Integrations

Production-ready integrations for popular AI agent frameworks. Checkpointing, caching, vector search, and memory - all backed by Valkey.

| Framework | Description |
| --- | --- |
| <nobr>[Mem0](mem0/)</nobr> | Intelligent memory layer for AI agents with a dedicated `valkey` provider. Per-user memories, vector search, and HNSW indexing. |
| <nobr>[LangChain / LangGraph](langchain/)</nobr> | Use Valkey as the complete persistence layer for LangGraph agents - checkpointing, semantic caching, and vector search - through the official `langgraph-checkpoint-aws` package. |
| <nobr>[CrewAI](crewai/)</nobr> | Give CrewAI agents persistent, searchable memory backed by Valkey. Custom `ValkeyStorage` backend with GLIDE client, vector search, and Amazon Bedrock embeddings. |
| <nobr>[Strands Agents](strands/)</nobr> | Use the official `strands-valkey-session-manager` community package to back Strands agents with Valkey - persisting conversation history, session metadata, and agent state across invocations. |
| <nobr>[Haystack](haystack/)</nobr> | Use `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack pipeline components for sub-millisecond RAG retrieval. |
| <nobr>[LangChain4j](langchain4j/)</nobr> | Java vector search and RAG with `ValkeyEmbeddingStore` — HNSW indexing, metadata filtering, and Bedrock integration via the official `langchain4j-community-valkey` package. |
| <nobr>[DB-GPT](dbgpt/)</nobr> | Use Valkey as a vector store for RAG pipelines and an LLM response cache in DB-GPT. HNSW indexing, metadata filtering, and sub-millisecond cache reads via `valkey-glide`. |
| <nobr>[DocsGPT](docs-gpt/)</nobr> | Use Valkey as the vector store backend in DocsGPT for document retrieval (RAG). HNSW indexing, source isolation via TAG filtering, and bulk ingestion with `valkey-glide`. |
| <nobr>[CocoIndex](cocoindex/)</nobr> | Build incremental RAG pipelines with Valkey as the vector store target. Declarative indexing with automatic HNSW search, incremental sync (only Δ reprocessed), and semantic queries via `valkey-glide`. |
| <nobr>[BetterDB](betterdb-agent-cache/)</nobr> | Two packages for Valkey-backed LLM caching. `@betterdb/semantic-cache` — Valkey-native vector similarity cache. `@betterdb/agent-cache` — multi-tier LLM, tool, and session cache with LangGraph support. |
| <nobr>[LMCache](lmcache/)</nobr> | Offload LLM KV caches to Valkey for 3-10× TTFT reduction. Share computed attention tensors across vLLM instances via a centralized Valkey L2 store using `valkey-glide`. |
| <nobr>[vLLM Semantic Router](vllm-semantic-router/)</nobr> | Run the vLLM Semantic Router on Valkey — semantic cache, RAG vector store, and agentic memory backends with HNSW vector search via the `valkey-glide` Go client. |
| <nobr>[Cognee](cognee/)</nobr> | AI memory system that builds knowledge graphs from your data. Uses `valkey-glide` with Valkey Search for vector storage, providing more accurate context than traditional RAG through entity and relationship extraction. |
| <nobr>[PraisonAI](praisonai/)</nobr> | Give PraisonAI agents persistent state and vector knowledge retrieval backed by Valkey. `ValkeyStateStore` for session history and counters, `ValkeyVectorKnowledgeStore` for HNSW semantic search. |
| <nobr>[Unstructured](unstructured/)</nobr> | Use Valkey as a vector store destination for Unstructured document ingestion pipelines — store chunked embeddings with HNSW indexing and retrieve via KNN semantic search using `valkey-glide` and `valkey-glide-sync`. |
