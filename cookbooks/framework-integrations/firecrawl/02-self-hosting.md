# Self-Hosting Firecrawl with Valkey

> Deploy a production-ready self-hosted Firecrawl instance with Valkey as the backend for
> job queues, rate limiting, and crawl state management.

**Intermediate** · Docker · ~20 min

**Who is this for:** Teams self-hosting Firecrawl who want to use Valkey instead of Redis for open governance and BSD-3 licensing.

## Prerequisites

- Completed [Getting Started](01-getting-started.md)
- Docker and Docker Compose installed
- Familiarity with environment variables and YAML configuration

> **Security Note:** Production deployments should configure Valkey authentication, bind to
> private interfaces, and enable TLS. See the
> [Valkey security documentation](https://valkey.io/topics/security/) for guidance.

## Docker Compose Configuration

A full production-oriented `docker-compose.yaml` with Valkey, the API server, and workers:

```yaml
version: "3.9"

services:
  valkey:
    image: valkey/valkey:8.1-alpine
    container_name: firecrawl-valkey
    volumes:
      - valkey-data:/data
      - ./valkey.conf:/usr/local/etc/valkey/valkey.conf
    command: valkey-server /usr/local/etc/valkey/valkey.conf
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  firecrawl-api:
    image: ghcr.io/firecrawl/firecrawl:1.1.0
    container_name: firecrawl-api
    ports:
      - "3002:3002"
    environment:
      - REDIS_URL=redis://valkey:6379
      - REDIS_RATE_LIMIT_URL=redis://valkey:6379
      - PORT=3002
      - NUM_WORKERS_PER_QUEUE=2
    depends_on:
      valkey:
        condition: service_healthy
    restart: unless-stopped

  firecrawl-worker:
    image: ghcr.io/firecrawl/firecrawl:1.1.0
    container_name: firecrawl-worker
    environment:
      - REDIS_URL=redis://valkey:6379
      - REDIS_RATE_LIMIT_URL=redis://valkey:6379
      - NUM_WORKERS_PER_QUEUE=4
    depends_on:
      valkey:
        condition: service_healthy
    deploy:
      replicas: 2
    restart: unless-stopped

volumes:
  valkey-data:
```

Note: The service is named `valkey` but the `REDIS_URL` still uses the `redis://` protocol
scheme — this is correct because ioredis uses the scheme for protocol selection, and
Valkey speaks the same protocol.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `REDIS_URL` | Primary Valkey connection for BullMQ queues and state | `redis://valkey:6379` |
| `REDIS_RATE_LIMIT_URL` | Valkey connection for rate limiting (can be same instance) | `redis://valkey:6379` |
| `NUM_WORKERS_PER_QUEUE` | Concurrent jobs per queue per worker container | `2` |
| `CRAWL_CONCURRENT_REQUESTS` | Max concurrent requests per crawl | `10` |
| `MAX_CONCURRENT_JOBS` | Max concurrent jobs across all queues | `5` |

For high-throughput deployments, you can point `REDIS_RATE_LIMIT_URL` to a separate Valkey
instance to isolate rate-limiting load from job queue operations.

## Valkey Configuration

Create a `valkey.conf` file for production settings:

```text
# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Memory management
maxmemory 2gb
maxmemory-policy noeviction

# Performance
tcp-backlog 511
timeout 300
tcp-keepalive 60

# Security (uncomment for production)
# requirepass your-strong-password
# bind 127.0.0.1
```

### Why `noeviction` is Critical

BullMQ stores job data, queue metadata, and completion records in Valkey. If Valkey evicts
keys under memory pressure:

- Jobs disappear silently — no error, no retry, just lost work
- Queue state becomes inconsistent — workers may process jobs that were already completed
- Rate limit counters reset — allowing burst traffic that overwhelms target sites

The `noeviction` policy makes Valkey return errors on write when memory is full, which BullMQ
handles gracefully with backpressure. This is always preferable to silent data loss.

## BullMQ and Valkey

Firecrawl uses BullMQ for all job orchestration. Understanding the queue structure helps
with debugging and monitoring.

### Queue Architecture

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  API Server │────▶│    Valkey    │◀────│   Workers   │
│  (enqueue)  │     │  (BullMQ)    │     │  (process)  │
└─────────────┘     └──────────────┘     └─────────────┘
```

Key queues:

- `bull:scrape` — Individual page scrape jobs
- `bull:crawl` — Multi-page crawl orchestration jobs
- `bull:crawl-status` — Crawl progress tracking

### Retry Behavior

BullMQ retries failed jobs with exponential backoff. Default settings:

```typescript
{
  attempts: 3,
  backoff: {
    type: 'exponential',
    delay: 1000  // 1s, 2s, 4s
  }
}
```

Failed jobs move to the `failed` set after all retries are exhausted. Monitor with:

```bash
docker exec firecrawl-valkey valkey-cli ZCARD bull:scrape:failed
```

## Rate Limiting

Firecrawl implements rate limiting using the `INCR` + `EXPIRE` pattern in Valkey.

### Sliding Window Pattern

```typescript
// Simplified rate limit check (actual implementation in src/lib/rate-limiter.ts)
async function checkRateLimit(
  key: string,
  limit: number,
  windowSec: number
): Promise<boolean> {
  const current = await redis.incr(key);
  if (current === 1) {
    await redis.expire(key, windowSec);
  }
  return current <= limit;
}
```

Rate limits are applied at multiple levels:

- **Per API key** — Prevents a single user from consuming all capacity
- **Per domain** — Respects target site rate limits and robots.txt crawl-delay
- **Global** — Protects the Firecrawl instance from overload

### Inspecting Rate Limit State

```bash
# Check current rate limit counters
docker exec firecrawl-valkey valkey-cli KEYS "rate_limit:*"

# Check a specific key's remaining TTL
docker exec firecrawl-valkey valkey-cli TTL "rate_limit:api_key:fc-abc123"

# Check current count
docker exec firecrawl-valkey valkey-cli GET "rate_limit:api_key:fc-abc123"
```

## Crawl State Management

For multi-page crawls, Firecrawl uses Valkey sorted sets and sets to manage the URL frontier.

### Sorted Sets for URL Priority

```bash
# URLs to crawl, scored by priority (lower = higher priority)
docker exec firecrawl-valkey valkey-cli ZRANGE "crawl:<job-id>:queue" 0 -1 WITHSCORES
```

### SADD for Deduplication

```bash
# Already-visited URLs for a crawl session
docker exec firecrawl-valkey valkey-cli SMEMBERS "crawl:<job-id>:visited"

# Check if a URL was already crawled
docker exec firecrawl-valkey valkey-cli SISMEMBER "crawl:<job-id>:visited" \
  "https://example.com/page"
```

This prevents infinite loops on sites with circular links and avoids wasting resources
re-scraping pages already in the result set.

## Health Checks

### Valkey Health

```bash
# Basic connectivity
docker exec firecrawl-valkey valkey-cli PING

# Memory usage
docker exec firecrawl-valkey valkey-cli INFO memory | grep used_memory_human

# Connected clients (should show API + workers)
docker exec firecrawl-valkey valkey-cli INFO clients | grep connected_clients

# Key count per database
docker exec firecrawl-valkey valkey-cli INFO keyspace
```

### BullMQ Queue Health

```bash
# Waiting jobs (backlog)
docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:wait

# Active jobs (currently processing)
docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:active

# Completed count
docker exec firecrawl-valkey valkey-cli ZCARD bull:scrape:completed
```

### Docker Health Check

The `docker-compose.yaml` above includes a health check. Verify it's passing:

```bash
docker inspect firecrawl-valkey --format='{{.State.Health.Status}}'
# healthy
```

## Troubleshooting

### Workers not processing jobs

Check that workers can connect to Valkey:

```bash
docker compose logs firecrawl-worker | grep -i "redis\|valkey\|connect"
```

Verify the queue has waiting jobs:

```bash
docker exec firecrawl-valkey valkey-cli LLEN bull:scrape:wait
```

### Memory growing unbounded

If `INFO memory` shows continuous growth:

```bash
docker exec firecrawl-valkey valkey-cli INFO memory | grep used_memory_human
```

Check for completed job data accumulating:

```bash
docker exec firecrawl-valkey valkey-cli ZCARD bull:scrape:completed
```

BullMQ retains completed jobs by default. Configure `removeOnComplete` in Firecrawl's
queue settings to auto-prune old jobs.

### Rate limit errors (429 responses)

Check current rate limit state:

```bash
docker exec firecrawl-valkey valkey-cli KEYS "rate_limit:*" | head -20
```

If limits are too restrictive, adjust via environment variables or Firecrawl's configuration.

### Crawl jobs stuck in active state

Jobs can get stuck if a worker crashes mid-processing. BullMQ's stalled-job detection
should recover these automatically. Check stalled count:

```bash
docker exec firecrawl-valkey valkey-cli ZCARD bull:crawl:stalled
```

---

**Next:** [Production Operations →](03-production-operations.md)

[← Back to Firecrawl Cookbook](README.md)
