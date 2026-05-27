# Production Deployment

> Deploy Upsonic with Valkey in production: cluster mode, ElastiCache, batch operations, content deduplication, and monitoring.

**Advanced** · Python · ~15 min

## Cluster Mode

For production workloads, use a Valkey cluster to distribute data across shards:

```python
from upsonic.vectordb import ValkeyProvider, ValkeyConfig
from upsonic.vectordb.config import ConnectionConfig, Mode, DistanceMetric

config = ValkeyConfig(
    vector_size=1536,
    collection_name="production_docs",
    key_prefix="{prod}:",
    connection=ConnectionConfig(
        mode=Mode.CLOUD,
        host="my-cluster.abc123.clustercfg.us-east-1.cache.amazonaws.com",
        port=6379,
        use_tls=True,
    ),
    distance_metric=DistanceMetric.COSINE,
    cluster_mode=True,  # Use GlideClusterClient
    batch_size=200,
    request_timeout=5000,  # 5 seconds
)

provider = ValkeyProvider(config)
```

> ⚠️ **Cluster mode requires hash-tagged prefixes** (e.g., `{prod}:`) so that all
> keys and the FT index land on the same shard. Without this, search returns
> partial results.

Setting `cluster_mode=True` switches from `GlideClient` to `GlideClusterClient`, which auto-discovers cluster topology from the seed node.

## TLS / ElastiCache

For ElastiCache Serverless or any TLS-enabled endpoint, configure the connection with TLS mode:

```python
config = ValkeyConfig(
    vector_size=1536,
    collection_name="production_docs",
    key_prefix="{prod}:",
    connection=ConnectionConfig(
        mode=Mode.CLOUD,
        host="my-cache.serverless.us-east-1.cache.amazonaws.com",
        port=6379,
        use_tls=True,
    ),
    cluster_mode=True,
    batch_size=200,
)
```

