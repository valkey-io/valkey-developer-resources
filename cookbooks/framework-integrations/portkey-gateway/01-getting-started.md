# Getting Started with Portkey AI Gateway + Valkey

**Beginner** · Python / TypeScript · ~15 min

## What is Portkey AI Gateway + Valkey?

[Portkey AI Gateway](https://github.com/Portkey-AI/gateway) routes requests to 250+ LLMs through a single API. By default it caches responses in memory, which means cache is lost on restart and cannot be shared across instances.

With Valkey as the cache backend you get:

* **Persistent caching** — LLM responses survive gateway restarts
* **Shared state** — multiple gateway instances read/write the same cache
* **Sub-millisecond reads** — Valkey serves cached responses in ~0.1ms
* **Built-in TTL** — keys auto-expire, no cleanup jobs

You talk to the gateway with the official [`portkey-ai`](https://github.com/Portkey-AI/portkey-python-sdk) SDK, and the gateway persists responses in Valkey via [`@valkey/valkey-glide`](https://github.com/valkey-io/valkey-glide).

## Prerequisites

* Docker or Podman installed
* Python 3.10+ or Node.js 18+
* An LLM provider API key (OpenAI, Anthropic, etc.)

## Step 1: Start Valkey

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

## Step 2: Start the Gateway with Valkey

Clone and build the gateway, then point it at Valkey with the `VALKEY_CONNECTION_STRING` environment variable. The gateway detects this at startup and initializes all cache backends with Valkey:

```bash
git clone https://github.com/Portkey-AI/gateway.git
cd gateway && npm install
```

Enable caching in `conf.json` — the cache middleware is only mounted when this flag is `true`:

```json
{
  "cache": true
}
```

> The gateway bundles `conf.json` at build time, so set this **before** running `npm run build`. Without it, requests return `x-portkey-cache-status: DISABLED` and nothing is cached.

```bash
export VALKEY_CONNECTION_STRING="valkey://localhost:6379"
npm run build && node build/start-server.js
```

You'll see in the logs:

```
[CacheService] Creating cache backends with Valkey valkey://localhost:6379
```

Supported connection string formats:

| Format | TLS | Example |
|--------|-----|---------|
| `valkey://host:port` | No | `valkey://localhost:6379` |
| `valkeys://host:port` | Yes | `valkeys://my-cluster.cache.amazonaws.com:6379` |
| `valkey://:password@host:port` | No | `valkey://:secret@localhost:6379` |
| `valkey://host1:6379,host2:6380?cluster=true` | No | Multi-seed cluster bootstrap |

> **Timeout errors?** The gateway's GLIDE client defaults to a 5000ms request timeout. If you're connecting to a remote or high-latency Valkey instance, raise `requestTimeout` in the gateway's client config (`src/shared/services/valkey/client.ts`). See [03 - Production](03-production.md) Step 7 for details.

## Step 3: Install the Portkey SDK

```bash
# Python
pip install portkey-ai

# Node.js
npm install portkey-ai
```

## Step 4: Make a Cached LLM Request

Point the SDK at your local gateway and enable simple caching. The gateway caches the first response in Valkey and serves identical follow-up requests from there — the second call returns in a fraction of the time.

**Python**

```python
import os
import time
from portkey_ai import Portkey

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Point the SDK at the local gateway; the gateway persists responses in Valkey
client = Portkey(
    api_key="dummy",  # the gateway authenticates the provider, not Portkey Cloud
    base_url="http://localhost:8787/v1",
    provider="openai",
    Authorization=f"Bearer {OPENAI_API_KEY}",
    config={"cache": {"mode": "simple"}},
)

messages = [{"role": "user", "content": "What is Valkey in one sentence?"}]

# First call — cache MISS, forwarded to the LLM and stored in Valkey
t0 = time.time()
client.chat.completions.create(model="gpt-4o-mini", messages=messages)
print(f"first call:  {time.time() - t0:.3f}s (MISS, hit the LLM)")

# Second identical call — cache HIT, served from Valkey in ~1ms
t0 = time.time()
client.chat.completions.create(model="gpt-4o-mini", messages=messages)
print(f"second call: {time.time() - t0:.3f}s (HIT, served from Valkey)")
```

**TypeScript**

```typescript
import { Portkey } from "portkey-ai";

const client = new Portkey({
  apiKey: "dummy",
  baseURL: "http://localhost:8787/v1",
  provider: "openai",
  Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
  config: { cache: { mode: "simple" } },
});

const messages = [{ role: "user", content: "What is Valkey in one sentence?" }];

// First call — cache MISS, forwarded to the LLM and stored in Valkey
let t0 = Date.now();
await client.chat.completions.create({ model: "gpt-4o-mini", messages });
console.log(`first call:  ${Date.now() - t0}ms (MISS, hit the LLM)`);

// Second identical call — cache HIT, served from Valkey
t0 = Date.now();
await client.chat.completions.create({ model: "gpt-4o-mini", messages });
console.log(`second call: ${Date.now() - t0}ms (HIT, served from Valkey)`);
```

## Step 5: Verify the Cache in Valkey

```bash
docker exec valkey valkey-cli --scan --pattern "default:*"
# Shows cached LLM response keys
```

## How It Works Under the Hood

| Operation | Valkey Command | When |
|-----------|---------------|------|
| Cache lookup | `GET default:llm-responses:{hash}` | Before forwarding to LLM |
| Cache write | `SET default:llm-responses:{hash} '{...}' EX ttl` | After receiving LLM response |
| Key expiry | Automatic via TTL | Configured per-request or default 5 min |
| Key scan | `SCAN 0 MATCH pattern COUNT 100` | On cache clear/stats |

**Source:** [`src/shared/services/cache/backends/valkey.ts`](https://github.com/Portkey-AI/gateway/blob/main/src/shared/services/cache/backends/valkey.ts)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Cannot find module '@valkey/valkey-glide'` | Run `npm install` in the gateway directory |
| Connection refused on port 6379 | Ensure Valkey is running: `docker ps` or `podman ps` |
| Gateway still uses in-memory cache | Confirm `VALKEY_CONNECTION_STRING` is set before starting |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` (includes the Search module) |
| Cache always `DISABLED` | Set `"cache": true` in `conf.json` and rebuild — the cache middleware only mounts when enabled |
| Cache always MISS | Caching skips streaming requests; use a non-streaming call with `cache.mode: simple` |

---

[02 - Vector Search →](02-vector-search.md)
