<div align="center">

# Valkey Samples

<p>
    ✨ A curated list of resources with demos, tutorials, and samples for Valkey. ✨
</p>

<div align="center">
  <h3>
    <a href="#cookbooks">Cookbooks</a> |
    <a href="#mcp-servers">MCP Servers</a> |
    <a href="#integrations">Integrations</a> |
    <!--<a href="#valkey-sample-apps">Sample Apps</a> |-->
    <a href="#tutorials">Tutorials</a> |
    <a href="#cloud-platforms">Cloud Platforms</a> |
    <a href="#official-valkey-documentation">Official Docs</a>
  </h3>
</div>

</div>

## Cookbooks

> Cookbooks, demos, and production patterns for semantic caching, vector search, RAG, agent memory, and more.

**New to Valkey for AI?** Start with [Semantic Caching → Getting Started](cookbooks/use-cases/semantic-caching/01-getting-started.md) or [LangChain → Getting Started](cookbooks/framework-integrations/langchain/01-getting-started.md).

---

### Use Cases

From caching LLM responses to powering real-time vector search, Valkey is the high-performance backbone for modern AI applications.

| Use Case | Description |
| --- | --- |
| <nobr>[Semantic Caching](cookbooks/use-cases/semantic-caching/)</nobr> | Cache LLM responses by meaning, not just exact match. Cut costs by 60%+ and slash latency from seconds to milliseconds. |
| <nobr>[Conversation Memory](cookbooks/use-cases/conversation-memory/)</nobr> | Scalable, low-latency session storage for chatbot and agent conversations with TTL-based expiry. |
| <nobr>[Vector Search](cookbooks/use-cases/vector-search/)</nobr> | Native vector similarity search with HNSW and FLAT indexing. Sub-millisecond nearest-neighbor queries. |
| <nobr>[Agent Session State](cookbooks/use-cases/agent-session-state/)</nobr> | Persist tool calls, reasoning chains, and intermediate results for multi-step AI agents with atomic operations. |
| <nobr>[Rate Limiting](cookbooks/use-cases/rate-limiting/)</nobr> | Token-aware rate limiting for LLM APIs. Sliding window counters and token bucket patterns built in. |
| <nobr>[Pub/Sub & Streaming](cookbooks/use-cases/pubsub-streaming/)</nobr> | Real-time messaging for AI workloads. Broadcast LLM tokens, fan out agent events, and build durable task queues. |
| <nobr>[RAG Pipelines](cookbooks/use-cases/rag-pipelines/)</nobr> | Retrieval-Augmented Generation with vector search, document chunking, and metadata filtering - all in Valkey. |
| <nobr>[Context Engineering](cookbooks/use-cases/context-engineering/)</nobr> | Build the unified memory and context layer for AI agents. Assemble context from 5 sources, manage short/long-term memory, prune and budget tokens. |
| <nobr>[Feature Store](cookbooks/use-cases/feature-store/)</nobr> | Real-time feature serving for ML models. Microsecond reads for online inference at scale. |

---

### Framework Integrations

Production-ready integrations for popular AI agent frameworks. Checkpointing, caching, vector search, and memory - all backed by Valkey.

