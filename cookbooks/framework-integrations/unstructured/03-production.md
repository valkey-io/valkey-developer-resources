# Production Deployment

> Configure TLS, authentication, TTL lifecycle, HNSW tuning, and batch
> strategies for production Unstructured + Valkey deployments.

**Advanced** · Python · ~20 min

**Who is this for:** Platform engineers deploying document ingestion pipelines
with Valkey as the vector store in production environments (cloud or
self-hosted).

## Prerequisites

- Completed [01 Getting Started](01-getting-started.md) and
  [02 Ingestion & Search](02-ingestion-and-search.md)
- Familiarity with Valkey authentication and TLS concepts
- Access to a Valkey instance (local for testing, or cloud for production)

## Step 1: Enable Authentication and TLS

For production, always use authentication and TLS:

```python
from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig,
    ValkeyConnectionConfig,
    ValkeyUploader,
    ValkeyUploaderConfig,
)

# Option A: Individual parameters
connection_config = ValkeyConnectionConfig(
    host="valkey.example.com",
    port=6379,
    ssl=True,  # Enable TLS
    username="ingest-user",
    access_config=ValkeyAccessConfig(
        password="strong-password-here",
    ),
)

# Option B: URI with TLS (valkeys:// scheme)
connection_config = ValkeyConnectionConfig(
    access_config=ValkeyAccessConfig(
        uri="valkeys://ingest-user:strong-password@valkey.example.com:6379",
    ),
)
```

### Cloud Provider Connection Strings

| Provider | URI format |
| ---------- | ----------- |
| AWS ElastiCache (Valkey) | `valkeys://user:token@cluster.xxxxx.region.cache.amazonaws.com:6379` |
| GCP Memorystore | `valkeys://user:pass@10.x.x.x:6379` |
| Self-hosted (TLS) | `valkeys://user:pass@host:6379` |

> **Tip:** Store credentials in environment variables or a secrets manager.
> Never hard-code passwords in source files.

```python
import os

connection_config = ValkeyConnectionConfig(
    host=os.environ["VALKEY_HOST"],
    port=int(os.environ.get("VALKEY_PORT", "6379")),
    ssl=True,
    username=os.environ.get("VALKEY_USERNAME"),
    access_config=ValkeyAccessConfig(
        password=os.environ["VALKEY_PASSWORD"],
    ),
)
```

## Step 2: Configure TTL Lifecycle

Use TTL to auto-expire stale documents. This is useful for time-sensitive
content like news articles or support tickets:

```python
upload_config = ValkeyUploaderConfig(
    batch_size=100,
    key_prefix="doc:support:",
    index_name="support_tickets_index",
    ttl_seconds=604800,  # 7 days — tickets expire after a week
)
```

### TTL Strategies

| Strategy | TTL | Use case |
| ---------- | ----- | ---------- |
| No TTL | — | Permanent knowledge base (legal docs, manuals) |
| Short (1–24h) | 3600–86400 | Real-time feeds, session-bound context |
| Medium (7–30d) | 604800–2592000 | Support tickets, news articles |
| Long (90–365d) | 7776000–31536000 | Regulatory docs with retention requirements |

## Step 3: Tune HNSW Index Parameters

The connector creates an HNSW index with default parameters. For production
workloads, you may want to tune these by creating the index manually before
ingestion:

```python
import asyncio
from glide import (
    FtCreateOptions,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    NumericField,
    TagField,
    TextField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
    ft,
)


async def create_tuned_index():
    """Create an HNSW index with production-tuned parameters."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    try:
        schema = [
            TextField("text"),
            TagField("element_type"),
            TagField("source_document"),
            TagField("record_id"),
            NumericField("page_number"),
            VectorField(
                "embedding",
                VectorAlgorithm.HNSW,
                VectorFieldAttributesHnsw(
                    dimensions=384,             # Match your embedding model
                    distance_metric="COSINE",
                    type=VectorType.FLOAT32,
                    # HNSW tuning parameters:
                    # m=32,                     # Connections per node (default 16)
                    # ef_construction=200,      # Build-time search width (default 200)
                    # ef_runtime=100,           # Query-time search width (default 10)
                ),
            ),
        ]

        await ft.create(
            client,
            "documents_index",
            schema,
            FtCreateOptions(prefixes=["doc:unstructured:"]),
        )
        print("✓ Created tuned HNSW index")

    finally:
        await client.close()


asyncio.run(create_tuned_index())
```

### HNSW Tuning Guide

| Parameter | Default | Tuning guidance |
| ----------- | --------- | ---------------- |
| `M` | 16 | Higher = better recall, more memory. 32–64 for high-quality retrieval. |
| `EF_CONSTRUCTION` | 200 | Higher = better index quality, slower build. 200–500 for production. |
| `EF_RUNTIME` | 10 | Higher = better recall at query time, slower queries. 50–200 for production. |

**Trade-offs:**

