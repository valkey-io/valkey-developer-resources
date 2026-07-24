# Production Operations for Firecrawl with Valkey

> Monitor, scale, and maintain your Firecrawl + Valkey deployment for reliable production operation.

**Intermediate** · Docker/CLI · ~15 min

**Who is this for:** DevOps engineers and platform teams running Firecrawl in production who need to monitor health, scale workers, and handle migrations.

## Prerequisites

- Completed [Self-Hosting with Valkey](02-self-hosting.md)
- A running Firecrawl + Valkey deployment
- Familiarity with Docker and basic operations tooling

> **Security Note:** Production Valkey instances should use authentication, TLS, and network
> isolation. See the [Valkey security documentation](https://valkey.io/topics/security/)
> for best practices.

## Monitoring Valkey

### Key Metrics via INFO

```bash
# Full server info
docker exec firecrawl-valkey valkey-cli INFO

# Memory usage
docker exec firecrawl-valkey valkey-cli INFO memory
```

Critical fields to monitor:

| Metric | Command | Alert Threshold |
| --- | --- | --- |
| Memory usage | `INFO memory` → `used_memory_human` | >80% of `maxmemory` |
| Connected clients | `INFO clients` → `connected_clients` | Unexpected drops |
| Blocked clients | `INFO clients` → `blocked_clients` | >0 sustained |
| Keys in database | `INFO keyspace` → `db0:keys=N` | Unbounded growth |
| Evicted keys | `INFO stats` → `evicted_keys` | >0 (with noeviction, this shouldn't happen) |
| Ops/sec | `INFO stats` → `instantaneous_ops_per_sec` | Baseline deviation |

### Real-Time Monitoring

```bash
# Watch commands in real-time (careful in production — adds overhead)
docker exec firecrawl-valkey valkey-cli MONITOR | head -50

# Latency check
docker exec firecrawl-valkey valkey-cli --latency

# Slow log (commands taking >10ms)
docker exec firecrawl-valkey valkey-cli SLOWLOG GET 10
```

### Queue-Specific Monitoring

```bash
# BullMQ queue depths
echo "Scrape waiting: $(docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:wait)"
echo "Scrape active:  $(docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:active)"
echo "Scrape failed:  $(docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:failed)"
echo "Crawl waiting:  $(docker exec firecrawl-valkey valkey-cli LLEN bull:crawl:wait)"
echo "Crawl active:   $(docker exec firecrawl-valkey valkey-cli LLEN bull:crawl:active)"
```

## Scaling Workers

### Horizontal Scaling with NUM_WORKERS_PER_QUEUE

Each worker container processes `NUM_WORKERS_PER_QUEUE` concurrent jobs per queue. Scale by:

1. **Increasing concurrency per container** — raise `NUM_WORKERS_PER_QUEUE`:

    ```yaml
    environment:
      - NUM_WORKERS_PER_QUEUE=8
    ```

1. **Adding more worker containers** — increase replicas:

    ```yaml
    firecrawl-worker:
      deploy:
        replicas: 4
    ```

1. **Both** — for maximum throughput:

    ```bash
    # Scale workers dynamically
    docker compose up -d --scale firecrawl-worker=4
    ```

### Scaling Guidelines

| Crawl Volume | Workers | NUM_WORKERS_PER_QUEUE | Valkey Memory |
| --- | --- | --- | --- |
| <1K pages/hour | 1 | 2 | 512MB |
| 1K–10K pages/hour | 2–4 | 4 | 1GB |
| 10K–100K pages/hour | 4–8 | 8 | 2–4GB |
| >100K pages/hour | 8+ | 8–16 | 4GB+ |

Monitor Valkey memory and queue depths when scaling. If `bull:scrape:wait` grows faster
than workers can process, add more worker containers.

## Persistence and Backup

### RDB + AOF for BullMQ Durability

BullMQ job data must survive restarts. Configure both persistence mechanisms:

```text
# valkey.conf - persistence settings
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

- **RDB** — Point-in-time snapshots. Fast restores but potential data loss between snapshots.
- **AOF** — Append-only log of every write. Near-zero data loss with `everysec` fsync.
- **Combined** — Valkey uses AOF for recovery (more complete) and RDB for backups.

### Backup Strategy

```bash
# Trigger a manual RDB snapshot
docker exec firecrawl-valkey valkey-cli BGSAVE

# Check last save status
docker exec firecrawl-valkey valkey-cli LASTSAVE

# Copy the dump file
docker cp firecrawl-valkey:/data/dump.rdb ./backup/dump-$(date +%Y%m%d).rdb
```

For automated backups, mount the data volume and use cron:

```bash
# Cron job: daily backup at 2 AM
0 2 * * * docker exec firecrawl-valkey valkey-cli BGSAVE && \
  sleep 5 && \
  cp /var/lib/docker/volumes/firecrawl_valkey-data/_data/dump.rdb \
     /backups/valkey-$(date +\%Y\%m\%d).rdb
```

## Distributed Locking

Firecrawl uses the Redlock pattern to coordinate concurrent workers and prevent duplicate
processing of the same crawl job.

### How Redlock Works in Firecrawl

```text
Worker A                   Valkey                    Worker B
   │                         │                         │
   ├── SET lock:crawl:123 ──▶│                         │
   │   NX EX 30              │                         │
   │◀── OK ─────────────────┤                         │
   │                         │◀── SET lock:crawl:123 ──┤
   │                         │    NX EX 30             │
   │                         ├── (nil) ───────────────▶│
   │   (processes job)       │       (skips/waits)     │
   │                         │                         │
   ├── DEL lock:crawl:123 ──▶│                         │
```

The `NX` (not exists) flag ensures only one worker acquires the lock. The `EX 30` sets a
30-second TTL as a safety net in case the holding worker crashes.

### Monitoring Locks

```bash
# Find active locks
docker exec firecrawl-valkey valkey-cli KEYS "lock:*"

# Check lock TTL (if stuck)
docker exec firecrawl-valkey valkey-cli TTL "lock:crawl:some-job-id"

# Force-release a stuck lock (use with caution)
docker exec firecrawl-valkey valkey-cli DEL "lock:crawl:some-job-id"
```

## Migration from Redis to Valkey

Valkey is wire-compatible with Redis. Migration is straightforward.

### Zero-Downtime Swap (Docker)

1. **Stop the Redis container:**

    ```bash
    docker compose stop redis
    ```

1. **Copy the data file:**

    ```bash
    # Redis and Valkey use the same dump.rdb format
    docker cp firecrawl-redis-1:/data/dump.rdb ./dump.rdb
    ```

1. **Update docker-compose.yaml:**

    ```yaml
    # Change
    image: redis:alpine
    # To
    image: valkey/valkey:alpine
    ```

1. **Restore data and start:**

    ```bash
    # Place dump.rdb in the Valkey volume
    docker cp ./dump.rdb firecrawl-valkey:/data/dump.rdb
    docker compose up -d
    ```

1. **Verify:**

    ```bash
    docker exec firecrawl-valkey valkey-cli INFO SERVER | grep server_name
    # server_name:valkey

    docker exec firecrawl-valkey valkey-cli DBSIZE
    # Should match pre-migration key count
    ```

### RDB Compatibility

The `dump.rdb` format is fully portable between Redis 7.x and Valkey 8.x. No conversion
tools needed — just copy the file.

### DNS-Based Zero-Downtime (Production)

For production environments using DNS-based service discovery:

1. Start a new Valkey instance alongside Redis
2. Use `REPLICAOF` to sync Valkey from Redis
3. Once synced (`INFO replication` shows `master_link_status:up`), update DNS to point to Valkey
4. Promote Valkey to primary with `REPLICAOF NO ONE`
5. Decommission Redis

## AWS ElastiCache with Valkey

AWS ElastiCache supports Valkey as a backend engine. Use it for managed production deployments.

### Connection String Format

```bash
# Standard ElastiCache endpoint
REDIS_URL=redis://your-cluster.abc123.use1.cache.amazonaws.com:6379

# With TLS (recommended)
REDIS_URL=rediss://your-cluster.abc123.use1.cache.amazonaws.com:6379

# With auth token
REDIS_URL=rediss://:your-auth-token@your-cluster.abc123.use1.cache.amazonaws.com:6379
```

Note the `rediss://` scheme (double s) for TLS connections.

### ElastiCache Configuration Tips

- **Node type:** `cache.r7g.large` or higher for production crawl workloads
- **Engine:** Select "Valkey" when creating the cluster
- **Parameter group:** Set `maxmemory-policy` to `noeviction`
- **Multi-AZ:** Enable for high availability
- **Encryption:** Enable in-transit (TLS) and at-rest encryption

### Firecrawl Environment for ElastiCache

```bash
REDIS_URL=rediss://:AUTH_TOKEN@primary-endpoint.cache.amazonaws.com:6379
REDIS_RATE_LIMIT_URL=rediss://:AUTH_TOKEN@primary-endpoint.cache.amazonaws.com:6379
```

If using a reader endpoint for rate-limit reads:

```bash
REDIS_RATE_LIMIT_URL=rediss://:AUTH_TOKEN@reader-endpoint.cache.amazonaws.com:6379
```

## Troubleshooting

### High memory usage

```bash
# Check what's consuming memory
docker exec firecrawl-valkey valkey-cli INFO memory

# Find large keys
docker exec firecrawl-valkey valkey-cli --bigkeys

# Check queue sizes for accumulation
docker exec firecrawl-valkey valkey-cli ZCARD bull:scrape:completed
```

If completed jobs are accumulating, configure BullMQ's `removeOnComplete` option to limit
retention (e.g., keep last 1000 completed jobs).

### Latency spikes

```bash
# Check for slow commands
docker exec firecrawl-valkey valkey-cli SLOWLOG GET 10

# Check if persistence is causing latency
docker exec firecrawl-valkey valkey-cli INFO persistence | grep rdb_last_bgsave_status
```

Large `KEYS` or `SMEMBERS` on big sets can cause latency. Use `SCAN` for iteration.

### Workers losing connection after scaling

When scaling workers rapidly, Valkey may hit `maxclients`. Check:

```bash
docker exec firecrawl-valkey valkey-cli CONFIG GET maxclients
docker exec firecrawl-valkey valkey-cli INFO clients | grep connected_clients
```

Increase `maxclients` in `valkey.conf` if needed:

```text
maxclients 10000
```

### ElastiCache connection timeouts

Common causes:

- Security group doesn't allow inbound on port 6379 from worker nodes
- Worker containers aren't in the same VPC
- TLS required but using `redis://` instead of `rediss://`

```bash
# Test connectivity from worker
docker exec firecrawl-worker-1 sh -c \
  "apk add redis && redis-cli -h your-cluster.cache.amazonaws.com -p 6379 PING"
```

---

[← Back to Firecrawl Cookbook](README.md)
