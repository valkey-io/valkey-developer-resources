# Recall + Valkey — Sample Project

Scripts and integration tests that validate the Valkey data patterns used by
[Recall](https://github.com/joseairosa/recall) for persistent AI memory.

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install

# Run health check
node scripts/health_check.mjs

# Run integration tests
node --test tests/
```

## What's Included

- `scripts/health_check.mjs` — Verify Valkey connectivity via `@valkey/valkey-glide`
- `scripts/simulate_recall.mjs` — Simulate Recall's memory storage patterns
- `tests/test_valkey_patterns.mjs` — Integration tests for Recall's key patterns