- **Recall vs. speed:** Higher `EF_RUNTIME` improves recall but increases latency
- **Memory vs. quality:** Higher `M` uses more RAM but produces better graphs
- **Build time vs. quality:** Higher `EF_CONSTRUCTION` makes indexing slower but
  produces better HNSW graphs

For most document search workloads, the defaults work well up to ~100K
documents. Beyond that, consider tuning `M=32` and `EF_RUNTIME=50`.

## Step 4: Batch Strategy for Large Ingestions

The connector uses two write strategies:

1. **Batch pipeline** (first upload, no index exists): Fast bulk writes via
   non-atomic pipeline. Index is created after all data is stored.
2. **Individual HSET** (subsequent uploads, index active): Avoids batch
   timeouts caused by synchronous HNSW indexing during pipeline execution.

For very large initial ingestions (>100K documents), control batch size:

```python
upload_config = ValkeyUploaderConfig(
    batch_size=200,         # Larger batches for initial bulk load
    key_prefix="doc:kb:",
    index_name="knowledge_base_index",
)
```

After the index is created, subsequent uploads automatically switch to
individual writes to avoid the GLIDE batch timeout issue with active HNSW
indexes.

### Recommended Batch Sizes

| Scenario | `batch_size` | Rationale |
| ---------- | ------------- | ----------- |
| Initial bulk load (no index) | 200–500 | Pipeline writes are fast without index overhead |
| Incremental updates (index active) | 50–100 | Individual HSET, batch size affects memory buffering |
| High-dimension vectors (>1024d) | 50 | Larger payloads per element |

## Step 5: Cluster Mode

For horizontal scaling, use hash tags in key prefixes to ensure all keys for
a logical group land on the same shard:

```python
# Hash tag ensures all doc: keys map to the same slot
upload_config = ValkeyUploaderConfig(
    key_prefix="{docs}:unstructured:",  # Hash tag: {docs}
    index_name="documents_index",
)
```

> **Important:** In cluster mode, the FT Search index only covers keys on
> the node where it's created. Use hash tags to co-locate all indexed keys.

## Step 6: Monitoring and Observability

### Index Health

Monitor your index with `FT.INFO`:

```python
async def check_index_health():
    """Report index statistics."""
    from glide import GlideClient, GlideClientConfiguration, NodeAddress, ft

    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    try:
        info = await ft.info(client, "documents_index")
        print(f"Documents indexed: {info.get('num_docs', 0)}")
        print(f"Index size (bytes): {info.get('inverted_sz_mb', 0)}")
        print(f"Indexing progress: {info.get('percent_indexed', 1.0) * 100:.1f}%")
    finally:
        await client.close()


asyncio.run(check_index_health())
```

### Key Metrics to Monitor

| Metric | Source | Alert threshold |
| -------- | -------- | ----------------- |
| `percent_indexed` | `FT.INFO` | < 1.0 means indexing in progress |
| `num_docs` | `FT.INFO` | Compare with expected doc count |
| Memory usage | `INFO memory` | Track `used_memory` growth |
| Latency | Client-side timing | P99 > 50ms for KNN queries |
| Connection errors | Application logs | Any `DestinationConnectionError` |

### Error Handling in Production

The connector maps GLIDE exceptions to typed errors for retry logic:

```python
from unstructured_ingest.error import (
    DestinationConnectionError,
    TimeoutError,
    UserAuthError,
    WriteError,
)

# Transient (retry-safe):
# - TimeoutError → increase request_timeout or reduce batch_size
# - DestinationConnectionError → check network, retry with backoff

# Permanent (do not retry):
# - UserAuthError → fix credentials
# - WriteError → fix data (bad element_id, wrong dimension, etc.)
```

## Configuration Reference

### Production Checklist

| Item | Setting | Notes |
| ------ | --------- | ------- |
| TLS | `ssl=True` | Required for non-localhost |
| Auth | `username` + `password` | Use ACL with minimal permissions |
| Timeout | `request_timeout=30000` | Increase for large batches |
| TTL | `ttl_seconds` | Set based on content freshness needs |
| Prefix | `key_prefix` with hash tag | Required for cluster mode |
| Batch size | 50–200 | Tune based on vector dimension |
| Distance metric | `COSINE` | Match your embedding model's training |

### ACL Permissions (Minimum Required)

```text
ACL SETUSER ingest-user on >password ~doc:unstructured:* &documents_index +@hash +@search +@generic +PING +INFO
```

This grants:

- Read/write on keys matching the prefix
- Access to the FT index
- PING and INFO for health checks

## Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| `UserAuthError` | Wrong credentials or insufficient ACL | Verify ACL grants match key prefix and index |
| `TimeoutError` on upload | Batch too large with active index | Reduce `batch_size` or increase `request_timeout` |
| High memory after bulk load | HNSW graph construction | Expected — memory stabilizes after indexing completes |
| Slow queries (>50ms) | Low `EF_RUNTIME` | Increase runtime search width via index re-creation |
| "CROSSSLOT" error | Keys span multiple slots in cluster | Use hash tags in `key_prefix` |

---

[← 02 - Ingestion & Search](02-ingestion-and-search.md)
