# Production Patterns

**Advanced** · Python · ~15 min

## What You'll Build

Production-ready configuration for `ValkeyMemoryService` including TTL-based memory expiry, cluster mode support, TLS connections, observability, and performance tuning.

## Prerequisites

- Completed [01 — Getting Started](01-getting-started.md) and [02 — Vector Memory Search](02-vector-memory-search.md)
- Valkey running with Search module (`valkey-bundle`)
- `google-adk-community[valkey]` and `google-genai` installed

## Step 1: TTL-Based Memory Expiry

Set `ttl_seconds` to automatically expire old memories. This prevents unbounded memory growth and ensures stale context doesn't surface:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_production",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)

    try:
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=768,
                ttl_seconds=86400,  # Memories expire after 24 hours
                similarity_top_k=10,
                vector_distance_threshold=0.6,
            ),
        )

        # Every HSET is followed by EXPIRE in the batch pipeline
        # After 24 hours, entries are automatically removed by Valkey
        print("✅ Memory service with 24h TTL configured")

    finally:
        await client.close()

asyncio.run(main())
```

**TTL guidance:**

| Use case | Recommended TTL |
|----------|----------------|
| Short-term conversation context | 1–4 hours (3600–14400) |
| Daily user preferences | 24 hours (86400) |
| Long-term knowledge | 7–30 days (604800–2592000) |
| Permanent memories | `None` (no expiry) |

## Step 2: Cluster Mode with GlideClusterClient

For production deployments with ElastiCache or MemoryDB, use `GlideClusterClient`:

```python
import asyncio
from glide import GlideClusterClient, GlideClusterClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    # Cluster mode: connect to the configuration endpoint
    cluster_config = GlideClusterClientConfiguration(
        addresses=[NodeAddress(host="my-cluster.abc123.use1.cache.amazonaws.com", port=6379)],
        client_name="adk_memory_cluster",
        request_timeout=5000,
        use_tls=True,  # Always use TLS in production
    )
    client = await GlideClusterClient.create(cluster_config)

    try:
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        # ValkeyMemoryService works with both GlideClient and GlideClusterClient
        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=768,
                similarity_top_k=10,
                ttl_seconds=86400,
            ),
        )
        await memory_service.create_index()
        print("✅ Connected to Valkey cluster with TLS")

    finally:
        await client.close()

asyncio.run(main())
```

## Step 3: Environment-Driven Configuration

Use environment variables for deployment flexibility:

```python
import asyncio
import os
from glide import GlideClient, GlideClusterClient
from glide import GlideClientConfiguration, GlideClusterClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    host = os.environ.get("VALKEY_HOST", "localhost")
    port = int(os.environ.get("VALKEY_PORT", "6379"))
    use_tls = os.environ.get("VALKEY_TLS", "false").lower() == "true"
    cluster_mode = os.environ.get("VALKEY_CLUSTER", "false").lower() == "true"
    ttl = int(os.environ.get("MEMORY_TTL_SECONDS", "86400"))

    if cluster_mode:
        config = GlideClusterClientConfiguration(
            addresses=[NodeAddress(host=host, port=port)],
            client_name="adk_memory_service",
            request_timeout=5000,
            use_tls=use_tls,
        )
        client = await GlideClusterClient.create(config)
    else:
        config = GlideClientConfiguration(
            addresses=[NodeAddress(host=host, port=port)],
            client_name="adk_memory_service",
            request_timeout=5000,
            use_tls=use_tls,
        )
        client = await GlideClient.create(config)

    try:
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=768,
                ttl_seconds=ttl,
                similarity_top_k=10,
            ),
        )
        await memory_service.create_index()
        print(f"✅ Connected to {host}:{port} (TLS={use_tls}, cluster={cluster_mode})")

    finally:
        await client.close()

asyncio.run(main())
```

## Step 4: Observability

`ValkeyMemoryService` logs via Python's `logging` module under the `google_adk` namespace. Configure structured logging for production:

```python
import logging

# Enable debug logging for memory operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_adk")
logger.setLevel(logging.DEBUG)

# Key log messages:
# INFO  "Created search index: adk_memory_idx"
# INFO  "Added 5 memories via batch pipeline"
# INFO  "Found 3 memories for query: 'user preferences'"
# ERROR "Failed to generate embeddings: ..."
# ERROR "Failed to execute batch pipeline: ..."
```

Set `client_name` on `GlideClientConfiguration` — it appears in `CLIENT LIST`, slow-log entries, and CloudWatch metrics for ElastiCache, making it easy to trace which service is generating traffic.

## Step 5: Performance Tuning

### Embedding Batch Size

The embedding function receives all event texts in a single batch call. For large sessions, consider batching at the provider level:

```python
import asyncio

# Create client once at module scope
from google import genai
genai_client = genai.Client()

async def embed_texts_batched(texts: list[str]) -> list[list[float]]:
    """Batch-aware embedding function with rate limiting."""
    batch_size = 100  # Provider-specific limit
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await genai_client.models.embed_content_async(
            model="text-embedding-004",
            contents=batch,
        )
        all_embeddings.extend([e.values for e in response.embeddings])
        # Rate limiting between batches if needed
        if i + batch_size < len(texts):
            await asyncio.sleep(0.1)

    return all_embeddings
```

### Key Prefix Isolation

Use distinct `key_prefix` values to separate environments or tenants:

```python
from google.adk_community.memory import ValkeyMemoryServiceConfig

# Per-environment isolation
dev_config = ValkeyMemoryServiceConfig(
    key_prefix="dev:adk:memory",
    index_name="dev_adk_memory_idx",
    embedding_dimensions=768,
)

prod_config = ValkeyMemoryServiceConfig(
    key_prefix="prod:adk:memory",
    index_name="prod_adk_memory_idx",
    embedding_dimensions=768,
)
```

### Request Timeout

The default GLIDE client timeout is 250ms, which causes failures over network links. Always set `request_timeout`:

| Deployment | Recommended timeout |
|-----------|-------------------|
| Localhost | 1000ms |
| Same-region VPC | 2000–5000ms |
| Cross-region | 5000–10000ms |

## How It Works Under the Hood

| Operation | Valkey Command | Production Note |
|-----------|---------------|----------------|
| Batch pipeline | Multiple `HSET` + `EXPIRE` in one round-trip | Reduces network overhead |
| TTL | `EXPIRE adk:memory:{uuid} 86400` | Automatic cleanup, no cron needed |
| Cluster routing | Automatic via GlideClusterClient | Hash-slot aware key routing |
| TLS | Connection-level encryption | Required for ElastiCache/MemoryDB |
| Index check | `FT.CREATE` with "already exists" handling | Idempotent, safe on restart |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `CROSSSLOT` error in cluster mode | `ValkeyMemoryService` uses single-key operations (HSET + EXPIRE per entry), so CROSSSLOT errors are unlikely. If you need multi-key atomicity (e.g., batch DEL), use hash-tag syntax in your prefix: `{adk:memory}:` to force all keys to one hash slot |
| TLS handshake failure | Verify CA certificate trust chain; ElastiCache uses Amazon-managed CA |
| Slow first query after restart | Index is created on first use — pre-warm by calling `create_index()` at startup |
| Memory not expiring | Verify `ttl_seconds` is set in config; `None` disables TTL |

[← Previous: 02 — Vector Memory Search](02-vector-memory-search.md)
