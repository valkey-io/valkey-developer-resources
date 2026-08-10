# Production Deployment

> Deploy DocsGPT with Valkey vector store in production — Docker Compose orchestration, TLS, persistence, connection management, monitoring, and scaling considerations.

**Advanced** · Python · ~20 min

**Who is this for:** DevOps engineers and developers deploying DocsGPT with Valkey as the vector store in production environments.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md) and [Ingestion & Retrieval](./02-ingestion-and-retrieval.md)
- Docker Compose v2
- Familiarity with Docker networking and TLS certificates

## Step 1: Production Docker Compose

A complete `docker-compose.yml` for production DocsGPT with Valkey:

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - valkey_data:/data
    command: >
      valkey-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 2gb
      --maxmemory-policy noeviction
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  docsgpt-backend:
    build: ./application
    environment:
      - VECTOR_STORE=valkey
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6379
      - VALKEY_INDEX_NAME=docsgpt
      - VALKEY_PREFIX=doc:
      - VALKEY_DISTANCE_METRIC=cosine
      - VALKEY_VECTOR_ALGORITHM=hnsw
    depends_on:
      valkey:
        condition: service_healthy
    restart: unless-stopped

volumes:
  valkey_data:
```

Key configuration choices:

| Setting | Value | Reason |
| --- | --- | --- |
| `appendonly yes` | AOF persistence | Survive restarts without re-ingesting all documents |
| `appendfsync everysec` | Flush every second | Balance durability and performance |
| `maxmemory-policy noeviction` | Never evict data | Vector data must not be silently dropped |
| `127.0.0.1:6379:6379` | Bind to localhost only | Prevent external access |
| `condition: service_healthy` | Wait for healthcheck | DocsGPT won't start until Valkey is ready |

## Step 2: Persistence and Backup

### AOF Persistence

With `appendonly yes`, Valkey writes every mutation to an append-only file. On restart, it replays the AOF to reconstruct the dataset including all stored vectors and the search index.

### RDB Snapshots (additional)

For point-in-time backups, add RDB snapshotting alongside AOF:

```yaml
command: >
  valkey-server
  --appendonly yes
  --appendfsync everysec
  --save 900 1
  --save 300 10
  --save 60 10000
  --maxmemory 2gb
  --maxmemory-policy noeviction
```

### Backup Strategy

```bash
# Trigger an RDB snapshot
docker exec valkey-docsgpt valkey-cli BGSAVE

# Copy the dump file
docker cp valkey-docsgpt:/data/dump.rdb ./backups/dump-$(date +%Y%m%d).rdb
```

> **Note:** The HNSW index is stored in memory and rebuilt from HASH keys on restart. The rebuild is automatic but takes time proportional to the number of stored vectors.

## Step 3: Authentication and TLS

### Password Authentication

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
      --requirepass ${VALKEY_PASSWORD}
      --appendonly yes
    # ...

  docsgpt-backend:
    environment:
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6379
      - VALKEY_PASSWORD=${VALKEY_PASSWORD}
```

### TLS Encryption

For encrypted connections, mount certificates into the Valkey container:

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
      --tls-port 6380
      --port 0
      --tls-cert-file /tls/server.crt
      --tls-key-file /tls/server.key
      --tls-ca-cert-file /tls/ca.crt
      --appendonly yes
    volumes:
      - ./tls:/tls:ro
      - valkey_data:/data
    ports:
      - "127.0.0.1:6380:6380"

  docsgpt-backend:
    environment:
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6380
      - VALKEY_USE_TLS=true
```

### Authentication Methods

| Method | Use Case | Configuration |
| --- | --- | --- |
| Password (`requirepass`) | Simple deployments | `VALKEY_PASSWORD` env var |
| ACL users | Multi-tenant with least privilege | Configure via `valkey.conf` |
| TLS | Encrypt in transit (server-authenticated) | Mount certs, set `VALKEY_USE_TLS=true` |
| AWS IAM | ElastiCache/MemoryDB | Modify `ValkeyStore` to pass IAM credentials |

## Step 4: Connection Management

### Context Manager Pattern

Always use `ValkeyStore` as a context manager in production to ensure connections are released:

```python
"""Production connection management pattern."""
from __future__ import annotations

from application.vectorstore.valkey import ValkeyStore


def search_documents(source_id: str, query: str, k: int = 5):
    """Search with guaranteed connection cleanup."""
    with ValkeyStore(source_id=source_id, embeddings_key="embeddings") as store:
        return store.search(query, k=k)
