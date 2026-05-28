# How It Works

> The index schema, data model, and search mechanics inside Valkey when Kilocode indexes your codebase.

**Intermediate** · TypeScript · ~15 min

When you select "Valkey" in Kilocode's settings, the `kilo-indexing` package uses `@valkey/valkey-glide` to create a ValkeySearch index, store code chunk embeddings as HASH keys, and query them with KNN.

## Step 1: The ValkeySearch Index Schema

Kilocode creates an HNSW index on HASH keys with this schema:

```
FT.CREATE <collectionName>
  ON HASH
  PREFIX 1 <collectionName>:
  SCHEMA
    vector VECTOR HNSW 6 TYPE FLOAT32 DIM <dimensions> DISTANCE_METRIC COSINE
    seg0 TAG
    seg1 TAG
    seg2 TAG
    seg3 TAG
    seg4 TAG
    filePath TAG SEPARATOR \x00
    type TAG
```

The collection name is derived from a SHA-256 hash of your workspace path: `ws-<first 16 hex chars>`.

Key design choices:
- **HNSW algorithm**: approximate nearest-neighbor, fast at scale
- **FLOAT32 encoding**: 4 bytes per dimension
- **COSINE distance**: normalized similarity scoring
- **TAG fields (seg0-seg4)**: path segments for directory-scoped filtering
- **filePath TAG with null separator**: prevents comma tokenization of paths, so exact-match deletion works
- **type TAG**: distinguishes data points from metadata entries

Inspect it yourself:

```bash
# Use FT._LIST to find your index name, then:
docker exec valkey valkey-cli FT.INFO ws-a1b2c3d4e5f67890
```

## Step 2: The Data Model

Each code chunk becomes a HASH key with the pattern `{collectionName}:{pointId}`:

```bash
docker exec valkey valkey-cli HGETALL "ws-a1b2c3d4e5f67890:abc123"
```

Fields stored in each hash:

| Field | Type | Description |
|-------|------|-------------|
| `vector` | Binary (FLOAT32) | Embedding vector, `dim * 4` bytes |
| `type` | TAG | Always `"point"` (distinguishes data from metadata) |
| `filePath` | TAG | Full relative file path (e.g., `src/utils/validation.ts`) |
| `codeChunk` | String | The actual source code text for this chunk |
| `startLine` | String | Starting line number in the source file |
| `endLine` | String | Ending line number in the source file |
| `seg0` | TAG | First path segment (e.g., `src`) |
| `seg1` | TAG | Second path segment (e.g., `utils`) |
| `seg2` | TAG | Third path segment (e.g., `validation.ts`) |
| `seg3` | TAG | Fourth path segment (if present) |
| `seg4` | TAG | Fifth path segment (if present) |

There's also a single metadata key at `{collectionName}:__metadata__` that stores the embedding profile:

```bash
docker exec valkey valkey-cli HGETALL "ws-a1b2c3d4e5f67890:__metadata__"
# type: metadata
# indexing_complete: true
# embedding_provider: openai
# embedding_model_id: text-embedding-3-small
# embedding_dimension: 1536
```

The vector is encoded as a raw FLOAT32 buffer:

```typescript
encodeVector(vector: number[]): Buffer {
  const buffer = Buffer.alloc(vector.length * 4);
  for (let i = 0; i < vector.length; i++) {
    buffer.writeFloatLE(vector[i], i * 4);
  }
  return buffer;
}
```

## Step 3: Directory-Scoped Search with TAG Filtering

When you search within a specific directory, Kilocode adds TAG filters to the KNN query. For example, searching within `src/utils/`:

```
(@type:{point} @seg0:{src} @seg1:{utils})=>[KNN 10 @vector $BLOB AS score]
```

This means Valkey only considers vectors under that path, reducing the search space for large codebases.

The full search query format:

```typescript
const query = "(@type:{point})=>[KNN K @vector $BLOB AS score]";
// With directory filter:
const query = "(@type:{point} @seg0:{src} @seg1:{utils})=>[KNN K @vector $BLOB AS score]";
```

Search is executed via GLIDE:

