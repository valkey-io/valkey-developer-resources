# Getting Started with AnythingLLM and Valkey

> Configure Valkey as AnythingLLM's vector database, understand the per-namespace storage model, and run your first KNN similarity search.

**Beginner** · Node.js · ~15 min

**Who is this for:** Developers setting up AnythingLLM who want a self-hosted, high-performance vector store without paid cloud services.

## Prerequisites

- Docker and Docker Compose
- Node.js 18+
- Basic familiarity with vector embeddings and similarity search

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey

AnythingLLM's Valkey provider uses the `valkey-search` module for FT.CREATE and FT.SEARCH. Start a container with the search module included:

```bash
cd sample/
docker compose up -d
```

Verify it's running:

```bash
docker exec -it $(docker compose ps -q valkey) valkey-cli PING
# PONG
```

Confirm the search module is loaded:

```bash
docker exec -it $(docker compose ps -q valkey) valkey-cli MODULE LIST
# 1) 1) "name"
#    2) "search"
#    ...
```

## Step 2: Install Dependencies

```bash
npm install
```

This installs `@valkey/valkey-glide` — the official Valkey client used by AnythingLLM's provider.

## Step 3: Understand the Storage Model

AnythingLLM creates one HNSW index per workspace namespace:

```text
┌─────────────────────────────────────────────────────────┐
│  Namespace: "my-workspace"                              │
├─────────────────────────────────────────────────────────┤
│  Index:  allm_idx_my-workspace                          │
│  Prefix: allm:my-workspace:                             │
│                                                         │
│  allm:my-workspace:chunk-1  →  HASH                    │
│    vector:   <FLOAT32 bytes>                            │
│    text:     "The document text..."                     │
│    metadata: {"title":"Doc","published":"2024-01-01"}   │
│                                                         │
│  allm:my-workspace:chunk-2  →  HASH                    │
│    vector:   <FLOAT32 bytes>                            │
│    text:     "Another chunk..."                         │
│    metadata: {"title":"Doc","published":"2024-01-01"}   │
└─────────────────────────────────────────────────────────┘
```

Key design decisions:

- **HASH keys** (not JSON) — valkey-search indexes HASH fields directly
- **FLOAT32 little-endian** vectors stored as raw bytes
- **COSINE distance** metric — measures angular similarity between vectors
- **Per-namespace isolation** — each workspace gets its own index and key prefix

## Step 4: Create an Index

The provider creates an index when the first document is embedded into a namespace:

```javascript
import { GlideClient, GlideFt, ProtocolVersion } from "@valkey/valkey-glide";

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
  protocol: ProtocolVersion.RESP2,
  requestTimeout: 5000,
});

const ns = "getting_started";

await GlideFt.create(
  client,
  `allm_idx_${ns}`,
  [
    {
      type: "VECTOR",
      name: "vector",
      attributes: {
        algorithm: "HNSW",
        type: "FLOAT32",
        dimensions: 1536,       // matches your embedding model
        distanceMetric: "COSINE",
      },
    },
  ],
  { dataType: "HASH", prefixes: [`allm:${ns}:`] },
);
```

## Step 5: Store a Chunk

Each document chunk is stored as a HASH with the vector, text, and metadata:

```javascript
const vector = Buffer.from(
  Float32Array.from(embeddingFromYourModel).buffer,
);

await client.hset(`allm:${ns}:chunk-1`, {
  vector,
  text: "Valkey is a high-performance key-value datastore.",
  metadata: JSON.stringify({ title: "Valkey Docs", published: "2024-06-01" }),
});
```

## Step 6: Search with KNN

Retrieve similar chunks using a KNN query. The query vector is bound via `PARAMS` — never string-interpolated:

```javascript
const queryVector = Buffer.from(
  Float32Array.from(embeddingOfQuestion).buffer,
);

const [count, docs] = await GlideFt.search(
  client,
  `allm_idx_${ns}`,
  "*=>[KNN 4 @vector $BLOB AS score]",
  {
    params: [{ key: "BLOB", value: queryVector }],
    returnFields: [
      { fieldIdentifier: "text" },
      { fieldIdentifier: "metadata" },
      { fieldIdentifier: "score" },
    ],
    limit: { offset: 0, count: 4 },
    dialect: 2,
  },
);
```

The `score` field contains the COSINE distance (0 = identical, 1 = orthogonal). Convert to similarity:

```javascript
const similarity = Math.max(0, Math.min(1, 1 - distance));
```

## Step 7: Run the Integration Test

The sample test validates this entire flow end-to-end:

```bash
npm test -- --grep "Getting Started"
```

## How It Works

```text
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  AnythingLLM │────▶│  Valkey Provider │────▶│  Valkey + Search │
│  (workspace) │◀────│  (GLIDE client)  │◀────│  (HNSW index)    │
└──────────────┘     └─────────────────┘     └──────────────────┘
       │                                              ▲
       │  embed(text)                                 │
       └──────────────► Embedding Model ─────────────┘
                        (Ollama / OpenAI)      store vector
```

1. User uploads a document to a workspace
2. AnythingLLM splits it into chunks and embeds each via the configured model
3. The Valkey provider creates the namespace index (if absent) and stores chunks
4. On query, the provider embeds the question and runs a KNN search
5. Top-K results are scored, filtered, and returned as context for the LLM

## Configuration Reference

| Environment Variable | Default | Description |
| --- | --- | --- |
| `VECTOR_DB` | — | Set to `valkey` to activate the provider |
| `VALKEY_VECTOR_DB_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_VECTOR_DB_PORT` | `6379` | Valkey server port |
| `VALKEY_VECTOR_DB_ENDPOINT` | — | Full URL (overrides host/port), e.g. `redis://localhost:6379` |
| `VALKEY_VECTOR_DB_USERNAME` | — | ACL username (optional) |
| `VALKEY_VECTOR_DB_PASSWORD` | — | AUTH password (optional) |
| `VALKEY_VECTOR_DB_USE_TLS` | `false` | Enable TLS encryption |
| `VALKEY_VECTOR_DB_REQUEST_TIMEOUT` | `5000` | Per-command timeout in milliseconds |

---

[Next: Vector Search & Retrieval →](./02-vector-search.md) · [← Back to README](./README.md)
