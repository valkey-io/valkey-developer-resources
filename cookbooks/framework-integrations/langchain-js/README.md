# LangChain.js + Valkey Cookbook

> Build vector search applications with LangChain.js and Valkey — from embedding storage to full RAG pipelines, using Valkey as a high-performance vector store.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Connect LangChain.js to Valkey, store embeddings, and run similarity searches |
| [Metadata Filtering](./02-metadata-filtering.md) | Intermediate | Filter vector search results using metadata fields and hybrid queries |
| [RAG Pipeline](./03-rag-pipeline.md) | Intermediate | Build a retrieval-augmented generation pipeline with Valkey as the retriever |

## Prerequisites

- **Valkey 8.1+** with search module (`valkey-bundle`)
- **Node.js 20+**
- **An embeddings provider API key** (e.g., OpenAI, Cohere, or any LangChain-supported provider)

## How LangChain.js Uses Valkey

LangChain.js integrates with Valkey through the `ValkeyVectorStore` class in the `@langchain/valkey` package. Under the hood it uses:

- **@valkey/valkey-glide** — the official Valkey client for Node.js
- **GlideFt** — the Valkey Search command interface exposed by valkey-glide, providing `FT.CREATE`, `FT.SEARCH`, and related commands
- **HASH storage** — each document is stored as a Valkey Hash with fields for content, embedding vector, and metadata
- **HNSW or FLAT indexing** — vector indexes are created with either HNSW (approximate, fast) or FLAT (exact, brute-force) algorithms depending on your configuration

When you call `ValkeyVectorStore.fromDocuments()` or `addDocuments()`, LangChain.js:

1. Generates embeddings via your configured embeddings model
2. Stores each document as a Hash (`doc:<prefix>:<id>`)
3. Creates (or reuses) a Valkey Search index with a vector field for similarity queries

## Quick Start

```typescript
import { ValkeyVectorStore } from "@langchain/valkey";
import { OpenAIEmbeddings } from "@langchain/openai";
import { GlideClient } from "@valkey/valkey-glide";

// Connect to Valkey
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

// Create the vector store
const vectorStore = new ValkeyVectorStore(new OpenAIEmbeddings(), {
  client,
  indexName: "langchain-demo",
  keyPrefix: "doc:demo:",
});

// Add documents
await vectorStore.addDocuments([
  { pageContent: "Valkey is a high-performance key-value store", metadata: { source: "docs" } },
  { pageContent: "Vector search enables semantic similarity queries", metadata: { source: "tutorial" } },
]);

// Similarity search
const results = await vectorStore.similaritySearch("fast database", 2);
console.log(results);
```

> **Note:** `@langchain/valkey` is from PR [langchain-ai/langchainjs#9915](https://github.com/langchain-ai/langchainjs/pull/9915). Until published, install from git:
>
> ```bash
> npm install langchain-ai/langchainjs#9915
> ```

---

[← Back to Valkey Samples](../../../README.md)
