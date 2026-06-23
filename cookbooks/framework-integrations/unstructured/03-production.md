# Production Deployment

**Advanced** · Python · ~20 min

## Step 1: ElastiCache for Valkey

ElastiCache for Valkey 8.2+ includes built-in vector search. Use the cluster endpoint as your host:

```python
from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig, ValkeyConnectionConfig, ValkeyUploader, ValkeyUploaderConfig,
)

uploader = ValkeyUploader(
    connection_config=ValkeyConnectionConfig(
        host="your-cluster.xxxxx.use1.cache.amazonaws.com",
        port=6379,
        ssl=True,  # TLS enabled by default in production
        access_config=ValkeyAccessConfig(
            password="your-auth-token",
        ),
        username="default",
        request_timeout=60000,  # higher for cloud latency
    ),
    upload_config=ValkeyUploaderConfig(
        batch_size=100,
        key_prefix="doc:prod:",
        index_name="production_index",
    ),
)
```

Or via URI:

```python
connection_config = ValkeyConnectionConfig(
    access_config=ValkeyAccessConfig(
        uri="valkeys://default:your-token@your-cluster.xxxxx.use1.cache.amazonaws.com:6379"
    ),
)
```

Note: `valkeys://` (with `s`) enables TLS.

## Step 2: TTL for data lifecycle

Set TTL to auto-expire old documents:

```python
upload_config = ValkeyUploaderConfig(
    key_prefix="doc:ephemeral:",
    index_name="ephemeral_index",
    ttl_seconds=86400,  # 24 hours
)
```

Use cases:
- **Temporary ingestion results** — expire after processing
- **Daily refreshed data** — new ingestion overwrites, old keys expire
- **Session-scoped documents** — user uploads that auto-cleanup

Without TTL, documents persist indefinitely until explicitly deleted.

## Step 3: HNSW tuning

The connector creates HNSW indexes with sensible defaults. For production workloads, consider the tradeoffs:

| Parameter | Default | Higher value | Lower value |
|-----------|---------|--------------|-------------|
| Dimensions | Auto-detected | More accurate similarity | Faster search, less memory |
| Distance metric | COSINE | — | Use L2 for normalized vectors |
| M (connections) | 16 | Better recall, more memory | Faster build, less recall |
| EF construction | 200 | Better index quality | Faster index build |

The connector uses COSINE distance and auto-detects dimensions from your embedding model. For most use cases (sentence-transformers, OpenAI, Bedrock), the defaults work well.

To customize, create the index manually before ingestion:

```python
from glide_sync import (
    GlideClient, GlideClientConfiguration, NodeAddress,
    TextField, TagField, NumericField, VectorField,
    VectorAlgorithm, VectorFieldAttributesHnsw, VectorType,
    DistanceMetricType, FtCreateOptions, ft,
)

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=30000,
)
client = GlideClient.create(config)

schema = [
    TextField("text"),
    TagField("element_type"),
    TagField("source_document"),
    NumericField("page_number"),
    VectorField(
        "embedding",
        VectorAlgorithm.HNSW,
        VectorFieldAttributesHnsw(
            dimensions=1536,  # OpenAI text-embedding-3-small
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
            number_of_edges=32,       # M parameter
            initial_cap=10000,        # pre-allocate for expected doc count
        ),
    ),
]

ft.create(client, "custom_index", schema, FtCreateOptions(prefixes=["doc:custom:"]))
client.close()
```

Then point the uploader at the pre-created index:

```python
upload_config = ValkeyUploaderConfig(
    key_prefix="doc:custom:",
    index_name="custom_index",  # uses existing index, skips creation
)
```

## Step 4: Incremental updates

The connector handles re-uploads gracefully:

- **Same document, same data** — keys overwritten (idempotent)
- **New documents to existing index** — individual HSET (index-aware path)
- **Updated documents** — same `element_id` = overwrite; new chunks = new keys

No deduplication logic needed — the key is `{prefix}{element_id}`, and Unstructured generates deterministic IDs from content hashes.

## Step 5: Cluster mode

For Valkey clusters, use a hash-tagged prefix so all keys land in the same slot (required for `FT.SEARCH` to see all documents):

```python
upload_config = ValkeyUploaderConfig(
    key_prefix="{unstructured}:doc:",  # hash tag ensures same slot
    index_name="cluster_index",
)
```

Without the hash tag, keys distribute across slots and search only returns partial results.

## Step 6: Monitoring

Check index health and document count:

```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ft

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=10000,
)
client = GlideClient.create(config)

info = ft.info(client, "production_index")
print(f"Documents: {info[b'num_docs'].decode()}")
print(f"Index size: {info[b'inverted_sz_mb'].decode()} MB")
print(f"Indexing: {info[b'indexing'].decode()}")  # 0 = idle, 1 = backfilling

client.close()
```

Monitor for:
- `num_docs` — matches expected document count
- `indexing` — should be `0` after ingestion completes
- Memory usage — `INFO MEMORY` for overall Valkey memory

## Production checklist

| Area | Recommendation |
|------|---------------|
| **Connection** | TLS (`ssl=True` or `valkeys://`), auth token, `request_timeout=60000` |
| **Data lifecycle** | Set `ttl_seconds` for ephemeral data, omit for permanent |
| **Cluster** | Hash-tagged prefix (`{tag}:prefix:`) for cross-slot search |
| **Embedding model** | Match dimensions to your model (384 for MiniLM, 1536 for OpenAI) |
| **Batch size** | 50-100 for initial loads, individual for incremental |
| **Monitoring** | `FT.INFO` for doc count + index status |
| **High availability** | Multi-AZ ElastiCache with read replicas |

[← Previous: 02 Document Ingestion & Search](02-ingestion-and-search.md)
