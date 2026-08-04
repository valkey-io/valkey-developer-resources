# Production Configuration

> Configure TLS, ACL authentication, and environment variable-based setup for deploying Stagehand with Valkey in production.

**Intermediate** · Python · ~15 min

**Who is this for:** Engineers deploying the Stagehand server + Valkey beyond local dev — to a managed Valkey instance (e.g. ElastiCache) with TLS and ACL auth.

Moving from a local dev setup to production means adding TLS encryption, authentication, and configuring the Stagehand server to connect to a managed Valkey instance.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- A Valkey instance with TLS and/or ACL authentication (e.g., AWS ElastiCache for Valkey, or a self-hosted TLS-enabled instance)

## Step 1: Server-Side Configuration via Environment Variables

Configure the Stagehand server with production Valkey settings:

```bash
export VALKEY_HOST=my-valkey.example.com
export VALKEY_PORT=6379
export VALKEY_TLS=true
export VALKEY_USERNAME=stagehand-svc
export VALKEY_PASSWORD=<your-valkey-password>
export VALKEY_CACHE_TTL=3600
export VALKEY_KEY_PREFIX=prod-stagehand

npx tsx src/server.ts
```

The server reads these at startup. Every session uses these defaults automatically.

## Step 2: Connect the Python Client

The Python client connects to the server as normal - no Valkey config needed on the client side:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url=os.environ["STAGEHAND_SERVER_URL"],
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(model_name="gpt-4o-mini")
try:
    pass  # ... automation code, caching happens server-side ...
finally:
    client.sessions.end(id=session.data.session_id)
    client.close()
```

## Step 3: Per-Session Override via the Client API

Clients can override server-side Valkey defaults for a specific session using `valkey_cache`:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url=os.environ["STAGEHAND_SERVER_URL"],
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(
    model_name="gpt-4o-mini",
    valkey_cache={
        "host": "custom-valkey.internal",
        "port": 6379,
        "tls": True,
        "password": os.environ["CUSTOM_VALKEY_TOKEN"],
        "cache_ttl": 1800,
        "key_prefix": "team-a",
    },
)
try:
    pass  # ... automation code ...
finally:
    client.sessions.end(id=session.data.session_id)
    client.close()
```

This overrides any server-side environment defaults for that session.

## Step 4: Client Constructor Params (Local Mode)

When using `server="local"`, pass Valkey config directly to the constructor. These parameters are forwarded as environment variables to the server process:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    server="local",
    model_api_key=os.environ["MODEL_API_KEY"],
    valkey_host=os.environ["VALKEY_HOST"],
    valkey_port=6379,
    valkey_tls=True,
    valkey_username=os.environ["VALKEY_USERNAME"],
    valkey_password=os.environ["VALKEY_PASSWORD"],
    valkey_cache_ttl=3600,
    valkey_key_prefix="prod-stagehand",
)
```

These params are passed as environment variables to the underlying server process.

> ⚠️ **Local mode caching doesn't work end-to-end yet.** `server="local"` requires a downloaded platform-specific SEA binary
> (the constructor raises `FileNotFoundError` without one — see the SDK's local-development docs). The core server's cache
> backend also dynamically imports `iovalkey` at runtime rather than bundling it (see
> [`CacheStorage.ts`](https://github.com/edlng/stagehand/blob/feat/valkey-cache-backend/packages/core/lib/v3/cache/CacheStorage.ts)
> in the fork) — a prebuilt SEA binary doesn't include it, so that import fails and the connection silently falls back to disabled.
> Separately, `valkey_cache_ttl` wouldn't take effect even if the import succeeded: this SDK forwards it as a `CACHE_TTL` env var, but the server reads `VALKEY_CACHE_TTL`
> (see the note in the [TypeScript track's Step 3](../stagehand/03-production-configuration.md#step-3-server-side-configuration-via-environment-variables))
> — the two forks haven't reconciled that name yet.
> Use **server mode** (Steps 1-3) for working Valkey caching today; local mode is documented here for when these issues are resolved upstream.

## Graceful Degradation

If the Valkey connection fails (wrong host, network issues, auth failure), Stagehand logs the error and continues with caching disabled.
Automations still execute, they just make LLM calls on every run instead of replaying cached actions.

```text
[cache] unable to initialize valkey cache: connection refused
```

No exceptions are thrown and no automation is interrupted.

## Configuration Reference

`valkey_cache` dict fields (per-session, remote/server mode — the reliable path):

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `host` | ✓ | — | Valkey host address. Caching is disabled entirely unless this is set. |
| `port` | — | `6379` | Valkey port |
| `tls` | — | `true` if `password` is set, else `false` | Enable TLS for the connection |
| `username` | — | — | ACL username |
| `password` | — | — | Auth password or token |
| `cache_ttl` | — | none (persists indefinitely) | TTL in seconds for cache entries |
| `key_prefix` | — | `"stagehand"` | Key namespace prefix |

Client constructor params (`server="local"` — see the caveat above before relying on this):

| Field | Env var forwarded | Default |
|-------|-------------------|---------|
| `valkey_host` | `VALKEY_HOST` | — |
| `valkey_port` | `VALKEY_PORT` | `6379` |
| `valkey_tls` | `VALKEY_TLS` | `true` if password set, else `false` |
| `valkey_username` | `VALKEY_USERNAME` | — |
| `valkey_password` | `VALKEY_PASSWORD` | — |
| `valkey_cache_ttl` | `CACHE_TTL` (server expects `VALKEY_CACHE_TTL` — see caveat) | none |
| `valkey_key_prefix` | `VALKEY_KEY_PREFIX` | `"stagehand"` |

The TypeScript track's `V3Options` also exposes `valkeyRequestTimeout` and `valkeyMaxCacheValueBytes`
(see its [Configuration Reference](../stagehand/03-production-configuration.md#configuration-reference)).
Neither `ValkeyCacheOptions` nor the local-mode constructor params expose these from Python yet — this SDK doesn't have a knob for them today.

---

[← 02 - Cache Categories and TTL](02-cache-categories-and-ttl.md)
