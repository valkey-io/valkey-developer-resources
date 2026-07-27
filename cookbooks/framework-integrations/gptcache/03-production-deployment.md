# Production Deployment of GPTCache with Valkey

> Deploy a semantic caching layer at scale with Docker Compose, TLS encryption, persistence, monitoring, and strategies for scaling and migrating from Redis.

**Intermediate** · Python/Docker · ~20 min

**Who is this for:** Developers and DevOps engineers ready to move their GPTCache + Valkey
semantic caching setup from local development into a production environment with proper
security, persistence, and observability.

## Prerequisites

- Completed [Semantic Caching Pipeline](02-semantic-caching.md)
- Docker and Docker Compose installed
- Basic familiarity with TLS certificates

> **Security:** Production deployments must configure authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/) for a complete guide to securing your deployment.

## Docker Compose Setup

Create a `docker-compose.yml` that runs Valkey with the search module alongside your application:

```yaml
version: "3.8"

services:
  valkey:
    image: valkey/valkey-bundle:8.1.1
    container_name: valkey-gptcache
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/etc/valkey/valkey.conf
    command: valkey-server /etc/valkey/valkey.conf --requirepass ${VALKEY_PASSWORD}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  app:
    build: .
    container_name: gptcache-app
    depends_on:
      valkey:
        condition: service_healthy
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6379
      - VALKEY_PASSWORD=${VALKEY_PASSWORD}
    restart: unless-stopped

volumes:
  valkey-data:
```

Create the corresponding `Dockerfile` for the application:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

And `requirements.txt`:

```text
gptcache[redis]==0.1.43
openai==1.82.0
redis==5.2.1
```

## Valkey Configuration

Create a `valkey.conf` for production:

```text
# Persistence — AOF for durability
appendonly yes
appendfsync everysec

# RDB snapshots as backup
save 900 1
save 300 10
save 60 10000

# Memory management for cache workloads
maxmemory 2gb
maxmemory-policy allkeys-lru

# Authentication — injected at runtime via docker-compose command
# (Valkey config does not support env var substitution)
# requirepass is set via: --requirepass ${VALKEY_PASSWORD}

# Network
bind 0.0.0.0
protected-mode yes
tcp-keepalive 300

# Logging
loglevel notice
logfile /data/valkey.log
```

### Memory policy considerations

| Policy | Use case |
| --- | --- |
| `allkeys-lru` | Best for pure cache workloads — evicts least recently used keys when full |
| `volatile-lru` | Only evicts keys with TTL set — use if mixing cache with persistent data |
| `allkeys-random` | Simpler eviction, slightly less optimal hit rate |
| `noeviction` | Returns errors when full — use only if you manage eviction externally |

For GPTCache, `allkeys-lru` is recommended since all stored data is cache entries that can be regenerated.

## TLS Connection

### Generate certificates (development)

```bash
# Create a CA and server certificate for development
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/ca-key.pem -out certs/ca-cert.pem \
  -days 365 -nodes -subj "/CN=Valkey CA"
openssl req -newkey rsa:4096 -keyout certs/server-key.pem -out certs/server-req.pem \
  -nodes -subj "/CN=valkey"
openssl x509 -req -in certs/server-req.pem -CA certs/ca-cert.pem \
  -CAkey certs/ca-key.pem -CAcreateserial -out certs/server-cert.pem -days 365
```

### Configure Valkey for TLS

Add to `valkey.conf`:

```text
# TLS configuration
tls-port 6380
port 0
tls-cert-file /tls/server-cert.pem
tls-key-file /tls/server-key.pem
tls-ca-cert-file /tls/ca-cert.pem
tls-auth-clients optional
```

Update `docker-compose.yml` to mount certificates:

```yaml
services:
  valkey:
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/etc/valkey/valkey.conf
      - ./certs:/tls:ro
    ports:
      - "6380:6380"
```

### Connect with TLS from Python

