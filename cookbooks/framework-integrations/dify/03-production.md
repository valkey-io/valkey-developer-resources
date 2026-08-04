# Production Deployment

> Harden, scale, and monitor a Dify + Valkey vector store deployment — covering authentication, TLS, persistence, memory management, and operational visibility.

**Advanced** · Python · ~25 min

**Who is this for:** DevOps engineers and platform teams deploying Dify with Valkey in production environments where security, durability, and observability matter.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md) and [Vector Search](./02-vector-search.md)
- Familiarity with Docker Compose or Kubernetes deployments
- Understanding of TLS certificates and network security

## Authentication

### Password Authentication

Set a strong password for Valkey and configure Dify to use it:

```yaml
# docker-compose.yml
services:
  valkey-vector:
    image: valkey/valkey-bundle:9.1.0
    command: valkey-server --requirepass "${VALKEY_PASSWORD}"
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - valkey-data:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "-a", "${VALKEY_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Configure Dify:

```bash
VALKEY_PASSWORD=your-strong-password-here
```

### ACL-Based Authentication

For fine-grained access control, use Valkey ACLs to create a dedicated user for Dify with only the permissions it needs:

```bash
# Create a user with exactly the commands Dify requires
ACL SETUSER dify_user on >secure_password \
  ~doc:* ~idx:* \
  +ping +info +module \
  +hset +hget +hgetall +hdel +hexists +del +exists +keys \
  +ft.create +ft.dropindex +ft.search +ft.info +ft._list
```

This grants:

| Permission | Purpose |
| --- | --- |
| `~doc:* ~idx:*` | Key patterns for documents and indexes |
| `+hset +hget +hgetall +hdel` | Document CRUD |
| `+ft.create +ft.search +ft.info` | Index management and search |
| `+del +exists +keys` | Bulk operations |

## TLS Encryption

### Generate Certificates

For production, use certificates from your PKI or a certificate authority. For testing:

```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365 -out ca.crt \
  -subj "/CN=Valkey CA"

# Generate server cert
openssl genrsa -out valkey.key 2048
openssl req -new -key valkey.key -out valkey.csr -subj "/CN=valkey-vector"
openssl x509 -req -in valkey.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out valkey.crt -days 365 -sha256
```

### Configure Valkey with TLS

```yaml
# docker-compose.yml
services:
  valkey-vector:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
        --tls-port 6379
        --port 0
        --tls-cert-file /tls/valkey.crt
        --tls-key-file /tls/valkey.key
        --tls-ca-cert-file /tls/ca.crt
        --requirepass "${VALKEY_PASSWORD}"
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - ./tls:/tls:ro
      - valkey-data:/data
```

### Configure Dify for TLS

```bash
VALKEY_USE_SSL=true
VALKEY_HOST=valkey-vector
VALKEY_PORT=6379
VALKEY_PASSWORD=your-strong-password
```

Dify's `valkey-glide` client respects `VALKEY_USE_SSL=true` and establishes a TLS connection. If using a self-signed CA, you may need to add the CA certificate to the container's trust store.

## Persistence

Valkey is an in-memory store, but vector data must survive restarts. Configure persistence to protect against data loss.

### RDB Snapshots (Default)

RDB creates point-in-time snapshots. Suitable for most Dify deployments:

```bash
# valkey.conf (or command-line args)
save 900 1      # Snapshot if ≥1 key changed in 900 seconds
save 300 10     # Snapshot if ≥10 keys changed in 300 seconds
save 60 10000   # Snapshot if ≥10000 keys changed in 60 seconds
```

### AOF (Append-Only File)

AOF logs every write operation for minimal data loss:

```bash
appendonly yes
appendfsync everysec  # Fsync once per second (good balance)
```

### Recommended: RDB + AOF

For production Dify deployments, enable both:

```yaml
services:
  valkey-vector:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
        --requirepass "${VALKEY_PASSWORD}"
        --save "900 1"
        --save "300 10"
        --appendonly yes
        --appendfsync everysec
    volumes:
      - valkey-data:/data
```

### Memory Policy

Vector stores should **never evict data** — a missing vector means incorrect search results:

```bash
maxmemory-policy noeviction
```

This causes Valkey to return errors when memory is full rather than silently dropping vectors. Monitor memory usage and scale before hitting limits.

## Memory Sizing

### Estimating Memory Requirements

Each document chunk stored by Dify consumes:

| Component | Size | Notes |
| --- | --- | --- |
| Vector (1536-dim, FLOAT32) | 6,144 bytes | `dim × 4 bytes` |
| Vector (768-dim, FLOAT32) | 3,072 bytes | Smaller models |
| HNSW overhead | ~8 bytes × M × 2 | Graph edges per vector |
| Hash fields | ~200–500 bytes | `page_content` + metadata + IDs |
| Key overhead | ~64 bytes | Valkey key metadata |

**Rule of thumb:** For 1536-dim embeddings, budget ~8 KB per document chunk.

| Document chunks | Estimated memory |
| --- | --- |
| 10,000 | ~80 MB |
| 100,000 | ~800 MB |
| 1,000,000 | ~8 GB |

### Monitoring Memory

```bash
# Current memory usage
docker exec valkey-vector valkey-cli INFO memory | grep used_memory_human

# Peak memory
docker exec valkey-vector valkey-cli INFO memory | grep used_memory_peak_human

