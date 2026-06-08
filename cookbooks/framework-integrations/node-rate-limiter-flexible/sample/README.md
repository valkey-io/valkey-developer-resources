# node-rate-limiter-flexible + Valkey Cookbook Sample

Runnable code for the [node-rate-limiter-flexible + Valkey cookbook series](../README.md).

## Prerequisites

1. **Docker** (for Valkey)
2. **Node.js 20+**

## Setup

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install
```

## Running

```bash
# 01 - Getting started (basic rate limiting)
npm run getting-started

# 02 - Middleware patterns (per-route, per-user, batch)
npm run middleware

# 03 - Advanced patterns (insurance, block, token-aware, escalation)
npm run advanced
```

## Testing

Run the automated test suite against a live Valkey instance:

```bash
npm test
```

This exercises all rate-limiting patterns (basic, insurance, block, reward, penalty) and verifies they work correctly.

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `src/getting-started.ts` | [01 - Getting Started](../01-getting-started.md) | Connect to Valkey, create a 10 req/sec limiter, serve a rate-limited Express endpoint |
| `src/middleware-patterns.ts` | [02 - Middleware Patterns](../02-middleware-patterns.md) | Reusable middleware, per-route limits, auth brute-force protection, variable-cost batch |
| `src/advanced-patterns.ts` | [03 - Advanced Patterns](../03-advanced-patterns.md) | Insurance failover, in-memory block, token-aware AI limiting, escalating blocks |
| `src/test-all.ts` | All | Automated verification of all patterns against Valkey |

## Cleanup

```bash
docker compose down
```