```python
import valkey

# TLS connection to Valkey
r = valkey.Valkey(
    host="localhost",
    port=6380,
    password="your-secure-password",
    ssl=True,
    ssl_ca_certs="certs/ca-cert.pem",
    ssl_certfile="certs/client-cert.pem",
    ssl_keyfile="certs/client-key.pem",
)

# Use with GPTCache
from gptcache.manager import VectorBase

vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6380,
    dimension=1536,
    namespace="production_cache",
    password="your-secure-password",
    ssl=True,
    ssl_ca_certs="certs/ca-cert.pem",
)
```

## Monitoring

### Cache hit rate metrics

Instrument your application to track cache performance:

```python
import time
import logging
from gptcache import Cache
from gptcache.adapter import openai

logger = logging.getLogger("gptcache.metrics")


class MonitoredCache:
    """Wrapper that logs cache hit/miss metrics."""

    def __init__(self, cache_instance: Cache):
        self.cache = cache_instance
        self.hits = 0
        self.misses = 0

    def query(self, **kwargs):
        start = time.time()
        response = openai.ChatCompletion.create(**kwargs)
        elapsed = time.time() - start

        # Heuristic: cache hits are much faster than API calls
        if elapsed < 0.5:
            self.hits += 1
            logger.info(f"Cache HIT - {elapsed:.3f}s")
        else:
            self.misses += 1
            logger.info(f"Cache MISS - {elapsed:.3f}s")

        return response

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

### Valkey memory and index monitoring

Create a monitoring script:

```python
import valkey
import json


def get_cache_stats(host: str = "localhost", port: int = 6379, password: str = None):
    """Collect cache and index statistics from Valkey."""
    r = valkey.Valkey(host=host, port=port, password=password)

    # Memory info
    memory = r.info("memory")
    stats = {
        "used_memory_human": memory["used_memory_human"],
        "used_memory_peak_human": memory["used_memory_peak_human"],
        "maxmemory_human": memory.get("maxmemory_human", "unlimited"),
    }

    # Index statistics
    try:
        index_info = r.execute_command("FT.INFO", "gptcache_demo")
        # Parse the alternating key-value list
        info_dict = dict(zip(index_info[::2], index_info[1::2]))
        stats["index_num_docs"] = info_dict.get(b"num_docs", 0)
        stats["index_num_records"] = info_dict.get(b"num_records", 0)
        stats["index_memory"] = info_dict.get(b"inverted_sz_mb", 0)
    except Exception as e:
        stats["index_error"] = str(e)

    return stats


if __name__ == "__main__":
    stats = get_cache_stats()
    print(json.dumps(stats, indent=2, default=str))
```

### Health check endpoint

```python
from fastapi import FastAPI
import valkey

app = FastAPI()


@app.get("/health")
def health_check():
    """Check Valkey connectivity and index status."""
    try:
        r = valkey.Valkey(host="valkey", port=6379)
        r.ping()
        indexes = r.execute_command("FT._LIST")
        return {
            "status": "healthy",
            "valkey": "connected",
            "indexes": len(indexes),
        }
    except valkey.ConnectionError:
        return {"status": "unhealthy", "valkey": "disconnected"}, 503
```

## Scaling

### Read replicas

For read-heavy cache workloads, add Valkey replicas:

```yaml
services:
  valkey-primary:
    image: valkey/valkey-bundle:8.1.1
    command: valkey-server /etc/valkey/valkey.conf
    volumes:
      - ./valkey.conf:/etc/valkey/valkey.conf

  valkey-replica:
    image: valkey/valkey-bundle:8.1.1
    command: valkey-server --replicaof valkey-primary 6379
    depends_on:
      - valkey-primary
    deploy:
      replicas: 2
```

Configure your application to read from replicas:

```python
import valkey

# Write to primary
primary = valkey.Valkey(host="valkey-primary", port=6379)

# Read from replicas (for KNN search)
replica = valkey.Valkey(host="valkey-replica", port=6379)
```

### Sharding considerations

For very large cache sizes (millions of entries):

- **Namespace-based sharding** — Route different namespaces to different Valkey instances
- **Consistent hashing** — Use a hash ring to distribute keys across multiple nodes
- **Valkey Cluster** — Native clustering with automatic slot distribution (requires valkey-search cluster support)

```python
def get_shard(namespace: str, num_shards: int = 4) -> int:
    """Determine which shard a namespace belongs to."""
    return hash(namespace) % num_shards


