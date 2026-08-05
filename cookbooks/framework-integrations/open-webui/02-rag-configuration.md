# RAG Configuration with Open WebUI and Valkey

> Tune HNSW parameters, choose distance metrics, and manage collections to optimize
> Open WebUI's retrieval-augmented generation pipeline with Valkey.

**Intermediate** · Docker · ~15 min

**Who is this for:** Operators who have Open WebUI running with Valkey and want to
optimize search quality, understand the indexing parameters, or manage document
collections directly.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Open WebUI running with `VECTOR_DB=valkey`

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Index Algorithms: HNSW vs FLAT

Open WebUI supports both HNSW and FLAT vector indexing via `VALKEY_INDEX_TYPE`:

| Parameter | HNSW (default) | FLAT |
| --- | --- | --- |
| Search speed | O(log n) | O(n) |
| Index memory | Higher (graph structure) | Lower (just vectors) |
| Accuracy | Approximate (tunable) | Exact |
| Best for | > 10K documents | < 10K documents or exact results |

To use FLAT indexing:

```yaml
environment:
  - VECTOR_DB=valkey
  - VALKEY_URL=valkey://valkey:6379
  - VALKEY_INDEX_TYPE=FLAT
```

## HNSW Parameter Tuning

The HNSW algorithm has three key parameters that control the accuracy/speed trade-off:

### M (graph connectivity)

`VALKEY_HNSW_M` controls how many edges each node has in the graph.

| Value | Effect |
| --- | --- |
| 8 | Lower memory, faster indexing, less accurate |
| 16 (default) | Good balance for most workloads |
| 32 | Higher memory, slower indexing, more accurate |
| 64 | Maximum recall, significant memory overhead |

### EF Construction (build-time search width)

`VALKEY_HNSW_EF_CONSTRUCTION` controls how thoroughly the graph is built.

| Value | Effect |
| --- | --- |
| 100 | Faster indexing, slightly lower recall |
| 200 (default) | Good balance |
| 400 | Slower indexing, higher recall |

Higher values mean documents take longer to index but produce better search quality.

### EF Runtime (query-time search width)

`VALKEY_HNSW_EF_RUNTIME` controls how many candidates are examined during search.

| Value | Effect |
| --- | --- |
| 10 (default) | Fast queries, good for top-5 retrieval |
| 50 | Better recall for top-10+ retrieval |
| 100 | Near-exact recall, slower queries |

**Rule of thumb:** `EF_RUNTIME` should be ≥ `topK` (the number of results requested).

### Recommended configurations

```yaml
# Default — good for most RAG workloads
environment:
  - VALKEY_HNSW_M=16
  - VALKEY_HNSW_EF_CONSTRUCTION=200
  - VALKEY_HNSW_EF_RUNTIME=10

# High recall — for critical accuracy (legal, medical docs)
environment:
  - VALKEY_HNSW_M=32
  - VALKEY_HNSW_EF_CONSTRUCTION=400
  - VALKEY_HNSW_EF_RUNTIME=50

# Low memory — for large document sets on constrained hardware
environment:
  - VALKEY_HNSW_M=8
  - VALKEY_HNSW_EF_CONSTRUCTION=100
  - VALKEY_HNSW_EF_RUNTIME=10
  - VALKEY_INDEX_TYPE=FLAT  # Consider FLAT if docs < 10K
```

## Distance Metrics

`VALKEY_DISTANCE_METRIC` determines how similarity is measured:

| Metric | Best For | Score Range |
| --- | --- | --- |
| `COSINE` (default) | General text embeddings (OpenAI, Ollama) | 0.0 (identical) to 2.0 |
| `L2` | Normalized embeddings, image features | 0.0 (identical) to ∞ |
| `IP` | When dot product similarity is desired | Depends on magnitude |

**Recommendation:** Use `COSINE` unless your embedding model documentation
specifically recommends a different metric.

## Collection Management

