# Getting Started with Helicone + Valkey

> Learn how Helicone uses Valkey for KV caching and rate limiting through hands-on examples
> that mirror the actual patterns in Helicone's Jawn API server.

**Beginner** · JavaScript · ~15 min

**Who is this for:** Backend developers evaluating Valkey as a caching and rate-limiting layer,
or anyone curious how a production LLM observability platform uses core Valkey commands.

## Prerequisites

- **Docker** and **Docker Compose** (to run Valkey locally)
- **Node.js** 20+ with npm
- Basic familiarity with JavaScript and async/await

> **Security note:** The examples in this guide use default Valkey settings with no authentication.
> Never deploy Valkey without authentication and network restrictions in production.
> See [Production](02-production.md) for TLS and auth configuration.

## Step 1: Start Valkey

From the sample directory, start a Valkey 8 instance with Docker Compose:

```bash
cd cookbooks/framework-integrations/helicone/sample
docker compose up -d
```

This starts a `valkey/valkey:8.1-alpine` container on `127.0.0.1:6379` with a health check that
verifies the server responds to `PING`. Wait a few seconds for the service to become healthy:

```bash
docker compose ps
```

You should see the `valkey` service listed as "healthy".

## Step 2: Install Dependencies

Install the project dependencies (all versions are pinned in `package.json`):

```bash
npm install
```

The only runtime dependency is `ioredis` — no build step required.

## Step 3: Check Connectivity

Run the health check to confirm Valkey is reachable and verify the backend:

```bash
node scripts/health_check.mjs
```

Expected output:

```text
PING → PONG
Backend: Valkey 8.1.1
```

## Step 4: Connect

Each script creates a client directly:

```javascript
import Redis from "ioredis";

const client = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
```

In production, Helicone reads the host from `process.env.VALKEY_HOST` and enables TLS.
See [Production](02-production.md) for the full configuration.

## Step 5: KV Cache Pattern

Helicone's KV Cache uses `SET ... PX` for millisecond-precision TTL and `GET` for retrieval.
Values are stored as JSON strings:

```javascript
// Store with 5-second TTL
const value = JSON.stringify({ model: "gpt-4o", tokens: 512, cached: true });
await client.set("cache:response:abc123", value, "PX", 5000);

// Retrieve
const raw = await client.get("cache:response:abc123");
console.log(JSON.parse(raw)); // { model: "gpt-4o", tokens: 512, cached: true }

// After TTL expires, GET returns null
await new Promise((r) => setTimeout(r, 5100));
console.log(await client.get("cache:response:abc123")); // null
```

**What's happening:** `SET key value PX 5000` stores the value with a 5000ms TTL. Valkey automatically
deletes the key when the TTL expires. Helicone uses this for API response caches and frequently-accessed metadata.

## Step 6: Rate Limiting Pattern

Helicone's Proxy Rate Limiter uses `GET`/`SET EX` with a sliding window stored as a JSON array.
Each entry records a timestamp and unit count:

```javascript
const key = "rl_proxy_user123_3";
const now = Date.now();
const windowMs = 60_000;
const limit = 10;

// Read the current window
const raw = await client.get(key);
let entries = raw ? JSON.parse(raw) : [];

// Prune entries outside the window
entries = entries.filter((e) => e.timestamp >= now - windowMs);
const currentUsage = entries.reduce((sum, e) => sum + e.unit, 0);
const allowed = currentUsage < limit;

if (allowed) entries.push({ timestamp: now, unit: 1 });

// Write back with TTL matching the window
await client.set(key, JSON.stringify(entries), "EX", 60);
```

**What's happening:** The entire window state lives in one key as a JSON array. `SET EX 60` keeps
the key alive for one window duration. Stale entries are filtered out before writing the updated array back.

## Step 7: Simulate All 5 Patterns

The simulate script walks through all 5 Helicone subsystems with annotated output:

```bash
node scripts/simulate_helicone.mjs
```

Expected output:

```text
=== Helicone Pattern Simulation ===

1. KV Cache (SET PX / GET)
   Stored:    {"model":"gpt-4o","tokens":512,"cached":true}
   Retrieved: {"model":"gpt-4o","tokens":512,"cached":true}
   TTL: ~4998ms remaining

2. Proxy Rate Limiter (GET / SET EX — sliding window)
   Window entries: 1 (limit e.g. 10/min)
   TTL: 60s

3. Lua Rate Limiter (SCRIPT LOAD / EVALSHA)
   Script SHA: <40-char hex>
   Request count: 1, window TTL: ~60000ms

4. Usage Cache (GET / SET EX — cache-aside)
   Cache miss: null
   Cache hit:  true (TTL: 3600s)

5. Encrypted Key Cache (GET / SET EX — hashed key)
   Plain key:    api-key:openai-provider
   Hashed key:   <sha256-prefix>...
   Retrieved:    yes (TTL: 600s)

Cleanup: deleted 5 keys

=== Simulation Complete ===
```

## Step 8: Run the Tests

```bash
npm test
```

This runs `node --test tests/test_helicone_patterns.mjs` against the live Valkey instance
and verifies all 5 pattern groups with assertions.

## How It Works

```text
┌──────────────────────────────────────────────────────────┐
│                  Helicone Jawn API Server                │
├────────────┬─────────────┬─────────────┬─────────────────┤
│  KV Cache  │ Proxy Rate  │ Usage Limit │ Encrypted Key   │
│  GET/SET PX│ Limiter     │ Cache       │ Cache           │
│            │ GET/SET EX  │ GET/SET EX  │ GET/SET EX      │
├────────────┴─────────────┴─────────────┴─────────────────┤
│              Client (single connection)                  │
├──────────────────────────────────────────────────────────┤
│              Valkey 8 (core commands only)               │
└──────────────────────────────────────────────────────────┘
```

All 5 subsystems share one connection and use only core string commands
(`GET`, `SET EX`, `SET PX`) plus scripting commands (`SCRIPT LOAD`, `EVALSHA`).
No Valkey modules or extensions are required.

## Next Steps

- **[Production Guide](02-production.md)** — TLS, Lua scripting, monitoring, and encrypted storage
- **[Sample README](sample/README.md)** — Run the full sample application with all 5 subsystems

---

[← Back to Cookbook README](README.md)