# Per-index stats
docker exec valkey-vector valkey-cli FT.INFO "idx:your_collection" | grep -A2 "num_docs"
```

## Monitoring

### Key Metrics

Monitor these metrics for a healthy Dify + Valkey deployment:

| Metric | Source | Alert threshold |
| --- | --- | --- |
| `used_memory_rss` | `INFO memory` | > 80% of available RAM |
| `connected_clients` | `INFO clients` | Sudden spikes |
| `instantaneous_ops_per_sec` | `INFO stats` | Baseline deviation |
| `rejected_connections` | `INFO stats` | > 0 |
| `rdb_last_bgsave_status` | `INFO persistence` | Not "ok" |
| `aof_last_write_status` | `INFO persistence` | Not "ok" |

### Health Check Script

```python
"""Production health check for Dify's Valkey vector store."""
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def health_check(host: str, port: int, password: str | None = None) -> dict:
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        client_name="dify_health_check",
        request_timeout=5000,
    )
    # Note: pass credentials via GlideClientConfiguration if auth is needed

    client = await GlideClient.create(config)
    try:
        status = {"healthy": True, "checks": {}}

        # Connectivity
        pong = await client.ping()
        status["checks"]["ping"] = pong == b"PONG" or pong == "PONG"

        # Memory
        info = await client.info()
        info_str = info.decode() if isinstance(info, bytes) else str(info)
        for line in info_str.split("\n"):
            if "used_memory_human" in line and "peak" not in line:
                status["checks"]["memory"] = line.strip().split(":")[1]

        # Search module
        modules = await client.custom_command(["MODULE", "LIST"])
        module_names = []
        for m in modules:
            if isinstance(m, dict):
                name = m.get(b"name") or m.get("name")
                if name:
                    module_names.append(name.decode() if isinstance(name, bytes) else str(name))
        status["checks"]["search_module"] = "search" in module_names

        # Index count
        indexes = await client.custom_command(["FT._LIST"])
        status["checks"]["index_count"] = len(indexes) if indexes else 0

        if not status["checks"]["search_module"]:
            status["healthy"] = False

        return status
    finally:
        await client.close()
```

### CLIENT SETNAME for Observability

Dify's `valkey-glide` client sets a client name on connection. Use `CLIENT LIST` to identify Dify connections:

```bash
docker exec valkey-vector valkey-cli CLIENT LIST | grep dify
```

This helps distinguish Dify's vector store connections from other services sharing the same Valkey instance.

## Backup and Restore

### Manual Backup

```bash
# Trigger an RDB snapshot
docker exec valkey-vector valkey-cli BGSAVE

# Copy the dump file
docker cp valkey-vector:/data/dump.rdb ./backup-$(date +%Y%m%d).rdb
```

### Restore from Backup

```bash
# Stop Valkey
docker compose stop valkey-vector

# Replace the dump file
docker cp ./backup-20260801.rdb valkey-vector:/data/dump.rdb

# Restart
docker compose start valkey-vector
```

### Automated Backups

```yaml
# Add to docker-compose.yml
services:
  valkey-backup:
    image: alpine:3.20
    volumes:
      - valkey-data:/data:ro
      - ./backups:/backups
    entrypoint: /bin/sh
    command: >
      -c 'while true; do
        cp /data/dump.rdb /backups/dump-$$(date +%Y%m%d-%H%M).rdb;
        find /backups -name "dump-*.rdb" -mtime +7 -delete;
        sleep 3600;
      done'
```

## Scaling

### Vertical Scaling

For most Dify deployments (< 1M chunks), a single Valkey instance is sufficient. Scale vertically by:

1. Increasing available memory (budget ~8 KB per 1536-dim chunk)
2. Using faster storage for AOF writes (NVMe SSD)
3. Increasing `maxmemory` configuration

### Connection Pooling

Dify's `valkey-glide` client handles connection pooling internally. For high-concurrency deployments with many Dify workers:

```bash
# Monitor active connections
docker exec valkey-vector valkey-cli INFO clients
# connected_clients: should be stable, not growing unbounded
```

### Read Replicas

For read-heavy workloads (many concurrent knowledge base queries), add read replicas:

```yaml
services:
  valkey-vector:
    image: valkey/valkey-bundle:9.1.0
    command: valkey-server --requirepass "${VALKEY_PASSWORD}"
    volumes:
      - valkey-data:/data

  valkey-replica:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
        --replicaof valkey-vector 6379
        --masterauth "${VALKEY_PASSWORD}"
        --requirepass "${VALKEY_PASSWORD}"
    depends_on:
      - valkey-vector
```

> **Note:** Dify does not natively support read/write splitting for Valkey. Replicas are useful for external monitoring queries or as hot standbys for failover.

## Production Checklist

- [ ] Authentication enabled (`VALKEY_PASSWORD` set)
- [ ] TLS enabled (`VALKEY_USE_SSL=true`) if traffic crosses network boundaries
- [ ] Persistence configured (RDB + AOF)
- [ ] `maxmemory-policy noeviction` set
- [ ] Memory headroom: current usage < 70% of `maxmemory`
- [ ] Health checks configured in orchestrator (Docker, K8s)
- [ ] Backup strategy in place (scheduled RDB copies)
- [ ] Monitoring dashboards for memory, connections, and ops/sec
- [ ] Network restricted: Valkey bound to `127.0.0.1` or private network
- [ ] Client name set for connection identification

## Teardown

To remove all resources created by this cookbook:

```bash
cd sample/
docker compose down -v
```

This removes the container and its data volume.

---

**← Previous:** [Vector Search & Filtering](./02-vector-search.md) · **Back to** [README](./README.md)
