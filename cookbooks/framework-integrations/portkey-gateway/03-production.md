# Production with ElastiCache

**Advanced** · Python / TypeScript · ~20 min

## What You'll Configure

Running the Portkey AI Gateway with Valkey in production means connecting to a managed, TLS-secured Valkey cluster instead of a local container. This cookbook covers connecting the gateway to [Amazon ElastiCache for Valkey](https://aws.amazon.com/elasticache/), enabling TLS, cluster mode, authentication, and tuning the cache TTLs.

## Architecture Overview

```
┌──────────────────┐     ┌─────────────────────┐
│  Portkey AI      │────▶│  ElastiCache for     │
│  Gateway         │     │  Valkey 8.2+         │
│  (Node.js)       │◀────│  (cache + vectors)   │
└──────────────────┘     └─────────────────────┘
        │
        ▼
   250+ LLM providers
```

The gateway uses a single `@valkey/valkey-glide` connection (or cluster client) for all cache namespaces — LLM responses, sessions, config, OAuth, and MCP servers.

> **Two connection paths:** The gateway connects to Valkey in two independent ways:
>
> 1. **Cache backend** (`VALKEY_CONNECTION_STRING` env var) — a shared GLIDE connection established at startup for all cache namespaces. Configured once at deploy time.
> 2. **Vector search provider** (`customHost` SDK header) — a per-request connection used by the `valkey-search` provider for `FT.*` commands. Configured client-side in your SDK calls.
>
> In production, both typically point to the same ElastiCache cluster, but they are configured separately.

## Step 1: ElastiCache for Valkey Setup

Create a Valkey 8.2+ cluster with the Search module (included by default in 8.2+):

```bash
aws elasticache create-serverless-cache \
  --serverless-cache-name portkey-gateway \
  --engine valkey \
  --major-engine-version 8
```

> **Important**: ElastiCache for Valkey 8.2+ includes the Search module by default — required for the `valkey-search` provider's vector operations.

## Step 2: Connect the Cache Backend with TLS

ElastiCache Serverless requires TLS. Use the `valkeys://` scheme (note the trailing `s`):

```bash
export VALKEY_CONNECTION_STRING="valkeys://portkey-gateway-xxxxx.serverless.use1.cache.amazonaws.com:6379"
npm run build && node build/start-server.js
```

This configures the **cache backend** (LLM response caching, sessions, config). For the **vector search provider**, pass the same endpoint via the SDK:

```python
client = Portkey(
    provider="valkey-search",
    custom_host="valkeys://portkey-gateway-xxxxx.serverless.use1.cache.amazonaws.com:6379",
)
```

The connection string parser enables TLS automatically for `valkeys://` and `rediss://` schemes.

| Scheme | TLS | Use |
|--------|-----|-----|
| `valkey://` | No | Local development |
| `valkeys://` | Yes | ElastiCache, production |
| `rediss://` | Yes | TLS-enabled Redis-compatible endpoints |

## Step 3: Authentication

For password-protected clusters, embed the password in the connection string. Never hardcode it — read it from a secret manager and inject it as an environment variable:

```bash
# Password is URL-encoded and injected from a secret store at deploy time
export VALKEY_CONNECTION_STRING="valkeys://:${VALKEY_PASSWORD}@host:6379"
```

The parser extracts the password and passes it to GLIDE as connection credentials. The redacted form (password replaced with `***`) is what appears in the startup logs.

## Step 4: Cluster Mode

For an ElastiCache cluster-mode-enabled deployment, add `?cluster=true` and optionally list multiple seed nodes for bootstrap resilience:

```bash
export VALKEY_CONNECTION_STRING="valkeys://node1.cache.amazonaws.com:6379,node2.cache.amazonaws.com:6379?cluster=true"
```

GLIDE discovers all nodes via `CLUSTER SLOTS`; the additional seeds only improve initial connection resilience. The gateway switches to `GlideClusterClient` automatically when `cluster=true` is set.

## Step 5: Tune Cache TTLs

The gateway provisions separate cache namespaces, each with a configurable TTL via environment variables:

| Variable | Default | Namespace |
|----------|---------|-----------|
| `VALKEY_DEFAULT_TTL_MS` | 5 min | Default cache (LLM responses) |
| `VALKEY_SESSION_TTL_MS` | 30 min | Session cache |
| `VALKEY_CONFIG_TTL_MS` | 30 days | Config cache |

```bash
export VALKEY_DEFAULT_TTL_MS=600000    # 10 min for LLM responses
export VALKEY_SESSION_TTL_MS=3600000   # 1 hour for sessions
```

Per-request cache TTL is also controllable with the `x-portkey-cache` header and a `max_age` config value, which overrides the default for that request.

## Step 6: HNSW Tuning for Vector Search

When creating indexes via the `valkey-search` provider, the HNSW algorithm uses Valkey's defaults. For larger datasets, pre-create the index with tuned parameters using a direct Valkey connection:

| Parameter | Default | Production Recommendation | Effect |
|-----------|---------|---------------------------|--------|
| `M` | 16 | 16–64 | Higher = better recall, more memory |
| `EF_CONSTRUCTION` | 200 | 200–500 | Higher = better index quality, slower builds |
| `EF_RUNTIME` | 10 | 50–200 | Higher = better recall at query time |

The gateway's index API accepts `HNSW` or `FLAT` as the `algorithm`; use `FLAT` for exact search on small datasets (<1000 vectors) and `HNSW` for approximate search at scale.

## Step 7: Connection Timeout

GLIDE's default request timeout is low. The gateway sets it to 5000ms, which is appropriate for a network-attached ElastiCache cluster. If you see timeout errors under load, the value is set in the client factory (`requestTimeout`) — raise it for high-latency networks.

## Step 8: Error Handling in Client Code

The Portkey SDK raises typed exceptions for the gateway's error responses. Handle them so a transient Valkey issue degrades gracefully rather than crashing your app:

**Python**

```python
from portkey_ai.api_resources.exceptions import (
    NotFoundError, ConflictError, APIStatusError,
)

try:
    client.post("/indexes/documents/search", vector=query_vec, top_k=5)
except NotFoundError:
    # 404 — index missing; create it or fall back
    rebuild_index()
except APIStatusError as e:
    if e.status_code == 503:
        # Valkey temporarily unreachable — retry with backoff
        retry_later()
    else:
        raise
```

**TypeScript**

```typescript
try {
  await client.post("/indexes/documents/search", { vector: queryVec, top_k: 5 });
} catch (e) {
  if (e.status === 404) {
    await rebuildIndex();        // index missing
  } else if (e.status === 503) {
    await retryLater();          // Valkey temporarily unreachable
  } else {
    throw e;
  }
}
```

## Step 9: Monitoring

Monitor via CloudWatch (ElastiCache) or directly:

```bash
# Vector index stats
valkey-cli FT.INFO "<index-name>"

# Memory usage — vector indexes consume significant RAM
valkey-cli INFO memory

# Cache hit rate — inspect cached LLM response keys
valkey-cli --scan --pattern "default:llm-responses:*" | wc -l

# Connected clients
valkey-cli INFO clients
```

Key metrics to watch:
- **Cache hit rate**: ratio of cache hits to total LLM requests
- **Memory usage**: vector indexes and cached responses consume RAM
- **Search latency**: track `FT.SEARCH` execution time
- **Eviction count**: rising evictions mean the cluster is undersized

## Cost Considerations

| Component | Cost Driver | Optimization |
|-----------|-------------|--------------|
| ElastiCache Serverless | ECPUs + storage | Right-size based on cache + vector volume |
| LLM providers | Tokens per request | Higher cache hit rate = fewer billed calls |
| Data transfer | Cross-AZ traffic | Co-locate gateway and ElastiCache in one AZ |

A higher cache hit rate directly reduces LLM spend — the main reason to run a persistent cache in the first place.

## Checklist

- [ ] ElastiCache for Valkey 8.2+ with Search module
- [ ] TLS enabled (`valkeys://` scheme)
- [ ] Password injected from a secret manager, never hardcoded
- [ ] Cluster mode configured if using cluster-mode-enabled ElastiCache
- [ ] Cache TTLs tuned per namespace
- [ ] HNSW parameters tuned for your vector dataset size
- [ ] CloudWatch alarms on memory, latency, and evictions
- [ ] Gateway and ElastiCache co-located in the same region/AZ

**Source:** [`src/shared/services/valkey/client.ts`](https://github.com/Portkey-AI/gateway/blob/main/src/shared/services/valkey/client.ts) · [`src/shared/services/cache/index.ts`](https://github.com/Portkey-AI/gateway/blob/main/src/shared/services/cache/index.ts)

---

[← 02 - Vector Search](02-vector-search.md)
