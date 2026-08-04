# Production Patterns

> TLS, HNSW tuning, monitoring, and error handling for running Cognee + Valkey in production.

**Advanced** · Python · ~20 min

**Who is this for:** Engineers taking a Cognee + Valkey prototype into production who need TLS, tuned vector indices, observability,
and resilient error handling.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - Knowledge Graph](02-knowledge-graph.md)
- A Valkey deployment reachable over the network (self-hosted, AWS [ElastiCache for Valkey](https://aws.amazon.com/elasticache/) or
  [MemoryDB for Valkey](https://aws.amazon.com/memorydb/), Google Cloud [Memorystore for Valkey](https://cloud.google.com/memorystore),
  or any other managed/self-hosted Valkey with the Search module)

## Step 1: TLS Configuration

The Valkey adapter uses `valkey-glide`, which supports TLS natively. Any Valkey deployment with TLS enabled — self-hosted behind a TLS
proxy, AWS ElastiCache Serverless or MemoryDB, Google Cloud Memorystore for Valkey, or another managed provider — uses the same
`valkeys://` scheme (note the trailing 's'):

```python
import os
from cognee import config
from cognee_community_vector_adapter_valkey import register  # noqa: F401

config.set_vector_db_config({
    "vector_db_provider": "valkey",
    "vector_db_url": os.environ["VECTOR_DB_URL"],  # e.g. valkeys://your-valkey-host:6379
})
```

> **Scheme reference**: Use `valkey://` for plaintext connections (local dev) and `valkeys://` for TLS connections (any production deployment).

Authenticate with whatever mechanism your Valkey deployment provides — ACL users/passwords, or IAM-based auth on managed services.
Never hardcode credentials in application code; read them from environment variables or a secrets manager.

## Step 2: HNSW Tuning

The Valkey adapter creates HNSW indices with default parameters. For production workloads, consider tuning:

| Parameter | Default | Production Range | Effect |
|---|---|---|---|
| `M` | 16 | 16–64 | Higher = better recall, more memory |
| `EF_CONSTRUCTION` | 200 | 200–500 | Higher = better index quality, slower builds |
| `EF_RUNTIME` | 10 | 50–200 | Higher = better recall at query time |

The adapter doesn't currently expose these as constructor parameters. To use custom HNSW parameters, pre-create the index yourself before calling `cognify()`:

```bash
docker exec -it valkey valkey-cli FT.CREATE index:my_collection \
  ON JSON PREFIX 1 vdb:my_collection: \
  SCHEMA \
    '$.id' AS id TAG \
    '$.vector' AS vector VECTOR HNSW 10 \
      TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE \
      M 32 EF_CONSTRUCTION 400 EF_RUNTIME 100
```

## Step 3: Monitoring

### Valkey Metrics

```bash
# Index stats
docker exec -it valkey valkey-cli FT.INFO "index:<collection_name>"

# Memory usage
docker exec -it valkey valkey-cli INFO memory

# Connected clients
docker exec -it valkey valkey-cli INFO clients
```

Key metrics to watch:

- **Vector index size**: `num_docs` in `FT.INFO` output
- **Search latency**: track `FT.SEARCH` execution time
- **Memory usage**: vector indices consume significant RAM — HNSW graphs roughly scale with `num_docs × M × 8 bytes` plus the raw vector storage

If you're on a managed provider (AWS ElastiCache/MemoryDB, Google Cloud Memorystore, etc.), also route these metrics through its
native monitoring integration (CloudWatch, Cloud Monitoring, or your provider's equivalent) for alerting.

### Cognee Logging

```python
import logging
logging.getLogger("ValkeyAdapter").setLevel(logging.INFO)
logging.getLogger("cognee").setLevel(logging.WARNING)
```

## Step 4: Error Handling

`cognify()` and `search()` can both fail — from transient network issues to LLM provider errors. Handle each independently so a single
bad document doesn't abort the whole batch, and provide a fallback search path:

```python
from cognee import add, cognify, search, SearchType
from cognee.modules.search.types import SearchResult

async def safe_add(documents: list[str]) -> int:
    """Add documents with per-document error handling. Returns count added."""
    added = 0
    for doc in documents:
        try:
            await add(doc)
            added += 1
        except Exception as e:
            # In production, narrow this to Cognee/Valkey-specific exceptions
            logging.error("Failed to add document: %s", e)
    return added

async def safe_search(query: str) -> list[SearchResult]:
    """Search with fallback from graph completion to raw chunks on failure."""
    try:
        return await search(query_type=SearchType.GRAPH_COMPLETION, query_text=query)
    except Exception as e:
        logging.warning("Graph search failed, falling back to chunks: %s", e)
        return await search(query_type=SearchType.CHUNKS, query_text=query)
```

See `sample/production_patterns.py` for a complete runnable script combining batch add, cognify, and fallback search.

## Production Checklist

- [ ] TLS enabled (`valkeys://` scheme) for any non-localhost Valkey
- [ ] Authentication configured (ACL/IAM as appropriate for your deployment)
- [ ] HNSW parameters tuned for your dataset size (pre-create the index if overriding defaults)
- [ ] Monitoring on memory usage and `FT.SEARCH`/`FT.INFO` latency
- [ ] Error handling and fallback search strategy in place
- [ ] LLM/embedding provider credentials scoped and rotated per your provider's guidance

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `vector_db_provider` | ✓ | — | Set to `"valkey"` after `register` import |
| `vector_db_url` | ✓ | — | `valkey://host:port` (dev) or `valkeys://host:port` (TLS/production) |
| `EMBEDDING_DIMENSIONS` | ✓ | — | Must match your embedding model's output dimension |

---

[← 02 - Knowledge Graph](02-knowledge-graph.md)
