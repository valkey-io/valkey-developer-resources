# Production Deployment

> Connection security, shared indexing, error handling, memory sizing, and monitoring for team-scale Valkey deployments.

**Advanced** · TypeScript · ~15 min

For individual developers, a local Docker container works. For teams sharing a codebase index, you need a production Valkey deployment with proper security, persistence, and monitoring.

## Step 1: Connection Security

Kilocode's `ValkeyVectorStore` connects via `GlideClient.createClient()`. Two security options matter: TLS and password authentication.

### TLS

Use the `rediss://` URL scheme (note the double 's'). Kilocode detects TLS from the URL, no manual flag needed:

```
rediss://valkey.example.com:6379
```

Under the hood:

```typescript
import { GlideClient } from "@valkey/valkey-glide";

const client = await GlideClient.createClient({
  addresses: [{ host: "valkey.example.com", port: 6379 }],
  useTLS: true,
  clientName: "kilo-valkey-store",
  requestTimeout: 5000,
});
```

### Password Authentication

Provide the password in Kilocode's **Valkey Password** field. The password is passed via the `credentials` option rather than embedded in the URL, avoiding URL-encoding issues with special characters:

```typescript
const client = await GlideClient.createClient({
  addresses: [{ host: "valkey.example.com", port: 6379 }],
  useTLS: true,
  credentials: { password: process.env.VALKEY_PASSWORD! },
  clientName: "kilo-valkey-store",
  requestTimeout: 5000,
});
```

### Connection Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `clientName` | `"kilo-valkey-store"` | Identifies Kilocode connections in `CLIENT LIST` |
| `requestTimeout` | `5000` ms | Prevents hanging on unresponsive servers |
| `useTLS` | auto-detected | Enabled when URL uses `rediss://` scheme |

## Step 2: Shared Indexing Across Team Members

When multiple developers point Kilocode at the same Valkey instance, they share the index:

- The first developer indexes the codebase, vectors land in Valkey
- Everyone else connects and searches immediately, no re-indexing
- Index updates happen incrementally when files change

The collection name is `ws-<first 16 hex chars of SHA-256 of workspace path>`, so different projects get separate indexes without conflicts.

### Considerations for shared indexes

| Concern | How Kilocode handles it |
|---------|------------------------|
| Stale vectors from deleted files | Tracks file paths and removes stale entries |
| Concurrent writes | Individual HSET commands are atomic; non-atomic batches allow partial success |
| Different branches | Each developer's local changes trigger incremental re-indexing |
| Embedding model conflicts | Detects provider/model/dimension mismatches and re-indexes automatically |

### Embedding Profile Management

Kilocode stores embedding metadata in `{collectionName}:__metadata__`. When the team switches models:

1. Kilocode compares stored metadata with the current model config
2. If dimensions or model differ, the old index is dropped and rebuilt
3. If metadata is missing but documents exist, same thing: drop and rebuild
4. No manual intervention needed

Ensure all team members use the same embedding model. A mismatch triggers a full re-index, overwriting the shared index.

```bash
# Check the current embedding profile
valkey-cli -h valkey.example.com --tls HGETALL "ws-a1b2c3d4e5f67890:__metadata__"
# type: metadata
# indexing_complete: true
# embedding_provider: openai
# embedding_model_id: text-embedding-3-small
# embedding_dimension: 1536
```

## Step 3: Error Handling

Kilocode's `ValkeyVectorStore` handles connection failures via GLIDE's built-in reconnection logic.

| Scenario | Behavior |
|----------|----------|
| Connection refused on startup | Indexing fails with a clear error; retries on next file change |
| Connection lost mid-operation | `ClosingError` detected, client reference cleared, next operation reconnects |
| Index doesn't exist during search | Returns empty results (no crash) |
| Dimension mismatch on init | Drops and recreates the index |
| Batch upsert partial failure | Non-atomic batch allows partial success; error logged |

For teams building automation around the index, wrap operations defensively:

