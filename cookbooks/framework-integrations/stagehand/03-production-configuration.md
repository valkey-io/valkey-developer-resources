# Production Configuration

> Configure TLS, ACL authentication, and environment variable-based setup for deploying Stagehand with Valkey in production or via the Stagehand server.

**Intermediate** · TypeScript · ~15 min

**Who is this for:** Engineers deploying Stagehand + Valkey beyond local dev — to a managed Valkey instance (e.g. ElastiCache) with TLS and ACL auth.

Moving from a local dev setup to production means adding TLS encryption, authentication, and optionally configuring the Stagehand server to accept Valkey settings from clients or environment variables.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- A Valkey instance with TLS and/or ACL authentication (e.g., AWS ElastiCache for Valkey, or a self-hosted TLS-enabled instance)

## Step 1: Enable TLS

Set `valkeyTls: true` to connect over an encrypted channel:

```typescript
import { Stagehand } from "@browserbasehq/stagehand";

const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: "my-valkey.example.com",
  valkeyPort: 6379,
  valkeyTls: true,
});

await stagehand.init();
try {
  // ... automation code ...
} finally {
  await stagehand.close();
}
```

## Step 2: Add Authentication

For ACL-enabled Valkey instances, provide both `valkeyUsername` and `valkeyPassword`:

```typescript
const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: process.env.VALKEY_HOST!,
  valkeyPort: 6379,
  valkeyTls: true,
  valkeyUsername: process.env.VALKEY_USERNAME!,
  valkeyPassword: process.env.VALKEY_PASSWORD!,
});

await stagehand.init();
try {
  // ... automation code ...
} finally {
  await stagehand.close();
}
```

For instances using a single auth token (no ACL username), provide only `valkeyPassword`:

```typescript
const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: process.env.VALKEY_HOST!,
  valkeyTls: true,
  valkeyPassword: process.env.VALKEY_PASSWORD!,
});

await stagehand.init();
try {
  // ... automation code ...
} finally {
  await stagehand.close();
}
```

## Step 3: Server-Side Configuration via Environment Variables

When running the Stagehand server (`@browserbasehq/stagehand-server`), Valkey can be configured via environment variables instead of per-session client parameters:

```bash
export VALKEY_HOST=my-valkey.example.com
export VALKEY_PORT=6379
export VALKEY_TLS=true
export VALKEY_USERNAME=stagehand-svc
export VALKEY_PASSWORD=<your-valkey-password>
export VALKEY_CACHE_TTL=3600
export VALKEY_KEY_PREFIX=prod-stagehand
```

The server reads these at session creation time. Every session started without an explicit `valkeyCache` config block will use these defaults.

> **Note:** The env var is `VALKEY_CACHE_TTL`, not `CACHE_TTL` — verified against
> [`InMemorySessionStore.ts`](https://github.com/edlng/stagehand/blob/feat/valkey-cache-backend/packages/server-v3/src/lib/InMemorySessionStore.ts) in the fork.
> If you're configuring the Python SDK's local mode instead (see the [Python track](../stagehand-python/03-production-configuration.md)),
> that path sets `CACHE_TTL`, not `VALKEY_CACHE_TTL` — the two forks don't agree on this one name yet.
> Passing `valkeyCache`/`valkey_cache` explicitly in the request body (Step 4) avoids the env var entirely and isn't affected.

## Step 4: Per-Session Override via the Server API

Clients can also pass Valkey config explicitly in the session start request body:

```typescript
const token = process.env.CUSTOM_VALKEY_TOKEN;
if (!token) throw new Error("CUSTOM_VALKEY_TOKEN required for per-session override");

const response = await fetch("http://localhost:3000/v1/sessions/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "gpt-4o-mini",
    valkeyCache: {
      valkeyHost: "custom-valkey.internal",
      valkeyPort: 6379,
      valkeyTls: true,
      valkeyPassword: token,
      cacheTtl: 1800,
      valkeyKeyPrefix: "team-a",
    },
  }),
});
```

This overrides any server-side environment defaults for that session.

> **Note:** The Python SDK's `valkey_cache` dict uses shorter field names (`host`, `port`, `tls`, `password`, `username`, `cache_ttl`, `key_prefix`)
> which are mapped to the wire-format camelCase keys shown above (`valkeyHost`, `valkeyPort`, `valkeyTls`, etc.). Both tracks talk to the same server API.

## Graceful Degradation

If the Valkey connection fails (wrong host, network issues, auth failure), Stagehand logs the error and continues with caching disabled.
Automations still execute - they just make LLM calls on every run instead of replaying cached actions.

```text
[cache] unable to initialize valkey cache: connection refused
```

No exceptions are thrown and no automation is interrupted.

## Configuration Reference

`V3Options` fields (constructor) and their `valkeyCache` request-body equivalents:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `valkeyHost` | ✓ | — | Valkey host address. Caching is disabled entirely unless this is set. |
| `valkeyPort` | — | `6379` | Valkey port |
| `valkeyTls` | — | `true` if `valkeyPassword` is set, else `false` | Enable TLS for the connection |
| `valkeyUsername` | — | — | ACL username |
| `valkeyPassword` | — | — | Auth password or token |
| `cacheTtl` | — | none (persists indefinitely) | TTL in seconds for cache entries |
| `valkeyKeyPrefix` | — | `"stagehand"` | Key namespace prefix |
| `valkeyRequestTimeout` | — | `5000` (ms) | Timeout for individual Valkey operations |
| `valkeyMaxCacheValueBytes` | — | `5242880` (5 MB) | Writes exceeding this size are skipped and logged, not cached |

---

[← 02 - Cache Categories and TTL](02-cache-categories-and-ttl.md)
