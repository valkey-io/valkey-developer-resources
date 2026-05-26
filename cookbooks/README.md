# Valkey for AI — Cookbooks

> Cookbooks, demos, and production patterns for semantic caching, vector search, RAG, agent memory, and more.

**New to Valkey for AI?** Start with [Semantic Caching → Getting Started](use-cases/semantic-caching/01-getting-started.md) or [LangChain → Getting Started](framework-integrations/langchain/01-getting-started.md).

---

## Use Cases

From caching LLM responses to powering real-time vector search, Valkey is the high-performance backbone for modern AI applications.

| Use Case | Description |
| --- | --- |
| <nobr>[Semantic Caching](use-cases/semantic-caching/)</nobr> | Cache LLM responses by meaning, not just exact match. Cut costs by 60%+ and slash latency from seconds to milliseconds. |
| <nobr>[Conversation Memory](use-cases/conversation-memory/)</nobr> | Scalable, low-latency session storage for chatbot and agent conversations with TTL-based expiry. |
| <nobr>[Vector Search](use-cases/vector-search/)</nobr> | Native vector similarity search with HNSW and FLAT indexing. Sub-millisecond nearest-neighbor queries. |
| <nobr>[Agent Session State](use-cases/agent-session-state/)</nobr> | Persist tool calls, reasoning chains, and intermediate results for multi-step AI agents with atomic operations. |
| <nobr>[Rate Limiting](use-cases/rate-limiting/)</nobr> | Token-aware rate limiting for LLM APIs. Sliding window counters and token bucket patterns built in. |
| <nobr>[Pub/Sub & Streaming](use-cases/pubsub-streaming/)</nobr> | Real-time messaging for AI workloads. Broadcast LLM tokens, fan out agent events, and build durable task queues. |
| <nobr>[RAG Pipelines](use-cases/rag-pipelines/)</nobr> | Retrieval-Augmented Generation with vector search, document chunking, and metadata filtering - all in Valkey. |
| <nobr>[Context Engineering](use-cases/context-engineering/)</nobr> | Build the unified memory and context layer for AI agents. Assemble context from 5 sources, manage short/long-term memory, prune and budget tokens. |
| <nobr>[Feature Store](use-cases/feature-store/)</nobr> | Real-time feature serving for ML models. Microsecond reads for online inference at scale. |

---

## Framework Integrations

Production-ready integrations for popular AI agent frameworks. Checkpointing, caching, vector search, and memory - all backed by Valkey.

| Framework | Description |
| --- | --- |
| <nobr>[Mem0](framework-integrations/mem0/)</nobr> | Intelligent memory layer for AI agents with a dedicated `valkey` provider. Per-user memories, vector search, and HNSW indexing. |
| <nobr>[LangChain / LangGraph](framework-integrations/langchain/)</nobr> | Use Valkey as the complete persistence layer for LangGraph agents - checkpointing, semantic caching, and vector search - through the official `langgraph-checkpoint-aws` package. |
| <nobr>[CrewAI](framework-integrations/crewai/)</nobr> | Give CrewAI agents persistent, searchable memory backed by Valkey. Custom `ValkeyStorage` backend with GLIDE client, vector search, and Amazon Bedrock embeddings. |
| <nobr>[Strands Agents](framework-integrations/strands/)</nobr> | Use the official `strands-valkey-session-manager` community package to back Strands agents with Valkey - persisting conversation history, session metadata, and agent state across invocations. |
| <nobr>[Haystack](framework-integrations/haystack/)</nobr> | Use `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack pipeline components for sub-millisecond RAG retrieval. |
| <nobr>[LangChain4j](framework-integrations/langchain4j/)</nobr> | Java vector search and RAG with `ValkeyEmbeddingStore` — HNSW indexing, metadata filtering, and Bedrock integration via the `langchain4j-community-valkey` package. |
| <nobr>[DB-GPT](framework-integrations/dbgpt/)</nobr> | Use Valkey as a vector store for RAG pipelines and an LLM response cache in DB-GPT. HNSW indexing, metadata filtering, and sub-millisecond cache reads via `valkey-glide`. |
| <nobr>[DocsGPT](framework-integrations/docs-gpt/)</nobr> | Use Valkey as the vector store backend in DocsGPT for document retrieval (RAG). HNSW indexing, source isolation via TAG filtering, and bulk ingestion with `valkey-glide`. |
| <nobr>[BetterDB](framework-integrations/betterdb-agent-cache/)</nobr> | Two packages for Valkey-backed LLM caching. `@betterdb/semantic-cache` — Valkey-native vector similarity cache. `@betterdb/agent-cache` — multi-tier LLM, tool, and session cache with LangGraph support. |
| <nobr>[Cognee](framework-integrations/cognee/)</nobr> | AI memory system that builds knowledge graphs from your data. Uses `valkey-glide` with Valkey Search for vector storage, providing more accurate context than traditional RAG. |

