# RAG Pipeline with LangChain.js and Valkey

> Build a complete Retrieval-Augmented Generation application that ingests documents into Valkey, retrieves relevant context via vector search, and generates grounded answers with an LLM.

**Intermediate** · TypeScript · ~25 min

**Who is this for:** Developers who have completed the embedding storage and
similarity search cookbooks and are ready to wire everything together into an
end-to-end RAG pipeline that answers questions from your own documents.

## Prerequisites

- Completed [01 - Embedding Storage](./01-embedding-storage.md) and [02 - Similarity Search](./02-similarity-search.md)
- Valkey 8.0+ running with the Search module (`localhost:6379`)
- Node.js 18+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)
- Installed packages:

```bash
npm install langchain @langchain/openai @langchain/community ioredis
```

## Security Note

> ⚠️ Never commit API keys to source control. Use environment variables or a secrets manager. In production, connect to Valkey over TLS and use ACLs to restrict access to the index.

## Architecture

```text
┌───────────┐    ┌───────────┐    ┌────────────┐    ┌─────────────────────┐
│ Documents │───▶│ Splitter  │───▶│ Embeddings │───▶│ Valkey Vector Store  │
└───────────┘    └───────────┘    └────────────┘    └──────────┬──────────┘
                                                               │
                                                               ▼
┌────────┐    ┌─────┐    ┌───────────┐                ┌───────────────┐
│ Answer │◀───│ LLM │◀───│ Retriever │◀───────────────│  User Query   │
└────────┘    └─────┘    └───────────┘                └───────────────┘
```

1. **Ingest** — Load documents, split into chunks, generate embeddings, store in Valkey.
2. **Retrieve** — Convert the user query into an embedding, find the top-k most similar chunks.
3. **Generate** — Pass retrieved context + question to the LLM to produce a grounded answer.

## Step 1 — Document Loading

Load raw text and split it into chunks that fit within the embedding model's context window.

```typescript
import { TextLoader } from "langchain/document_loaders/fs/text";
import { RecursiveCharacterTextSplitter } from "langchain/text_splitter";

const loader = new TextLoader("./docs/product-manual.txt");
const rawDocs = await loader.load();

const splitter = new RecursiveCharacterTextSplitter({
  chunkSize: 1000,
  chunkOverlap: 200,
});

const docs = await splitter.splitDocuments(rawDocs);

console.log(`Split into ${docs.length} chunks`);
```

The `chunkOverlap` ensures context isn't lost at split boundaries. Adjust `chunkSize` based on your embedding model's token limit (OpenAI `text-embedding-3-small` supports up to 8191 tokens).

## Step 2 — Create Vector Store and Ingest

Use `ValkeyVectorStore.fromDocuments` to embed all chunks and store them in a single call.

```typescript
import { ValkeyVectorStore } from "@langchain/community/vectorstores/valkey";
import { OpenAIEmbeddings } from "@langchain/openai";

const embeddings = new OpenAIEmbeddings({
  model: "text-embedding-3-small",
});

const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
  redisUrl: "redis://localhost:6379",
  indexName: "rag-docs",
  keyPrefix: "doc:",
  indexOptions: {
    algorithm: "HNSW",
    distanceMetric: "COSINE",
  },
});

console.log(`Ingested ${docs.length} chunks into Valkey`);
```

This creates the search index if it doesn't already exist, generates embeddings for every chunk, and stores them as hash keys in Valkey.

## Step 3 — Create Retriever

Wrap the vector store as a LangChain retriever to plug into a chain.

```typescript
const retriever = vectorStore.asRetriever({
  k: 4,
  filter: {
    source: "./docs/product-manual.txt",
  },
});
```

| Parameter | Purpose                                           |
| --------- | ------------------------------------------------- |
| `k`       | Number of chunks to retrieve per query            |
| `filter`  | Metadata filter to restrict results to a doc set  |

Increase `k` if answers feel incomplete; decrease it to reduce token usage and latency.

## Step 4 — Build the Chain

Use `createRetrievalChain` to connect the retriever to a chat model with a prompt template.

```typescript
import { ChatOpenAI } from "@langchain/openai";
import { createRetrievalChain } from "langchain/chains/retrieval";
import { createStuffDocumentsChain } from "langchain/chains/combine_documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const llm = new ChatOpenAI({
  model: "gpt-4o-mini",
  temperature: 0,
});

const systemPrompt =
  `You are a helpful assistant. Answer the user's question using ONLY the ` +
  `provided context. If the context doesn't contain enough information, ` +
  `say "I don't have enough information to answer that."

Context:
{context}`;

const prompt = ChatPromptTemplate.fromMessages([
  ["system", systemPrompt],
  ["human", "{input}"],
]);

const combineDocsChain = await createStuffDocumentsChain({
  llm,
  prompt,
});

const ragChain = await createRetrievalChain({
  retriever,
  combineDocsChain,
});
```

The `createStuffDocumentsChain` concatenates retrieved documents into the `{context}` placeholder. For large document sets, consider `createMapReduceDocumentsChain` instead.

## Step 5 — Query

Invoke the chain with a natural language question.

```typescript
const response = await ragChain.invoke({
  input: "What is the return policy for electronics?",
});