```

### Connection Pooling Considerations

The current `ValkeyStore` implementation creates one TCP connection per instance via the GLIDE client. For high-throughput services:

- Reuse `ValkeyStore` instances across requests where possible
- The GLIDE client handles multiplexing internally
- Monitor connection count with `INFO CLIENTS`

```bash
docker exec valkey-docsgpt valkey-cli INFO CLIENTS
# connected_clients: N
```

## Step 5: Monitoring

### Key Metrics

Monitor these Valkey metrics for a healthy DocsGPT vector store:

```bash
# Memory usage (vectors are memory-intensive)
docker exec valkey-docsgpt valkey-cli INFO MEMORY | grep used_memory_human

# Search index stats
docker exec valkey-docsgpt valkey-cli FT.INFO docsgpt

# Connected clients
docker exec valkey-docsgpt valkey-cli INFO CLIENTS | grep connected_clients

# Persistence status
docker exec valkey-docsgpt valkey-cli INFO PERSISTENCE | grep aof_last_bgrewrite_status
```

### FT.INFO Output

`FT.INFO docsgpt` returns critical index health information:

| Field | What to Watch |
| --- | --- |
| `num_docs` | Total documents indexed |
| `num_records` | Total index entries |
| `indexing` | Should be `0` (not currently indexing) |
| `hash_indexing_failures` | Should be `0` (no failed indexing) |

### Memory Estimation

Per document memory usage depends on:

- Key overhead (~64 bytes)
- Content and metadata field sizes
- Vector dimensions (dimensions × 4 bytes for float32)
- HNSW graph overhead (varies with `M` parameter)

Monitor `INFO memory` output and `used_memory` to right-size your deployment.

## Step 6: Scaling Considerations

### When to Scale

| Signal | Action |
| --- | --- |
| `used_memory` > 80% of `maxmemory` | Increase `maxmemory` or add RAM |
| Search latency > 10ms (p99) | Tune HNSW `ef_runtime` or switch to `FLAT` for small datasets |
| `connected_clients` > 100 | Review connection lifecycle (use context managers) |
| Ingestion throughput too low | Batch with `add_texts` instead of individual `add_chunk` |

### HNSW Tuning for Production

```python
"""Production HNSW parameters for different dataset sizes."""
# Small (< 10K documents) — defaults are fine
# No changes needed

# Medium (10K–100K documents)
# Increase ef_runtime for better recall
os.environ["VALKEY_VECTOR_ALGORITHM"] = "hnsw"
# Tune via Valkey server config or rebuild index

# Large (> 100K documents)
# Consider: higher M value, increased ef_construction
# Trade-off: more memory, slower inserts, but better search quality
```

### Index Rebuild

If you change HNSW parameters, you must rebuild the index:

1. Export all documents (use `get_chunks()` with a large scan)
2. Drop the index: `FT.DROPINDEX docsgpt`
3. Recreate with new parameters
4. Re-ingest all documents

> **Warning:** Index rebuild requires re-embedding all documents if you don't store the raw embedding bytes externally. Plan for the compute cost.

## Step 7: Health Check Script

A production health check that verifies the full stack:

```python
"""Production health check for DocsGPT + Valkey."""
from __future__ import annotations

import struct
import sys

from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress


def health_check(host: str = "localhost", port: int = 6379) -> bool:
    """Verify Valkey connectivity, search module, and index health."""
    try:
        config = GlideClientConfiguration(
            addresses=[NodeAddress(host=host, port=port)]
        )
        client = GlideClient.create(config)

        # 1. Connectivity
        assert client.ping() == b"PONG"

        # 2. Search module loaded
        info = client.custom_command(["FT.INFO", "docsgpt"])
        # FT.INFO returns a flat list of key-value pairs
        assert info is not None

        # 3. Index is not currently backfilling
        # (info contains "indexing" followed by 0 or 1)

        client.close()
        return True
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    ok = health_check()
    sys.exit(0 if ok else 1)
```

## Summary

| Concern | Solution |
| --- | --- |
| Data durability | AOF persistence (`appendonly yes`) |
| Security | Password auth + TLS, bind to 127.0.0.1 |
| Connection lifecycle | Context manager pattern |
| Memory planning | Monitor `INFO memory` and `used_memory` |
| Monitoring | `FT.INFO`, `INFO MEMORY`, `INFO CLIENTS` |
| Backup | `BGSAVE` + copy RDB file |
| Scaling | Tune HNSW params, increase memory |

---

[← Back to cookbook index](./README.md)
