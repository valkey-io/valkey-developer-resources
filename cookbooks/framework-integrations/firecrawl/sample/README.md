# Firecrawl + Valkey Cookbook Sample

Validates that Firecrawl's Redis/Valkey patterns work correctly against a Valkey backend.
Firecrawl uses [ioredis](https://github.com/redis/ioredis) which is wire-compatible with
Valkey — same commands, same protocol, zero code changes.

## Patterns Tested

- **SET/GET with EX** — page cache with TTL
- **INCR + EXPIRE** — rate limiting
- **ZADD/ZREM/ZRANGE** — sorted sets for crawl state tracking
- **SADD/SMEMBERS** — URL deduplication
- **Lua scripts** — SCRIPT LOAD + EVALSHA
- **Pipelines** — multi-command batches

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install

# Run health check
node scripts/health_check.mjs

# Simulate Firecrawl patterns
node scripts/simulate_firecrawl.mjs

# Run integration tests
npm test
```

## Prerequisites

- Node.js >= 18
- Docker / Docker Compose