console.log("Answer:", response.answer);
console.log("Sources:", response.context.map((doc) => doc.metadata.source));
```

The response includes both the generated answer and the source documents used, enabling citation and traceability.

## Complete Example

```typescript
import { TextLoader } from "langchain/document_loaders/fs/text";
import { RecursiveCharacterTextSplitter } from "langchain/text_splitter";
import { ValkeyVectorStore } from "@langchain/community/vectorstores/valkey";
import { OpenAIEmbeddings, ChatOpenAI } from "@langchain/openai";
import { createRetrievalChain } from "langchain/chains/retrieval";
import { createStuffDocumentsChain } from "langchain/chains/combine_documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";

async function main() {
  // 1. Load and split documents
  const loader = new TextLoader("./docs/product-manual.txt");
  const rawDocs = await loader.load();

  const splitter = new RecursiveCharacterTextSplitter({
    chunkSize: 1000,
    chunkOverlap: 200,
  });
  const docs = await splitter.splitDocuments(rawDocs);
  console.log(`Split into ${docs.length} chunks`);

  // 2. Create vector store and ingest
  const embeddings = new OpenAIEmbeddings({
    model: "text-embedding-3-small",
  });

  const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
    redisUrl: "redis://localhost:6379",
    indexName: "rag-docs",
    keyPrefix: "doc:",
    indexOptions: {
      algorithm: "HNSW",
      distanceMetric: "COSINE",
    },
  });
  console.log(`Ingested ${docs.length} chunks into Valkey`);

  // 3. Create retriever
  const retriever = vectorStore.asRetriever({ k: 4 });

  // 4. Build the chain
  const llm = new ChatOpenAI({
    model: "gpt-4o-mini",
    temperature: 0,
  });

  const prompt = ChatPromptTemplate.fromMessages([
    [
      "system",
      `You are a helpful assistant. Answer the user's question using ONLY the provided context. If the context doesn't contain enough information, say "I don't have enough information to answer that."

Context:
{context}`,
    ],
    ["human", "{input}"],
  ]);

  const combineDocsChain = await createStuffDocumentsChain({ llm, prompt });
  const ragChain = await createRetrievalChain({ retriever, combineDocsChain });

  // 5. Query
  const response = await ragChain.invoke({
    input: "What is the return policy for electronics?",
  });

  console.log("\nAnswer:", response.answer);
  console.log(
    "\nSources:",
    response.context.map((doc) => doc.metadata.source)
  );

  // Clean up connection
  await vectorStore.client?.disconnect();
}

main().catch(console.error);
```

## TTL for Ephemeral RAG

For time-limited document sets (e.g., daily reports, session-scoped context), set a TTL so Valkey automatically evicts stale chunks.

```typescript
const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
  redisUrl: "redis://localhost:6379",
  indexName: "ephemeral-rag",
  keyPrefix: "session:abc123:",
  ttl: 3600, // Expire documents after 1 hour
  indexOptions: {
    algorithm: "HNSW",
    distanceMetric: "COSINE",
  },
});
```

Use distinct `keyPrefix` values per session to isolate document sets. When the TTL expires, the keys are removed and no longer appear in search results.

This pattern works well for:

- Chat sessions with uploaded documents
- Daily news/report ingestion that becomes stale
- A/B testing different document sets

## Scaling

### Batch Ingestion

For large document sets, use `batchSize` to control how many embeddings are generated and stored per round-trip.

```typescript
const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
  redisUrl: "redis://localhost:6379",
  indexName: "rag-docs",
  keyPrefix: "doc:",
  batchSize: 100, // Process 100 chunks at a time
  indexOptions: {
    algorithm: "HNSW",
    distanceMetric: "COSINE",
  },
});
```

### Connection Pooling

For production workloads with concurrent queries, use a connection pool instead of a single client.

```typescript
import Redis from "ioredis";

const redisClient = new Redis("redis://localhost:6379", {
  maxRetriesPerRequest: 3,
  retryDelayOnFailover: 100,
  lazyConnect: true,
});

const vectorStore = new ValkeyVectorStore(embeddings, {
  redisClient,
  indexName: "rag-docs",
  keyPrefix: "doc:",
});
```

### Performance Tips

| Concern              | Recommendation                                              |
| -------------------- | ----------------------------------------------------------- |
| Ingestion speed      | Increase `batchSize` to 200–500 for bulk loads              |
| Query latency        | Use `FLAT` algorithm for <10k docs, `HNSW` for larger sets  |
| Memory usage         | Reduce embedding dimensions with `text-embedding-3-small`   |
| Concurrent queries   | Use connection pooling with 10–50 connections               |

## Troubleshooting

| Problem                              | Cause                                    | Fix                                                         |
| ------------------------------------ | ---------------------------------------- | ----------------------------------------------------------- |
| `ResponseError: unknown index name`  | Index not created yet                    | Run ingestion first; `fromDocuments` creates the index      |
| Empty retrieval results              | Embeddings model mismatch                | Use the same model for ingestion and queries                |
| `OPENAI_API_KEY` error               | Missing environment variable             | `export OPENAI_API_KEY=sk-...` before running               |
| Timeout on large ingestion           | Too many docs in one call                | Set `batchSize: 100` to chunk the ingestion                 |
| Answers hallucinate beyond context   | Prompt not constraining the LLM          | Add explicit "only use provided context" in system prompt   |
| Stale results after document update  | Old embeddings still in index            | Delete old keys or use a new `keyPrefix` per version        |

---

[← Back to README](./README.md)