```typescript
import { ClosingError, RequestError } from "@valkey/valkey-glide";

try {
  const results = await vectorStore.search(queryVector, "src/");
} catch (error) {
  if (error instanceof ClosingError) {
    // Connection lost - next call will reconnect automatically
    console.warn("Valkey connection lost, will retry on next search");
  } else if (error instanceof RequestError) {
    // Command-level error (e.g., index dropped externally)
    console.error("Search command failed:", error.message);
  }
}
```

## Step 4: Memory Sizing

Vector index memory depends on codebase size and embedding dimensions:

| Codebase | Chunks (est.) | 384-dim memory | 1536-dim memory |
|----------|---------------|----------------|-----------------|
| Small (1k files) | ~5,000 | ~15 MB | ~50 MB |
| Medium (10k files) | ~50,000 | ~150 MB | ~500 MB |
| Large (100k files) | ~500,000 | ~1.5 GB | ~5 GB |

HNSW graph overhead adds roughly 30% on top of raw vector storage. Plan accordingly.

**Memory per vector:**
- Raw vector: `dimensions x 4 bytes` (FLOAT32)
- HNSW graph links: 100-200 bytes per point (depends on M parameter)
- Hash fields (filePath, codeChunk, segments): varies by path length and chunk size

Set `maxmemory` with an appropriate eviction policy, or size your instance to hold the full index with headroom for growth.

> **Important:** Set `maxmemory-policy noeviction` on your Valkey instance. ValkeySearch requires all indexed data to remain in memory — eviction policies that remove keys will corrupt the search index.

## Step 5: Monitoring

Track index health with standard Valkey commands (these work on any deployment):

```bash
# Index stats (doc count, memory, indexing errors)
valkey-cli FT.INFO ws-a1b2c3d4e5f67890

# Memory usage
valkey-cli INFO memory

# Connected clients (identify active Kilocode sessions)
valkey-cli INFO clients

# Count indexed documents
valkey-cli FT.SEARCH ws-a1b2c3d4e5f67890 "*" LIMIT 0 0
```

Key metrics to watch:

| Metric | Source | Alert threshold |
|--------|--------|-----------------|
| `num_docs` | `FT.INFO` | Drops unexpectedly (stale index or accidental flush) |
| `used_memory` | `INFO memory` | >80% of available RAM |
| `indexing_failures` | `FT.INFO` | Any non-zero value |
| `connected_clients` | `INFO clients` | Exceeds expected team size |

> Use `FT._LIST` to discover your index name. It follows the pattern `ws-<16 hex chars>`.

## Step 6: Managed Service Deployment

Kilocode works with any Valkey-compatible managed service that has ValkeySearch:

| Provider | Service | ValkeySearch support | TLS |
|----------|---------|---------------------|-----|
| AWS | ElastiCache for Valkey 8.1.1+ | Built-in | Required (`rediss://`) |
| AWS | MemoryDB for Valkey | Built-in | Required (`rediss://`) |
| GCP | Memorystore for Valkey | Built-in | Supported, opt-in at creation (`rediss://`) |
| Self-hosted | Valkey 8.1.1+ with `valkey-bundle` | Included in bundle | Optional |

For any managed service:
1. Use the `rediss://` URL scheme (TLS is typically mandatory)
2. Put the auth token/password in Kilocode's Valkey Password field
3. Confirm the instance has ValkeySearch enabled
4. Size the instance per the memory table above

Consult your provider's docs for cluster creation, networking (VPC/firewall rules), monitoring dashboards, and cost optimization.

## Checklist

- [ ] Valkey 8.1.1+ with ValkeySearch module available
- [ ] TLS enabled (`rediss://` scheme in Kilocode settings)
- [ ] Password configured in Kilocode's Valkey Password field
- [ ] All team members using the same embedding model and dimensions
- [ ] Instance sized for your codebase (see memory table)
- [ ] `maxmemory` configured with appropriate headroom
- [ ] Monitoring on `FT.INFO` doc count and memory usage
- [ ] Network access restricted to developer machines / CI

---

[← 02 - How It Works](02-how-it-works.md)
