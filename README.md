<div align="center">

# Valkey Samples

<p>
    ✨ A curated list of resources with demos, tutorials, and samples for Valkey. ✨
</p>

<div align="center">
  <h3>
    <a href="#mcp-servers">MCP Servers</a> |
    <a href="#integrations">Integrations</a> |
    <a href="#valkey-sample-apps">Sample Apps</a> |
    <a href="#tutorials">Tutorials</a> |
    <a href="#cloud-platforms">Cloud Platforms</a> |
    <a href="#official-valkey-documentation">Official Docs</a>
  </h3>
</div>

</div>

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

## Valkey Sample Apps

Sample applications demonstrating Valkey capabilities:

| Sample App | Description |
| --- | --- |
| [FlicEnjoyer FTS Demo](https://github.com/valkey-io/Valkey-Samples/pull/6) | Full-text search demo showcasing Valkey's search capabilities for a movie discovery experience |
| [Sports Aggregation](https://github.com/valkey-io/Valkey-Samples/pull/5) | Real-time sports data aggregation application using Valkey for high-performance data ingestion and querying |
| [ValkeyMart E-Commerce](https://github.com/valkey-io/Valkey-Samples/pull/4) | Product recommendation engine for an e-commerce storefront powered by Valkey vector search |

<hr>

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