# Vector Search

**Intermediate** · Python / TypeScript · ~20 min

## What You'll Build

The gateway's `valkey-search` provider wraps Valkey's `FT.*` search commands behind a REST API. You reach it through the Portkey SDK's generic request methods (`post`, `get`, `delete`), so the same client you use for LLM calls also manages vector indexes — no direct Valkey connection needed from your app.

This cookbook walks through the full CRUD lifecycle: create an index, upsert documents, search by vector similarity with optional TAG filters, and clean up.

## Prerequisites

* Docker or Podman installed (Valkey running from Getting Started)
* Gateway running with `VALKEY_CONNECTION_STRING` set
* `portkey-ai` SDK installed

## Step 1: Create a Client for the valkey-search Provider

Select the `valkey-search` provider and pass the Valkey address via `custom_host`. The same SDK methods work in both languages.

**Python**

```python
from portkey_ai import Portkey

client = Portkey(
    api_key="dummy",
    base_url="http://localhost:8787/v1",
    provider="valkey-search",
    custom_host="valkey://localhost:6379",
)
```

**TypeScript**

```typescript
import { Portkey } from "portkey-ai";

const client = new Portkey({
  apiKey: "dummy",
  baseURL: "http://localhost:8787/v1",
  provider: "valkey-search",
  customHost: "valkey://localhost:6379",
});
```

## Step 2: Create a Vector Index

**Python**

```python
client.post(
    "/indexes",
    name="documents",
    schema={
        "vector": {
            "type": "VECTOR",
            "algorithm": "HNSW",
            "dims": 3,        # toy dimension for this demo — use 1536 for text-embedding-ada-002, 768 for MiniLM, etc.
            "distance": "COSINE",
        },
        "content": {"type": "TEXT"},
        "source": {"type": "TAG"},
    },
    options={"prefix": "documents:"},
)
```

**TypeScript**

```typescript
await client.post("/indexes", {
  name: "documents",
  schema: {
    vector: {
      type: "VECTOR",
      algorithm: "HNSW",
      dims: 3, // toy dimension for this demo — use 1536 for text-embedding-ada-002, 768 for MiniLM, etc.
      distance: "COSINE",
    },
    content: { type: "TEXT" },
    source: { type: "TAG" },
  },
  options: { prefix: "documents:" },
});
```

## Step 3: Upsert Documents with Embeddings

**Python**

```python
client.post(
    "/indexes/documents/upsert",
    documents=[
        {"id": "doc1", "vector": [0.1, 0.2, 0.3],
         "fields": {"content": "Valkey is a high-performance key-value store", "source": "docs"}},
        {"id": "doc2", "vector": [0.4, 0.5, 0.6],
         "fields": {"content": "Vector search finds similar items by embedding distance", "source": "tutorial"}},
        {"id": "doc3", "vector": [0.11, 0.21, 0.31],
         "fields": {"content": "Valkey supports HNSW and FLAT indexing algorithms", "source": "docs"}},
    ],
)
```

**TypeScript**

```typescript
await client.post("/indexes/documents/upsert", {
  documents: [
    { id: "doc1", vector: [0.1, 0.2, 0.3], fields: { content: "Valkey is a high-performance key-value store", source: "docs" } },
    { id: "doc2", vector: [0.4, 0.5, 0.6], fields: { content: "Vector search finds similar items by embedding distance", source: "tutorial" } },
    { id: "doc3", vector: [0.11, 0.21, 0.31], fields: { content: "Valkey supports HNSW and FLAT indexing algorithms", source: "docs" } },
  ],
});
```

## Step 4: Search by Vector Similarity

Find the two most similar documents to a query vector. Results are ordered by cosine distance (lower `__score` = more similar).

**Python**

```python
# Use a query vector distinct from stored documents so ranking is non-trivial
results = client.post(
    "/indexes/documents/search",
    vector=[0.12, 0.22, 0.32],
    top_k=2,
    return_fields=["content", "source", "__score"],
)
print(dict(results)["data"])
```

**TypeScript**

```typescript
// Use a query vector distinct from stored documents so ranking is non-trivial
const results = await client.post("/indexes/documents/search", {
  vector: [0.12, 0.22, 0.32],
  top_k: 2,
  return_fields: ["content", "source", "__score"],
});
console.log(results.data);
```

## Step 5: Filter with TAG Fields

Combine vector search with metadata filtering — only documents tagged `source:docs` are searched.

**Python**

```python
client.post(
    "/indexes/documents/search",
    vector=[0.12, 0.22, 0.32],
    top_k=5,
    filter="@source:{docs}",
    return_fields=["content", "__score"],
)
```

**TypeScript**

```typescript
await client.post("/indexes/documents/search", {
  vector: [0.12, 0.22, 0.32],
  top_k: 5,
  filter: "@source:{docs}",
  return_fields: ["content", "__score"],
});
```

## Step 6: Inspect and Clean Up

**Python**

```python
info = client.get(path="/indexes/documents").json()  # FT.INFO
client.delete(path="/indexes/documents")             # FT.DROPINDEX
```

**TypeScript**

```typescript
const info = await client.get("/indexes/documents");   // FT.INFO
await client.delete("/indexes/documents");             // FT.DROPINDEX
```

## How It Works Under the Hood

| SDK Call | Gateway Endpoint | Valkey Command |
|----------|-----------------|----------------|
| `post("/indexes", ...)` | `POST /v1/indexes` | `FT.CREATE` |
| `post("/indexes/:n/upsert", ...)` | `POST /v1/indexes/:n/upsert` | `HSET` per document |
| `post("/indexes/:n/search", ...)` | `POST /v1/indexes/:n/search` | `FT.SEARCH` with KNN clause |
| `get(path="/indexes/:n")` | `GET /v1/indexes/:n` | `FT.INFO` |
| `delete(path="/indexes/:n")` | `DELETE /v1/indexes/:n` | `FT.DROPINDEX` |

**Source:** [`src/providers/valkey-search/handlers.ts`](https://github.com/Portkey-AI/gateway/blob/main/src/providers/valkey-search/handlers.ts)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Invalid custom host` (400) | The `custom_host` must include the scheme: `valkey://host:port` |
| `NotFoundError` (404) | Create the index first with `post("/indexes", ...)` |
| `Service temporarily unavailable` (503) | Valkey is unreachable from the gateway; check connectivity |
| Empty search results | Wait ~1s after upsert for the index to update, or verify vector dimensions match |
| `ConflictError` (409) | Index already exists; drop it first or use a different name |

---

[03 - Production with ElastiCache →](03-production.md)
