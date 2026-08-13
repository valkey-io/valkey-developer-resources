# Helicone + Valkey Sample

Validates that Helicone's Valkey patterns work correctly against a live Valkey backend.
Uses the same client library Helicone uses in production.

## Patterns Covered

- **SET/GET with PX** — KV cache with millisecond TTL
- **GET / SET EX (JSON array)** — Sliding window rate limiter
- **SCRIPT LOAD / EVALSHA** — Atomic Lua rate limiter (INCR + PEXPIRE + PTTL)
- **GET / SET EX (cache-aside)** — Usage limit cache
- **GET / SET EX (hashed key)** — Encrypted key storage (app handles AES-GCM; Valkey stores opaque bytes)

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install

# Check connectivity
node scripts/health_check.mjs

# Walk through all 5 patterns with output
node scripts/simulate_helicone.mjs

# Run integration tests
npm test
```

## File Structure

```text
sample/
├── docker-compose.yml            # Valkey 8.1-alpine, bound to 127.0.0.1
├── .env.example                  # Environment variables reference
├── .gitignore
├── package.json                  # Single dependency: ioredis
├── scripts/
│   ├── health_check.mjs          # PING + INFO SERVER, confirms server_name:valkey
│   └── simulate_helicone.mjs     # Walks all 5 patterns with console output
└── tests/
    └── test_helicone_patterns.mjs  # node:test integration tests for all 5 patterns
```

## Prerequisites

- Node.js >= 20
- Docker / Docker Compose

---

[← Back to Cookbook](../README.md)