> **Authentication:** For ElastiCache IAM authentication, configure GLIDE with
> explicit `IamAuthConfig`. See the [GLIDE IAM integration guide](https://glide.valkey.io/how-to/security/iam-integration/)
> for setup details. Never hardcode credentials.

## Batch Operations

The provider automatically batches upserts according to `batch_size`. For large ingestion jobs, tune this based on your network and Valkey capacity:

```python
import asyncio
from upsonic.vectordb import ValkeyProvider, ValkeyConfig
from upsonic.vectordb.config import ConnectionConfig, Mode

config = ValkeyConfig(
    vector_size=384,
    collection_name="bulk_ingest",
    key_prefix="bulk:",
    connection=ConnectionConfig(mode=Mode.LOCAL, host="localhost", port=6379),
    batch_size=500,  # Process 500 documents per batch
)

provider = ValkeyProvider(config)


async def bulk_ingest(vectors, ids, chunks, doc_ids, doc_names):
    """Ingest a large dataset. Batching is handled automatically."""
    await provider.aconnect()
    try:
        await provider.acreate_collection()

        await provider.aupsert(
            vectors=vectors,
            ids=ids,
            chunks=chunks,
            document_ids=doc_ids,
            document_names=doc_names,
        )
    finally:
        await provider.adisconnect()
```

| `batch_size` | Trade-off |
|-------------|-----------|
| 50–100 | Safe for limited-memory Valkey instances |
| 200–500 | Good balance for production clusters |
| 1000+ | Maximum throughput, requires sufficient Valkey memory headroom |

## Content Deduplication

The provider computes an MD5 hash of each chunk's content (`chunk_content_hash`). Use this to avoid re-indexing identical content:

> **Note:** MD5 is used here as a fast content fingerprint for deduplication, not for security. This is dictated by Upsonic's internal `store.py` which uses `hashlib.md5` for all providers.

```python
async def ingest_with_dedup(provider, chunk_text, chunk_id, vector, doc_id, doc_name):
    """Skip chunks that already exist in the index."""
    import hashlib
    content_hash = hashlib.md5(chunk_text.encode()).hexdigest()

    if await provider.achunk_content_hash_exists(content_hash):
        print(f"Skipping duplicate: {chunk_id}")
        return

    await provider.aupsert(
        vectors=[vector],
        ids=[chunk_id],
        chunks=[chunk_text],
        document_ids=[doc_id],
        document_names=[doc_name],
    )
```

This is especially useful for incremental ingestion pipelines where documents are re-processed periodically.

> **Note:** This check-then-insert pattern is not atomic. For concurrent ingestion
> pipelines, use a `SET NX` lock on the content hash or accept occasional duplicates
> with periodic dedup passes.

## Delete Operations

### Delete by ID

```python
await provider.adelete(ids=["chunk_1", "chunk_2"])
```

Uses `UNLINK` for non-blocking deletion in a single round-trip.

### Delete by Document

Remove all chunks belonging to a document:

```python
# Delete all chunks from a specific document
await provider.adelete_by_document_name(document_name="outdated_doc.md")

# Delete by document ID
await provider.adelete_by_document_id(document_id="doc_123")
```

### Drop the Entire Index

```python
await provider.adelete_collection()
```

## Monitoring

### Index Stats

```bash
# Index info (doc count, memory, indexing status)
valkey-cli FT.INFO production_docs

# Key count under the prefix
valkey-cli DBSIZE
```

### Key Metrics to Watch

| Metric | Source | What It Tells You |
|--------|--------|-------------------|
| `num_docs` | `FT.INFO` | Total indexed documents |
| `indexing` | `FT.INFO` | Whether background indexing is in progress |
| `used_memory_human` | `INFO memory` | Total Valkey memory consumption |
| `keyspace_hits/misses` | `INFO stats` | Cache effectiveness for repeated queries |

### Memory Estimation

```
Memory per vector ≈ vector_size × 4 bytes (float32) + HNSW graph overhead
HNSW graph overhead ≈ m × 2 × 8 bytes per layer (bidirectional neighbor links)
Average layers per node ≈ 1/ln(2) ≈ 1.4 (plus internal node bookkeeping)
```

For 384-dim vectors with m=16:
- Vector data: 384 × 4 = 1,536 bytes (~1.5 KB)
- HNSW graph links: m × 2 × 8 × ~1.4 layers + overhead ≈ ~2 KB
- Metadata fields (content, tags, hashes): ~0.5 KB
- **Total per chunk: ~4 KB**

At 1M chunks: ~4 GB Valkey memory.

## Error Handling

The provider raises specific exceptions for different failure modes:

```python
import logging
from upsonic.utils.package.exception import (
    VectorDBConnectionError,
    CollectionDoesNotExistError,
    SearchError,
)

logger = logging.getLogger(__name__)

async def safe_search(provider, query_vector):
    """Search with proper error handling."""
    try:
        return await provider.adense_search(
            query_vector=query_vector,
            top_k=5,
        )
    except VectorDBConnectionError:
        # Valkey unreachable — retry or failover
        raise
    except CollectionDoesNotExistError:
        # Index not created yet
        await provider.acreate_collection()
        return await provider.adense_search(
            query_vector=query_vector,
            top_k=5,
        )
    except SearchError as e:
        # Query-level error (bad vector dimensions, etc.)
        logger.error("Search failed: %s", e)
        return []
```

## Full Production Configuration

```python
from upsonic.vectordb import ValkeyProvider, ValkeyConfig
from upsonic.vectordb.config import (
    ConnectionConfig, Mode, DistanceMetric, HNSWIndexConfig,
)

config = ValkeyConfig(
    vector_size=1536,                    # text-embedding-3-small
    collection_name="prod_knowledge",
    key_prefix="{kb}:",
    connection=ConnectionConfig(
        mode=Mode.CLOUD,
        host="my-cluster.clustercfg.us-east-1.cache.amazonaws.com",
        port=6379,
        use_tls=True,
    ),
    distance_metric=DistanceMetric.COSINE,
    index=HNSWIndexConfig(m=32, ef_construction=400),
    ef_runtime=150,
    cluster_mode=True,
    batch_size=300,
    request_timeout=5000,
    rrf_k=60,
)

provider = ValkeyProvider(config)
```

---

[← 02 - Search Strategies](02-search-strategies.md)