Open WebUI creates one collection per knowledge base. Collections are isolated via
key prefixes: `{VALKEY_COLLECTION_PREFIX}:{collection_name}:{document_id}`.

### List all collections

```bash
docker exec open-webui-valkey valkey-cli FT._LIST
```

### Inspect a collection

```bash
# Get index details (dimensions, algorithm, field count)
docker exec open-webui-valkey valkey-cli FT.INFO idx:open_webui:my_knowledge_base

# Count indexed documents
docker exec open-webui-valkey valkey-cli FT.SEARCH idx:open_webui:my_knowledge_base "*" LIMIT 0 0
```

### Delete a collection

From the Open WebUI UI: **Workspace** → **Knowledge** → select KB → **Delete**.

Or via CLI:

```bash
# Drop the index
docker exec open-webui-valkey valkey-cli FT.DROPINDEX idx:open_webui:my_knowledge_base

# Delete the data keys (SCAN-based, non-blocking)
docker exec open-webui-valkey valkey-cli --scan --pattern "open_webui:my_knowledge_base:*" | \
  xargs -L 100 docker exec -i open-webui-valkey valkey-cli DEL
```

### Reset all vector data

```bash
# Drop all indices
docker exec open-webui-valkey valkey-cli FT._LIST | while read idx; do
  docker exec open-webui-valkey valkey-cli FT.DROPINDEX "$idx"
done

# Flush all keys (caution: removes ALL data in this Valkey instance)
docker exec open-webui-valkey valkey-cli FLUSHDB
```

## Schema Details

Each document chunk is stored as a Valkey HASH:

| Field | Type | Description |
| --- | --- | --- |
| `id` | TAG | Document chunk ID (for exact-match lookups) |
| `vector` | VECTOR (FLOAT32) | Embedding bytes (little-endian float32 array) |
| `text` | TEXT | Original chunk content |
| `metadata_json` | TEXT | JSON-encoded metadata blob |
| `hash` | TAG | Content hash (deduplication) |
| `file_id` | TAG | Source file identifier |
| `source` | TAG | Source URL or filename |
| `knowledge_base_id` | TAG | Parent knowledge base ID |

The TAG fields enable filtered searches (e.g., "search only within this file").

## Monitoring Index Performance

```bash
# Memory usage per index
docker exec open-webui-valkey valkey-cli FT.INFO idx:open_webui:my_kb | grep -A1 "bytes"

# Overall Valkey memory
docker exec open-webui-valkey valkey-cli INFO memory | grep used_memory_human

# Slow queries (queries taking > 10ms)
docker exec open-webui-valkey valkey-cli SLOWLOG GET 5
```

## Changing Parameters After Creation

HNSW parameters and distance metrics are set at index creation time. To change them:

1. Delete the knowledge base in Open WebUI (or drop the index manually)
2. Update environment variables in docker-compose
3. Restart Open WebUI
4. Re-upload documents (the index will be recreated with new parameters)

The index is auto-created on first document insert with the current configuration.

## Troubleshooting

### "Collection was created with dim=X, refusing to insert vectors with dim=Y"

You changed embedding models after creating a collection. The existing index has a
fixed dimension. Delete the collection and re-ingest with the new model.

### Search returns irrelevant results

- Increase `VALKEY_HNSW_EF_RUNTIME` for better recall
- Check your embedding model — small models (< 768 dims) have lower quality
- Ensure documents are chunked appropriately (too large = diluted embeddings)

### Slow document ingestion

HNSW indexing is CPU-intensive. Options:

- Reduce `VALKEY_HNSW_EF_CONSTRUCTION` (e.g., 100)
- Switch to `VALKEY_INDEX_TYPE=FLAT` for small collections
- Ensure Valkey has enough CPU (it's single-threaded for commands)

---

[→ Next: Production Deployment](03-production-deployment.md) · [← Back to Getting Started](01-getting-started.md)