| Framework | Description |
| --- | --- |
| <nobr>[Mem0](cookbooks/framework-integrations/mem0/)</nobr> | Intelligent memory layer for AI agents with a dedicated `valkey` provider. Per-user memories, vector search, and HNSW indexing. |
| <nobr>[LangChain / LangGraph](cookbooks/framework-integrations/langchain/)</nobr> | Use Valkey as the complete persistence layer for LangGraph agents - checkpointing, semantic caching, and vector search - through the official `langgraph-checkpoint-aws` package. |
| <nobr>[CrewAI](cookbooks/framework-integrations/crewai/)</nobr> | Give CrewAI agents persistent, searchable memory backed by Valkey. Custom `ValkeyStorage` backend with GLIDE client, vector search, and Amazon Bedrock embeddings. |
| <nobr>[Strands Agents](cookbooks/framework-integrations/strands/)</nobr> | Use the official `strands-valkey-session-manager` community package to back Strands agents with Valkey - persisting conversation history, session metadata, and agent state across invocations. |
| <nobr>[Haystack](cookbooks/framework-integrations/haystack/)</nobr> | Use `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack pipeline components for sub-millisecond RAG retrieval. |
| <nobr>[LangChain4j](cookbooks/framework-integrations/langchain4j/)</nobr> | Java vector search and RAG with `ValkeyEmbeddingStore` — HNSW indexing, metadata filtering, and Bedrock integration via the `langchain4j-community-valkey` package. |
| <nobr>[DB-GPT](cookbooks/framework-integrations/dbgpt/)</nobr> | Use Valkey as a vector store for RAG pipelines and an LLM response cache in DB-GPT. HNSW indexing, metadata filtering, and sub-millisecond cache reads via `valkey-glide`. |
| <nobr>[DocsGPT](cookbooks/framework-integrations/docs-gpt/)</nobr> | Use Valkey as the vector store backend in DocsGPT for document retrieval (RAG). HNSW indexing, source isolation via TAG filtering, and bulk ingestion with `valkey-glide`. |
| <nobr>[BetterDB](cookbooks/framework-integrations/betterdb-agent-cache/)</nobr> | Two packages for Valkey-backed LLM caching. `@betterdb/semantic-cache` — Valkey-native vector similarity cache. `@betterdb/agent-cache` — multi-tier LLM, tool, and session cache with LangGraph support. |
| <nobr>[LMCache](cookbooks/framework-integrations/lmcache/)</nobr> | Offload LLM KV caches to Valkey for 3-10× TTFT reduction. Share computed attention tensors across vLLM instances via a centralized Valkey L2 store using `valkey-glide`. |
| <nobr>[Cognee](cookbooks/framework-integrations/cognee/)</nobr> | AI memory system that builds knowledge graphs from your data. Uses `valkey-glide` with Valkey Search for vector storage, providing more accurate context than traditional RAG. |

<hr>

## MCP Servers

Model Context Protocol servers that integrate with Valkey:

| Server | Description |
| --- | --- |
| [AWS MCP Server](https://github.com/awslabs/mcp) | Official suite of MCP servers providing AI applications access to AWS documentation, services, and best practices |
| [Valkey MCP Task Management Server](https://github.com/jbrinkman/valkey-ai-tasks) | Task management system implementing MCP for AI agents to create, manage, and track tasks with Valkey persistence |

<hr>

## Integrations

Real-world applications and libraries using Valkey:

| Integration | Description |
| --- | --- |
| [Cognee](https://github.com/topoteretes/cognee-community) | AI memory system for agents with vector database adapter for Valkey. Provides more accurate context than traditional RAG |
| [Haystack Integrations](https://github.com/deepset-ai/haystack-core-integrations/tree/main/integrations/valkey) | Valkey integration for Haystack, an open-source AI orchestration framework for building production-ready LLM applications |
| [LangChain AWS](https://github.com/langchain-ai/langchain-aws) | Valkey vector store integration for LangChain on AWS, enabling vector similarity search and LangGraph checkpointing with Valkey via the valkey-glide client |
| [LMCache](https://github.com/LMCache/LMCache) | High-performance KV cache layer for LLM inference engines (vLLM, SGLang) that uses Valkey as a storage backend to reduce time-to-first-token by up to 10× |
| [Mem0 Valkey Vector Store](https://docs.mem0.ai/components/vectordbs/dbs/valkey) | Vector database adapter enabling Mem0 to use Valkey for storing and searching embeddings with HNSW or FLAT indexing |
| [node-rate-limiter-flexible](https://github.com/animir/node-rate-limiter-flexible) | Atomic counters and rate limiting at any scale. Protects from DoS and brute force attacks with Valkey, Redis, and other backends |
| [Recall](https://github.com/joseairosa/recall) | Persistent cross-session memory for Claude and AI agents that survives context limits and session restarts. Available as managed SaaS or self-hosted |
| [redlock-universal](https://github.com/alexpota/redlock-universal/blob/main/VALKEY.md) | Distributed locking implementation with Valkey support using the Redlock algorithm |
| [TensorZero](https://github.com/tensorzero/tensorzero) | Open-source LLM gateway and optimization stack that uses Valkey as a backend for rate limiting and model inference caching |

<hr>

<!-- Coming Soon
## Valkey Sample Apps

Sample applications demonstrating Valkey capabilities:

| Sample App | Description |
| --- | --- |
| [FlicEnjoyer FTS Demo](https://github.com/valkey-io/Valkey-Samples/pull/6) | Full-text search demo showcasing Valkey's search capabilities for a movie discovery experience |
| [Sports Aggregation](https://github.com/valkey-io/Valkey-Samples/pull/5) | Real-time sports data aggregation application using Valkey for high-performance data ingestion and querying |
| [ValkeyMart E-Commerce](https://github.com/valkey-io/Valkey-Samples/pull/4) | Product recommendation engine for an e-commerce storefront powered by Valkey vector search |

<hr> -->

## Tutorials

Learn Valkey through guides, blog posts, and videos:

### Blog Posts

| Tutorial | Description |
| --- | --- |
| [Getting Started with Amazon ElastiCache for Valkey](https://aws.amazon.com/blogs/database/get-started-with-amazon-elasticache-for-valkey/) | Introduction to using Valkey on AWS ElastiCache |
| [Valkey Pipelining Explained](https://basicutils.com/learn/databases/valkey-pipelining-guide) | Guide to understanding and using Valkey pipelining |

### Videos

| Video | Description |
| --- | --- |
| [Introduction to Messaging in Valkey](https://www.youtube.com/watch?v=RLR4g07hIew) | Overview of messaging capabilities in Valkey |
| [Valkey Channel](https://www.youtube.com/@valkeyproject) | Official Valkey YouTube channel with tutorials and updates |
| [Valkey using Python/Valkey Client](https://www.youtube.com/watch?v=IRli5I9MxOs) | Intro tutorial on using Valkey with Python |

<hr>

## Cloud Platforms

### Azure

| Resource | Description |
| --- | --- |
| [Using Valkey on Azure and in .NET Aspire](https://www.infoworld.com/article/4073230/using-valkey-on-azure-and-in-net-aspire.html) | Guide to deploying Valkey on Azure with .NET Aspire |

<hr>

## Official Valkey Documentation

| Resource | Description |
| --- | --- |
| [Valkey](https://valkey.io/) | Official Valkey website with documentation, getting started guides, and community resources |
| [Valkey GitHub](https://github.com/valkey-io/valkey) | Main Valkey repository - open-source, high-performance key-value datastore |
| [Valkey-Glide](https://github.com/valkey-io/valkey-glide) | Official Valkey client library providing high-performance, multi-language support (Python, Java, Node.js, Go, and more) |

<hr>
