# RAG Pipeline with LangChain.js and Valkey

> Build a complete Retrieval-Augmented Generation application that ingests documents into Valkey, retrieves relevant context via vector search, and generates grounded answers with an LLM.

**Intermediate** · TypeScript · ~25 min

**Who is this for:** Developers who have completed the embedding storage and
similarity search cookbooks and are ready to wire everything together into an
end-to-end RAG pipeline that answers questions from your own documents.

## Prerequisites

- Completed [01 - Getting Started](./01-getting-started.md) and [02 - Metadata Filtering](./02-metadata-filtering.md)
- Valkey 8.1+ running with the Search module (`localhost:6379`)
- Node.js 20+
- [Ollama](https://ollama.com/) running locally with embedding and chat models
- Installed packages:

```bash
npm install @langchain/core@0.3.46 @valkey/valkey-glide@1.3.0 @langchain/ollama@0.2.0 langchain@0.3.22
```

> **Package note:** The code examples in this cookbook reference `@langchain/valkey`, which
> is not yet published on npm (upstream PR
> [langchain-ai/langchainjs#9915](https://github.com/langchain-ai/langchainjs/pull/9915) is
> closed). Until it ships, you can use `@langchain/community/vectorstores/valkey` with
> `ioredis` as the transport layer — it provides a compatible `ValkeyVectorStore` class.
> The API surface is nearly identical; the main difference is passing an `ioredis` client
> instead of a `GlideClient`. We use `@valkey/valkey-glide` directly in the sample project
> to demonstrate the underlying vector operations without depending on an unpublished package.

<details>
<summary>Optional: Using OpenAI instead of Ollama</summary>

```bash
npm install @langchain/openai
```

Set `OPENAI_API_KEY` as an environment variable. Replace `OllamaEmbeddings` with
`OpenAIEmbeddings` and `ChatOllama` with `ChatOpenAI` in the code below. This requires
a paid API key that sends data to OpenAI's servers.

</details>

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

The `chunkOverlap` ensures context isn't lost at split boundaries. Adjust `chunkSize` based on your embedding model's token limit (e.g., `nomic-embed-text` supports 8192 tokens).

## Step 2 — Create Vector Store and Ingest

Use `ValkeyVectorStore.fromDocuments` to embed all chunks and store them in a single call.

```typescript
import { ValkeyVectorStore } from "@langchain/valkey";
import { OllamaEmbeddings } from "@langchain/ollama";
import { GlideClient } from "@valkey/valkey-glide";

const embeddings = new OllamaEmbeddings({
  model: "nomic-embed-text",
});

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
  valkeyClient: client,
  indexName: "rag-docs",
  keyPrefix: "doc:rag-docs:",
  indexOptions: {
    ALGORITHM: "HNSW",
    DISTANCE_METRIC: "COSINE",
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
import { ChatOllama } from "@langchain/ollama";
import { createRetrievalChain } from "langchain/chains/retrieval";
import { createStuffDocumentsChain } from "langchain/chains/combine_documents";
import { ChatPromptTemplate } from "@langchain/core/prompts";

const llm = new ChatOllama({
  model: "llama3.2",
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
import { ValkeyVectorStore } from "@langchain/valkey";
import { OllamaEmbeddings, ChatOllama } from "@langchain/ollama";
import { GlideClient } from "@valkey/valkey-glide";
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
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });

  const embeddings = new OllamaEmbeddings({
    model: "nomic-embed-text",
  });

  const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
    valkeyClient: client,
    indexName: "rag-docs",
    keyPrefix: "doc:rag-docs:",
    indexOptions: {
      ALGORITHM: "HNSW",
      DISTANCE_METRIC: "COSINE",
    },
  });
  console.log(`Ingested ${docs.length} chunks into Valkey`);

  // 3. Create retriever
  const retriever = vectorStore.asRetriever({ k: 4 });

  // 4. Build the chain
  const llm = new ChatOllama({
    model: "llama3.2",
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
  client.close();
}

main().catch(console.error);
```

## TTL for Ephemeral RAG

For time-limited document sets (e.g., daily reports, session-scoped context), set a TTL so Valkey automatically evicts stale chunks.

```typescript
const vectorStore = await ValkeyVectorStore.fromDocuments(docs, embeddings, {
  valkeyClient: client,
  indexName: "ephemeral-rag",
  keyPrefix: "session:abc123:",
  ttl: 3600, // Expire documents after 1 hour
  indexOptions: {
    ALGORITHM: "HNSW",
    DISTANCE_METRIC: "COSINE",
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
  valkeyClient: client,
  indexName: "rag-docs",
  keyPrefix: "doc:rag-docs:",
  batchSize: 100, // Process 100 chunks at a time
  indexOptions: {
    ALGORITHM: "HNSW",
    DISTANCE_METRIC: "COSINE",
  },
});
```

### Connection Pooling

`GlideClient` from `@valkey/valkey-glide` manages connection pooling internally.
For production workloads with concurrent queries, create the client once and reuse it:

```typescript
import { GlideClient } from "@valkey/valkey-glide";

// Create once at application startup
const client = await GlideClient.createClient({
  addresses: [{ host: "valkey.internal", port: 6379 }],
});

// Reuse across vector store instances
const vectorStore = new ValkeyVectorStore(embeddings, {
  valkeyClient: client,
  indexName: "rag-docs",
  keyPrefix: "doc:rag-docs:",
});
```

### Performance Tips

| Concern            | Recommendation                                                   |
| ------------------ | ---------------------------------------------------------------- |
| Ingestion speed    | Increase `batchSize` to 200–500 for bulk loads                   |
| Query latency      | Use `FLAT` algorithm for <10k docs, `HNSW` for larger sets       |
| Memory usage       | Use a smaller embedding model (e.g., 768-dim `nomic-embed-text`) |
| Concurrent queries | Use connection pooling with 10–50 connections                    |

## Troubleshooting

| Problem                              | Cause                                    | Fix                                                         |
| ------------------------------------ | ---------------------------------------- | ----------------------------------------------------------- |
| `ResponseError: unknown index name`  | Index not created yet                    | Run ingestion first; `fromDocuments` creates the index      |
| Empty retrieval results              | Embeddings model mismatch                | Use the same model for ingestion and queries                |
| `OPENAI_API_KEY` error               | Missing environment variable             | Only needed if using OpenAI; Ollama runs locally            |
| Timeout on large ingestion           | Too many docs in one call                | Set `batchSize: 100` to chunk the ingestion                 |
| Answers hallucinate beyond context   | Prompt not constraining the LLM          | Add explicit "only use provided context" in system prompt   |
| Stale results after document update  | Old embeddings still in index            | Delete old keys or use a new `keyPrefix` per version        |

---

[← Previous: Metadata Filtering](./02-metadata-filtering.md) · [← Back to README](./README.md)
