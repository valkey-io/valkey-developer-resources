# Getting Started with LangChain.js and Valkey

> Store and search vector embeddings using LangChain.js with Valkey as your vector database.

**Beginner** · TypeScript · ~15 min

**Who is this for:** Developers who want to add semantic search or retrieval-augmented generation (RAG) to their Node.js/TypeScript applications using Valkey as a high-performance vector store.

## Prerequisites

- Node.js 20+
- Docker (for running Valkey)
- [Ollama](https://ollama.com/) running locally with an embedding model (e.g., `nomic-embed-text`)

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey

Run the Valkey bundle image, which includes the Search module required for vector indexing:

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:8.1.1
```

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Packages

```bash
npm install @langchain/valkey @langchain/core @valkey/valkey-glide @langchain/ollama
```

- `@langchain/valkey` — ValkeyVectorStore integration
- `@langchain/core` — Core LangChain abstractions (documents, embeddings)
- `@valkey/valkey-glide` — Valkey client (used internally by the vector store)
- `@langchain/ollama` — Ollama embeddings (local, no API key required)

<details>
<summary>Optional: Using OpenAI embeddings instead</summary>

```bash
npm install @langchain/openai
```

Replace `OllamaEmbeddings` with `OpenAIEmbeddings` in the code below and set the
`OPENAI_API_KEY` environment variable. This requires a paid API key.

</details>

## Step 3: Create a Vector Store

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { ValkeyVectorStore } from "@langchain/valkey";
import { OllamaEmbeddings } from "@langchain/ollama";

// Create a Glide client connection
const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

// Initialize the embeddings model (runs locally via Ollama)
const embeddings = new OllamaEmbeddings({
  model: "nomic-embed-text",
});

// Create the vector store
const vectorStore = new ValkeyVectorStore(embeddings, {
  valkeyClient: client,
  indexName: "my-documents",
  indexOptions: {
    ALGORITHM: "HNSW",
    DISTANCE_METRIC: "COSINE",
  },
});
```

## Step 4: Add Documents

You can add documents from plain text strings:

```typescript
const texts = [
  "Valkey is an open-source in-memory data store.",
  "Vector search enables semantic similarity matching.",
  "LangChain provides abstractions for working with LLMs.",
];

const metadata = [
  { source: "docs", topic: "valkey" },
  { source: "docs", topic: "search" },
  { source: "docs", topic: "langchain" },
];

await ValkeyVectorStore.fromTexts(texts, metadata, embeddings, {
  valkeyClient: client,
  indexName: "my-documents",
  indexOptions: {
    ALGORITHM: "HNSW",
    DISTANCE_METRIC: "COSINE",
  },
});
```

Or add structured `Document` objects directly:

```typescript
import { Document } from "@langchain/core/documents";

await vectorStore.addDocuments([
  new Document({
    pageContent: "Valkey supports hash and JSON data types.",
    metadata: { source: "docs", topic: "valkey" },
  }),
]);
```

## Step 5: Similarity Search

Query the vector store with natural language:

```typescript
const results = await vectorStore.similaritySearch(
  "What is Valkey?",
  3 // return top 3 results
);

for (const doc of results) {
  console.log(`[${doc.metadata.topic}] ${doc.pageContent}`);
}
```

Example output:

```text
[valkey] Valkey is an open-source in-memory data store.
[valkey] Valkey supports hash and JSON data types.
[search] Vector search enables semantic similarity matching.
```

## How It Works

When you call `addDocuments`, the following happens:

1. Each document's `pageContent` is passed to the embeddings model, which returns a vector (array of floats).
2. ValkeyVectorStore stores each document as a Valkey HASH with the key pattern `doc:<indexName>:<id>`.
3. The hash fields include:
   - `content` — the original text
   - `content_vector` — the embedding stored as a Float32Array buffer
   - `metadata` — document metadata serialized as a JSON string
4. On the first `addDocuments` call, ValkeyVectorStore automatically creates a search index using `FT.CREATE` (via `GlideFt.create`) on HASH keys matching the prefix `doc:<indexName>:`.
5. When you call `similaritySearch`, the query text is embedded and Valkey performs an approximate nearest-neighbor (ANN) search using the HNSW index.

## Configuration Reference

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `indexName` | `string` | `"langchain"` | Name of the Valkey search index |
| `indexOptions` | `object` | `{ ALGORITHM: "HNSW", DISTANCE_METRIC: "COSINE" }` | Index algorithm and distance metric |
| `keyPrefix` | `string` | `"doc:<indexName>:"` | Prefix for all document hash keys |
| `contentKey` | `string` | `"content"` | Hash field name for document text |
| `vectorKey` | `string` | `"content_vector"` | Hash field name for the embedding vector |
| `ttl` | `number` | `undefined` | Optional TTL in seconds for document keys |

## Troubleshooting

### Connection refused on port 6379

Ensure the Valkey container is running:

```bash
docker ps | grep valkey
```

If it's not listed, start it again with the command from Step 1.

### "Unknown command FT.CREATE"

You're running a Valkey image without the Search module. Use `valkey/valkey-bundle` instead of the base `valkey/valkey` image.

### Empty search results

- Verify documents were added: `docker exec valkey valkey-cli KEYS "doc:my-documents:*"`
- Check the index exists: `docker exec valkey valkey-cli FT._LIST`
- Ensure your embedding model is returning vectors (check your API key is set)

### Dimension mismatch errors

The index dimension is set on first insert. If you switch embedding models, drop the index first:

```bash
docker exec valkey valkey-cli FT.DROPINDEX my-documents
```

---

**Next →** [02-metadata-filtering.md](./02-metadata-filtering.md)

**Back to** [README](./README.md)