```typescript
import { GlideFt } from "@valkey/valkey-glide";

const [_count, documents] = await GlideFt.search(client, collectionName, query, {
  params: [{ key: "BLOB", value: encodedVector }],
  returnFields: [
    { fieldIdentifier: "filePath" },
    { fieldIdentifier: "codeChunk" },
    { fieldIdentifier: "startLine" },
    { fieldIdentifier: "endLine" },
    { fieldIdentifier: "score" },
  ],
  dialect: 2,
  limit: { offset: 0, count: maxResults },
});
```

The result is a tuple: `[totalCount, documents]`. Each document has a `key` (the hash key) and `value` (array of field entries). The `score` field is the cosine distance (0 = identical, 2 = opposite). Kilocode converts it to similarity: `1 - distance`.

Results with similarity below 0.4 (cosine distance > 0.6) are filtered out by default (`DEFAULT_SEARCH_MIN_SCORE = 0.4`). The default maximum number of results returned is 50 (`DEFAULT_MAX_SEARCH_RESULTS = 50`).

## Step 4: Batch Upserts via GLIDE Pipelines

Kilocode doesn't insert vectors one at a time. It batches them using non-atomic GLIDE `Batch` pipelines, 1000 points per batch:

```typescript
import { GlideClient, Batch } from "@valkey/valkey-glide";
import type { GlideString } from "@valkey/valkey-glide";

const BATCH_CHUNK_SIZE = 1000;

for (let i = 0; i < points.length; i += BATCH_CHUNK_SIZE) {
  const chunk = points.slice(i, i + BATCH_CHUNK_SIZE);
  const batch = new Batch(false); // non-atomic pipeline

  for (const point of chunk) {
    const key = `${collectionName}:${point.id}`;
    const fields: Record<string, GlideString> = {
      vector: encodeVector(point.vector),
      filePath: point.payload.filePath,
      codeChunk: point.payload.codeChunk,
      startLine: String(point.payload.startLine),
      endLine: String(point.payload.endLine),
      type: "point",
      ...splitPathSegments(point.payload.filePath),
    };
    batch.hset(key, fields);
  }

  await client.exec(batch, true); // raise on first error
}
```

This minimizes round-trips and keeps indexing fast for large codebases. Non-atomic mode (`new Batch(false)`) means partial success is possible: if one write fails, the rest still complete.

## Step 5: Embedding Metadata and Re-indexing

Kilocode stores metadata about the embedding model in `{collectionName}:__metadata__`. When you change models or dimensions, it detects the mismatch and re-indexes:

```bash
docker exec valkey valkey-cli HGETALL "ws-a1b2c3d4e5f67890:__metadata__"
# type: metadata
# indexing_complete: true
# embedding_provider: openai
# embedding_model_id: text-embedding-3-small
# embedding_dimension: 1536
```

The initialization logic checks three conditions:
1. **Dimension mismatch**: index vector dimension doesn't match the configured model. Drop and recreate.
2. **Provider/model mismatch**: stored profile differs from current config. Drop and recreate.
3. **Missing metadata**: no profile stored but documents exist. Drop and recreate.

In practice:
- Switching embedding models triggers a full re-index
- Dimension changes are caught automatically
- No manual cleanup needed
- The `indexing_complete` flag tracks whether indexing finished

## Step 6: Inspect Everything with valkey-cli

Useful commands for understanding what Kilocode stored:

```bash
# List all indexes
docker exec valkey valkey-cli FT._LIST

# Index details (field count, doc count, memory usage)
docker exec valkey valkey-cli FT.INFO ws-a1b2c3d4e5f67890

# Count indexed documents
docker exec valkey valkey-cli FT.SEARCH ws-a1b2c3d4e5f67890 "*" LIMIT 0 0

# View the metadata entry
docker exec valkey valkey-cli HGETALL "ws-a1b2c3d4e5f67890:__metadata__"

# Find all chunks in src/utils/
docker exec valkey valkey-cli FT.SEARCH ws-a1b2c3d4e5f67890 "@seg0:{src} @seg1:{utils}" LIMIT 0 10
```

> Your actual collection name is `ws-` followed by the first 16 hex characters of the SHA-256 hash of your workspace path. Use `FT._LIST` to discover it.

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
