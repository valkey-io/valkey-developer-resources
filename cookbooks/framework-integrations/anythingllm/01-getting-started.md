# Getting Started with AnythingLLM + Valkey

**Beginner** · JavaScript · ~15 min

## What is AnythingLLM + Valkey?

[AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) is a local-first RAG application that lets you chat with your own documents. It supports pluggable **vector database** providers; setting `VECTOR_DB=valkey` makes it store and search embeddings in Valkey through the [`valkey-search`](https://github.com/valkey-io/valkey-search) module and the [`@valkey/valkey-glide`](https://github.com/valkey-io/valkey-glide) client.

In this cookbook you will point AnythingLLM at Valkey, learn how it lays out vectors in the keyspace, and run a tiny GLIDE script that mirrors the provider's first operations — create an index, store a chunk, and retrieve it with a KNN search.

## Prerequisites

- **Docker or Podman** (to run Valkey with the search module)
- **Node.js 18+** (to run the GLIDE mirror script)
- An AnythingLLM instance (Docker, desktop, or source) — only needed for the configuration steps

## Step 1: Start Valkey with the search module

The provider needs the `valkey-search` module, which ships in the `valkey/valkey-bundle` image (it also bundles the JSON module). Start it with Docker:

```bash
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

Or with Podman:

```bash
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

Verify the module is loaded:

```bash
docker exec valkey-search valkey-cli FT._LIST
# (empty array) — the command exists, so valkey-search is loaded
```

> ⚠️ This example connects without authentication for local development. Always enable authentication and TLS for production deployments — see [03 - Production Operations](03-production.md).

## Step 2: Point AnythingLLM at Valkey

AnythingLLM reads its vector DB selection from environment variables (or the admin UI). Set `VECTOR_DB=valkey` and provide a connection. You can use a single endpoint URL **or** discrete host/port:

```bash
VECTOR_DB="valkey"

# Option A — a single endpoint (redis:// or rediss:// for TLS):
VALKEY_VECTOR_DB_ENDPOINT="redis://localhost:6379"

# Option B — discrete host/port (with optional credentials/TLS):
# VALKEY_VECTOR_DB_HOST="localhost"
# VALKEY_VECTOR_DB_PORT="6379"
# VALKEY_VECTOR_DB_USERNAME=                 # optional (ACL user)
# VALKEY_VECTOR_DB_PASSWORD=                 # optional (AUTH)
# VALKEY_VECTOR_DB_USE_TLS="false"           # "true" for cloud/TLS endpoints
# VALKEY_VECTOR_DB_REQUEST_TIMEOUT="5000"    # ms; GLIDE's 250ms default is too low off-localhost
```

If you run AnythingLLM from `docker-compose`, an opt-in Valkey service is included (commented out) in `docker/docker-compose.yml`. Uncomment it and set the variables above to use it.

In the admin UI, the same options appear under **Settings → Vector Database → Valkey**: Endpoint, Host, Port, Username, Password, and Use TLS. The password is write-only — the server only ever reports whether one is set, never its value.

> `VALKEY_VECTOR_DB_REQUEST_TIMEOUT` defaults to `5000` (5 seconds). GLIDE's built-in default is 250ms, which causes spurious timeouts for anyone not on localhost. Raise it for high-latency or TLS endpoints.

## Step 3: Understand the storage model

Before running anything, it helps to know how the provider maps an AnythingLLM **workspace namespace** onto the Valkey keyspace. It mirrors the one-index-per-namespace design used by the Qdrant and Milvus providers:

| Concept | Value | Notes |
|---------|-------|-------|
| Index name | `allm_idx_{namespace}` | One `valkey-search` index per workspace |
| Key prefix | `allm:{namespace}:` | Each chunk is a HASH at `allm:{namespace}:{vectorId}` |
| `vector` field | FLOAT32 little-endian bytes | The only indexed field (HNSW + COSINE) |
| `text` field | chunk text | Stored, returned on search, not indexed |
| `metadata` field | JSON string | Stored, returned on search, not indexed |

Namespaces are normalized to satisfy `valkey-search` naming rules (letters, digits, underscores; cannot start with a digit), so a workspace like `my-workspace` becomes index `allm_idx_my_workspace` over prefix `allm:my_workspace:`.

## Step 4: Run a minimal GLIDE mirror

You do not need the full app to see the provider's core loop. The script below connects with GLIDE, creates a per-namespace HNSW index, stores one chunk as a HASH, and retrieves it with a KNN search — exactly the sequence `addDocumentToNamespace` + `performSimilaritySearch` perform.

Install the client (the exact version AnythingLLM pins):

```bash
npm init -y
npm pkg set type=module
npm install @valkey/valkey-glide@2.4.1
```

Create `getting-started.js`:

```javascript
import { GlideClient, GlideFt, RequestError } from "@valkey/valkey-glide";

// Toy embedder: maps text to an 8-dim unit vector by hashing char codes.
// Stand-in for a real embedding model (e.g. OpenAI text-embedding-3-small
// returns 1536 dims). Distinct text yields a distinct direction, which is what
// COSINE similarity needs — never search with a constant/uniform vector.
const DIM = 8; // dimension of the toy embedder above
function embed(text = "") {
  const v = new Array(DIM).fill(0);
  for (let i = 0; i < text.length; i++) v[i % DIM] += text.charCodeAt(i);
  const mag = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
  return v.map((x) => x / mag);
}

// Encode a numeric vector as a FLOAT32 little-endian Buffer (what valkey-search
// expects). Buffer is little-endian on all supported platforms.
const floatToBuffer = (values) => Buffer.from(Float32Array.from(values).buffer);

// Coerce a GlideString reply value (string | Buffer) to a string.
const toStr = (v) => (Buffer.isBuffer(v) ? v.toString("utf-8") : `${v}`);

const namespace = "demo";
const indexName = `allm_idx_${namespace}`;
const keyPrefix = `allm:${namespace}:`;

async function main() {
  // GLIDE defaults to a 250ms request timeout — too low off-localhost — so the
  // provider sets it explicitly. RESP2 makes module replies predictable arrays.
  const client = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
    requestTimeout: 5000, // ms; tune up for high-latency/TLS endpoints
  });

  try {
    // Idempotent first step: drop any stale index so re-runs start clean.
    // dropindex throws RequestError when the index is absent — a safe no-op on
    // a clean first run — so catch only that narrow case.
    try {
      await GlideFt.dropindex(client, indexName);
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }

    // 1. Create the per-namespace HNSW index over the FLOAT32 `vector` field.
    await GlideFt.create(
      client,
      indexName,
      [
        {
          type: "VECTOR",
          name: "vector",
          attributes: {
            algorithm: "HNSW",
            type: "FLOAT32",
            dimensions: DIM,
            distanceMetric: "COSINE",
          },
        },
      ],
      { dataType: "HASH", prefixes: [keyPrefix] }
    );
    console.log(`Created index ${indexName}`);

    // 2. Store one chunk as a HASH: vector (bytes) + text + metadata (JSON).
    const text = "Valkey is a high-performance open-source key-value datastore.";
    await client.hset(`${keyPrefix}chunk-1`, {
      vector: floatToBuffer(embed(text)),
      text,
      metadata: JSON.stringify({ title: "Valkey", text }),
    });
    console.log("Stored 1 chunk");

    // 3. KNN search. The query vector is bound via PARAMS ($BLOB) — never
    // string-interpolated — and DIALECT 2 is required for vector queries.
    const topN = 3;
    const [count, docs] = await GlideFt.search(
      client,
      indexName,
      `*=>[KNN ${topN} @vector $BLOB AS score]`,
      {
        params: [{ key: "BLOB", value: floatToBuffer(embed("key value store")) }],
        returnFields: [
          { fieldIdentifier: "text" },
          { fieldIdentifier: "score" },
        ],
        limit: { offset: 0, count: topN },
        dialect: 2,
      }
    );

    console.log(`Search returned ${count} match(es):`);
    for (const doc of docs) {
      const fields = Object.fromEntries(
        doc.value.map((f) => [toStr(f.key), toStr(f.value)])
      );
      // COSINE distance -> similarity. valkey-search returns the distance in
      // `score`; similarity = 1 - distance, clamped into [0, 1].
      const similarity = Math.max(0, Math.min(1, 1 - Number(fields.score)));
      console.log(`  ${toStr(doc.key)} (similarity ${similarity.toFixed(3)}): ${fields.text}`);
    }

    // The query is semantically close to the stored chunk, so we expect a hit.
    if (count < 1) throw new Error("Expected at least one match — check that valkey-search is loaded.");
    console.log("\nGetting-started flow complete.");
  } finally {
    // Always close the client so the script doesn't hang on an open socket.
    await client.close();
  }
}

main().catch((e) => {
  console.error("Failed:", e.message);
  console.error("Is Valkey running with the search module? Try: docker exec valkey-search valkey-cli FT._LIST");
  process.exit(1);
});
```

Run it:

```bash
node getting-started.js
```

**Expected output:**

```text
Created index allm_idx_demo
Stored 1 chunk
Search returned 1 match(es):
  allm:demo:chunk-1 (similarity 0.xxx): Valkey is a high-performance open-source key-value datastore.

Getting-started flow complete.
```

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| Create namespace index | `FT.CREATE allm_idx_{ns} ON HASH PREFIX 1 allm:{ns}: SCHEMA vector VECTOR HNSW ... DIM n DISTANCE_METRIC COSINE` | One HNSW index per workspace |
| Store a chunk | `HSET allm:{ns}:{id} vector <f32le> text <str> metadata <json>` | The `vector` field is indexed; `text`/`metadata` are stored fields |
| Retrieve | `FT.SEARCH allm_idx_{ns} "*=>[KNN k @vector $BLOB AS score]" PARAMS 2 BLOB <f32le> DIALECT 2` | KNN over the HNSW graph, query vector bound as a parameter |

`GlideFt.create` / `GlideFt.search` are the typed wrappers GLIDE exposes for these module commands. AnythingLLM's provider issues the same commands through `customCommand` (with RESP2 reply parsing) for fine-grained control, but the operations are identical.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `unknown command 'FT.CREATE'` | The search module isn't loaded. Use the `valkey/valkey-bundle` image, not plain `valkey/valkey`. |
| Connection timeout off-localhost | Raise `requestTimeout` (the provider's `VALKEY_VECTOR_DB_REQUEST_TIMEOUT`); GLIDE defaults to 250ms. |
| `Search returned 0 matches` | Indexing is asynchronous — the chunk may not be indexed yet. In a real app, poll `FT.INFO num_docs`; see [02](02-vector-search.md). |
| AnythingLLM falls back to LanceDB | `VECTOR_DB` isn't set to `valkey`, or the value didn't persist. Re-check the admin UI / env. |

[Next: 02 Vector Search & Retrieval →](02-vector-search.md)
