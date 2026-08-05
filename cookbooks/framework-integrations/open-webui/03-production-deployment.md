# Production Deployment of Open WebUI with Valkey

> Deploy Open WebUI with Valkey in production — configure TLS, authentication,
> persistence, monitoring, and high availability.

**Intermediate** · Docker · ~20 min

**Who is this for:** DevOps engineers and platform teams deploying Open WebUI with
Valkey as the vector backend in production environments where security, reliability,
and observability matter.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - RAG Configuration](02-rag-configuration.md)
- Familiarity with Docker Compose and production deployment patterns

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Step 1: Production Docker Compose

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    container_name: valkey-prod
    command: valkey-server /etc/valkey/valkey.conf --requirepass ${VALKEY_PASSWORD}
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/etc/valkey/valkey.conf:ro
    healthcheck:
      test: ["CMD", "valkey-cli", "-a", "${VALKEY_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4g

  open-webui:
    image: ghcr.io/open-webui/open-webui:0.11.0
    container_name: open-webui-prod
    ports:
      - "127.0.0.1:3000:8080"
    environment:
      - VECTOR_DB=valkey
      - VALKEY_URL=valkey://:${VALKEY_PASSWORD}@valkey:6379
      - VALKEY_COLLECTION_PREFIX=prod
      - VALKEY_INDEX_TYPE=HNSW
      - VALKEY_DISTANCE_METRIC=COSINE
      - VALKEY_HNSW_M=16
      - VALKEY_HNSW_EF_CONSTRUCTION=200
      - VALKEY_HNSW_EF_RUNTIME=10
    volumes:
      - open-webui-data:/app/backend/data
    depends_on:
      valkey:
        condition: service_healthy
    restart: unless-stopped

volumes:
  valkey-data:
  open-webui-data:
```

## Step 2: Valkey Configuration File

Create `valkey.conf` for production settings:

```text
# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Memory
maxmemory 3gb
maxmemory-policy noeviction

# Network
bind 0.0.0.0
protected-mode yes
tcp-keepalive 300
timeout 0

# Performance
hz 10
io-threads 4
io-threads-do-reads yes

# Logging
loglevel notice
logfile ""
```

**Important:** Use `maxmemory-policy noeviction` for vector data. Unlike cache
workloads, you never want Valkey to evict document embeddings silently.

## Step 3: Authentication

The `VALKEY_URL` supports password authentication via URL format:

```text
valkey://:your-password@valkey:6379
```

Create a `.env` file (not committed to version control):

```bash
VALKEY_PASSWORD=your-secure-password-here
```

## Step 4: TLS Configuration

For encrypted connections, generate certificates and configure Valkey:

Add to `valkey.conf`:

```text
# TLS
tls-port 6380
port 0
tls-cert-file /etc/valkey/tls/server.crt
tls-key-file /etc/valkey/tls/server.key
tls-ca-cert-file /etc/valkey/tls/ca.crt
tls-auth-clients optional
```

Update the docker-compose to mount TLS certs and use `valkeys://`:

```yaml
  valkey:
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/etc/valkey/valkey.conf:ro
      - ./tls:/etc/valkey/tls:ro
    ports:
      - "127.0.0.1:6380:6380"

  open-webui:
    environment:
      - VALKEY_URL=valkeys://:${VALKEY_PASSWORD}@valkey:6380
```

Note: `valkeys://` (with `s`) enables TLS in the GLIDE client.

## Step 5: Monitoring

### Key metrics to track

```bash
# Memory usage (total and per-index)
docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" INFO memory | grep used_memory_human

# Index statistics
docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" FT._LIST | while read idx; do
  echo "=== $idx ==="
  docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" FT.INFO "$idx" | \
    grep -E "num_docs|num_records|bytes"
done

# Client connections
docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" INFO clients | grep connected_clients

# Slow queries
docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" SLOWLOG GET 10
```

### Health check endpoint

Add a simple monitoring script:

```bash
#!/bin/bash
# health_check.sh
PASS="${VALKEY_PASSWORD}"
HOST="localhost"
PORT="6379"

# Ping
if ! docker exec valkey-prod valkey-cli -a "$PASS" ping | grep -q PONG; then
  echo "CRITICAL: Valkey not responding"
  exit 2
fi

# Check search module
if ! docker exec valkey-prod valkey-cli -a "$PASS" MODULE LIST | grep -q search; then
  echo "CRITICAL: valkey-search module not loaded"
  exit 2
fi

# Memory usage (warn at 80%)
MEM_USED=$(docker exec valkey-prod valkey-cli -a "$PASS" INFO memory | grep used_memory: | cut -d: -f2 | tr -d '\r')
MEM_MAX=$(docker exec valkey-prod valkey-cli -a "$PASS" CONFIG GET maxmemory | tail -1 | tr -d '\r')
if [ "$MEM_MAX" -gt 0 ]; then
  PCT=$((MEM_USED * 100 / MEM_MAX))
  if [ "$PCT" -gt 80 ]; then
    echo "WARNING: Memory usage at ${PCT}%"
    exit 1
  fi
fi

echo "OK: Valkey healthy"
exit 0
```

## Step 6: Backup and Restore

### Automated backups

```bash
# Trigger RDB snapshot
docker exec valkey-prod valkey-cli -a "$VALKEY_PASSWORD" BGSAVE

# Copy the dump file
docker cp valkey-prod:/data/dump.rdb ./backups/dump-$(date +%Y%m%d).rdb
```

### Restore from backup

```bash
# Stop Valkey
docker compose stop valkey

# Replace the dump file
docker cp ./backups/dump-20250728.rdb valkey-prod:/data/dump.rdb

# Restart
docker compose start valkey
```

The vector index is automatically rebuilt from the persisted HASH data on startup.

## Step 7: Scaling Considerations

### Memory estimation

Each vector document uses approximately:

- Vector: `dimensions × 4 bytes` (e.g., 1536 dims = 6 KB)
- HNSW graph: `M × 2 × 4 bytes` per vector (e.g., M=16 → 128 bytes)
- Metadata + text: varies (typically 1–5 KB per chunk)
- **Total per chunk:** ~8–12 KB for 1536-dim embeddings

For 100K document chunks with 1536-dim embeddings: ~1.2 GB memory.

### Read replicas

For read-heavy deployments, add replicas:

```yaml
  valkey-replica:
    image: valkey/valkey-bundle:9.1.0
    command: >
      valkey-server
      --replicaof valkey 6379
      --masterauth ${VALKEY_PASSWORD}
      --requirepass ${VALKEY_PASSWORD}
    depends_on:
      valkey:
        condition: service_healthy
```

Note: Open WebUI currently uses a single `VALKEY_URL`. Route reads to replicas
via a load balancer or proxy if needed.

### Vertical scaling

- Increase `maxmemory` as your document set grows
- HNSW indexing is CPU-bound — more cores help with parallel ingestion
- `io-threads` helps with network I/O for concurrent searches

## Step 8: Migration from Other Vector Backends

### From Chroma to Valkey

1. Set `VECTOR_DB=valkey` and configure `VALKEY_URL`
2. Restart Open WebUI
3. Re-upload all documents (there's no direct migration tool between backends)
4. Open WebUI will create new indices and re-embed documents

### Preserving data between upgrades

Vector data persists in the `valkey-data` Docker volume. As long as:

- The volume is not deleted (`docker compose down` without `-v`)
- The embedding model doesn't change (dimension must match)
- `VALKEY_COLLECTION_PREFIX` stays the same

Data survives container restarts and Open WebUI upgrades.

## Production Checklist

- [ ] `VALKEY_PASSWORD` set and not in version control
- [ ] `maxmemory-policy noeviction` (never silently drop vectors)
- [ ] Persistence enabled (`appendonly yes`)
- [ ] TLS enabled for network-accessible deployments
- [ ] Memory monitoring with alerts at 80% usage
- [ ] Automated RDB backups on schedule
- [ ] Resource limits set on Docker containers
- [ ] Health checks configured for orchestrator restart
- [ ] `VALKEY_HNSW_EF_RUNTIME` ≥ your typical `topK` value

## Troubleshooting

### Out of memory errors

- Check `maxmemory` setting vs actual usage
- With `noeviction`, Valkey returns OOM errors on writes — you need to either
  increase memory or delete unused collections

### Slow searches after many documents

- Check `VALKEY_HNSW_EF_RUNTIME` — increase if topK is > 10
- Monitor with `SLOWLOG` for queries exceeding 10ms
- Consider switching large low-priority collections to FLAT

### Replication lag

- Monitor: `docker exec valkey-prod valkey-cli -a "$PASS" INFO replication`
- High lag during bulk ingestion is normal — it catches up after

---

[← Back to RAG Configuration](02-rag-configuration.md) · [← Back to README](README.md)