SHARDS = {
    0: {"host": "valkey-shard-0", "port": 6379},
    1: {"host": "valkey-shard-1", "port": 6379},
    2: {"host": "valkey-shard-2", "port": 6379},
    3: {"host": "valkey-shard-3", "port": 6379},
}


def get_vector_store(namespace: str):
    """Get the vector store for a given namespace, routed to the correct shard."""
    from gptcache.manager import VectorBase

    shard_id = get_shard(namespace)
    shard_config = SHARDS[shard_id]

    return VectorBase(
        "redis",
        host=shard_config["host"],
        port=shard_config["port"],
        dimension=1536,
        namespace=namespace,
    )
```

## Migration from Redis to Valkey

Migrating from Redis with RediSearch to Valkey with valkey-search is straightforward:

### What stays the same

- **Client library** — `redis-py` works with both Redis and Valkey
- **Application code** — No changes needed (GPTCache uses the same `VectorBase("redis", ...)` configuration)
- **Data format** — HASH structures and vector indexes are compatible
- **Commands** — `FT.CREATE`, `FT.SEARCH`, `FT.INFO` work identically

### What changes

- **Host/port** — Point to your Valkey instance instead of Redis
- **SORTBY behavior** — Handled automatically by GPTCache's detection logic
- **Docker image** — Use `valkey/valkey-bundle` instead of `redis/redis-stack`

### Migration steps

1. Deploy Valkey alongside Redis (parallel run)
1. Update connection configuration to point to Valkey:

    ```python
    # Before (Redis)
    vector_store = VectorBase(
        "redis",
        host="redis-host",
        port=6379,
        dimension=1536,
        namespace="production_cache",
    )

    # After (Valkey) — only the host changes
    vector_store = VectorBase(
        "redis",  # Backend name stays "redis"
        host="valkey-host",
        port=6379,
        dimension=1536,
        namespace="production_cache",
    )
    ```

1. The cache will rebuild naturally as queries come in (cache entries are regenerable)
1. Monitor hit rates during migration — expect a temporary dip as the cache warms up
1. Decommission Redis once Valkey cache is warm

### Data migration (optional)

If you want to preserve existing cache entries rather than warming up from scratch:

```bash
# Export from Redis and import to Valkey using RIOT or redis-cli
docker exec redis-old valkey-cli --rdb /data/dump.rdb
docker cp redis-old:/data/dump.rdb ./dump.rdb
docker cp ./dump.rdb valkey-new:/data/dump.rdb
docker restart valkey-new
```

> **Note:** After data migration, the search index may need to be recreated. GPTCache handles this automatically on startup if the index doesn't exist.

## Troubleshooting

### Container fails to start with "OOM" errors

- Increase Docker memory limits
- Reduce `maxmemory` in `valkey.conf`
- Check for memory leaks: `docker exec valkey-gptcache valkey-cli INFO memory`

### TLS handshake failures

- Verify certificate paths are mounted correctly in the container
- Check certificate expiry: `openssl x509 -in certs/server-cert.pem -noout -dates`
- Ensure the CA certificate matches on both client and server

### Slow cache performance in production

- Check network latency between app and Valkey: `docker exec gptcache-app ping valkey`
- Monitor Valkey slow log: `docker exec valkey-gptcache valkey-cli SLOWLOG GET 10`
- Consider connection pooling:

```python
import valkey

pool = valkey.ConnectionPool(
    host="valkey",
    port=6379,
    password="your-password",
    max_connections=20,
)
r = valkey.Valkey(connection_pool=pool)
```

### Index not created after migration

If GPTCache doesn't automatically recreate the index:

```bash
# Check existing indexes
docker exec valkey-gptcache valkey-cli FT._LIST

# Manually trigger index creation by restarting the application
docker compose restart app
```

### Replica lag causing stale cache reads

- Monitor replication: `docker exec valkey-gptcache valkey-cli INFO replication`
- Add a small delay for read-after-write consistency, or read from primary for critical paths

---

[← Previous: Semantic Caching Pipeline](02-semantic-caching.md) · [Back to README →](README.md)
