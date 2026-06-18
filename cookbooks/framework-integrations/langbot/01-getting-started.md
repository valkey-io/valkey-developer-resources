# Getting Started with LangBot + Valkey

**Beginner** · Python · ~15 min

## What is LangBot + Valkey?

[LangBot](https://github.com/langbot-app/LangBot) is an open-source, production-grade platform for building agentic IM bots across Discord, Slack, Telegram, WeChat, Lark, DingTalk, QQ, and Matrix. It ships agent orchestration, a knowledge base (RAG), a plugin system, and a configurable message pipeline.

Valkey plugs into two LangBot subsystems, both **opt-in and disabled by default**:

- **Distributed rate limiting** — the `valkey_fixwin` pipeline algorithm shares one fixed-window counter across worker processes, so a multi-worker deployment enforces a single global limit instead of one limit per worker.
- **Vector search** — the `valkey_search` knowledge-base backend stores embeddings in Valkey Search and serves vector, full-text, and hybrid queries.

Both talk to Valkey through the official [`valkey-glide`](https://github.com/valkey-io/valkey-glide) client (Rust core + async Python bindings).

## Prerequisites

- Python 3.10+
- Docker or Podman (for running Valkey)
- `valkey-glide>=2.4.1,<3.0.0` — installed in [Step 2](#step-2-install-the-valkey-client)

## Step 1: Start Valkey with the Search Module

The vector-search backend needs the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image ships it (along with JSON and other modules), so use it for both integrations:

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it is running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

> **Note**: The rate limiter only needs core commands (`INCR`/`EXPIRE`), so plain `valkey/valkey:latest` is enough if you are *only* doing rate limiting. The vector-search backend requires the search module, so `valkey/valkey-bundle:latest` covers both.

## Step 2: Install the Valkey Client

Both backends use `valkey-glide`. LangBot keeps it as an optional dependency (each backend has an import guard), so install it explicitly:

```bash
pip install 'valkey-glide>=2.4.1,<3.0.0'
```

The typed search API (`ft.create`, `ft.search`) that the vector backend relies on is available in `valkey-glide` 2.4.1 and later — pin below 3.0.0 to stay on the verified major version.

## Step 3: Verify the Connection

This snippet connects, pings, and lists search indexes to confirm the module is present. It wraps the client in `try/finally` so the connection is always closed.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

```python
"""Quick connectivity check for LangBot's Valkey backends."""
import asyncio
import os

from glide import GlideClient, GlideClientConfiguration, NodeAddress, ft


async def check_connection() -> None:
    config = GlideClientConfiguration(
        addresses=[
            NodeAddress(
                os.environ.get("VALKEY_HOST", "localhost"),
                int(os.environ.get("VALKEY_PORT", "6379")),
            )
        ],
        client_name="langbot_healthcheck",
        # GLIDE defaults to a 250ms request timeout, which causes spurious
        # failures off localhost. 5s is a safe cookbook default — tune it down
        # for a real-time chat pipeline (LangBot's limiter uses 500ms).
        request_timeout=5000,
    )
    client = await GlideClient.create(config)
    try:
        pong = await client.ping()
        print(f"Valkey says: {pong!r}")  # b"PONG"

        # ft.list confirms the search module is loaded (needed for vector search).
        indexes = await ft.list(client)
        print(f"Search module loaded — {len(indexes)} index(es) found")
        print("Connected successfully!")
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(check_connection())
    except Exception as exc:  # noqa: BLE001 — surface a friendly hint
        print(f"Connection failed: {exc}")
        print("Is Valkey running? Try: docker run -d -p 6379:6379 valkey/valkey-bundle:latest")
```

If `ft.list` raises an "unknown command" error, you are connected to a plain Valkey without the search module — restart with the `valkey-bundle` image from Step 1.

## Step 4: Enable the Backends in LangBot

Both backends are off by default, so existing deployments are unaffected until you opt in.

### Rate limiting (pipeline config)

Select the `valkey_fixwin` algorithm in the pipeline safety config and point it at your Valkey. The connection settings live in the top-level `valkey:` block of LangBot's instance config:

```yaml
# Top-level instance config — shared Valkey connection for the limiter
valkey:
  host: 'localhost'
  port: 6379
  db: 0
  password: ''            # optional; only sent when set, never logged
  tls: false              # set true (and use a password) for non-local hosts
  key_prefix: 'langbot:ratelimit:fixwin'  # namespace so deployments don't collide
  fail_strategy: 'open'   # 'open' = allow on Valkey error (default); 'closed' = deny
```

```yaml
# Pipeline safety config — choose the distributed algorithm
safety:
  rate-limit:
    algo: 'valkey_fixwin'   # default is the in-memory 'fixwin'
    strategy: 'drop'        # 'drop' or 'wait' when over the limit
    window-length: 60       # fixed window size in seconds
    limitation: 60          # max requests allowed per window
```

When `algo` is unset, LangBot falls back to the in-memory `fixwin`, preserving current behavior.

### Vector search (knowledge-base config)

Set `vdb.use` to `valkey_search` and add the connection block in `config.yaml`:

```yaml
vdb:
  use: valkey_search       # default is 'chroma'
  valkey_search:
    host: 'localhost'
    port: 6379
    db: 0
    username: ''           # optional ACL user
    password: ''           # optional; never logged
    tls: false             # optional (toB / SaaS)
    index_algorithm: 'HNSW'   # HNSW (approximate) | FLAT (exact)
    distance_metric: 'COSINE' # COSINE | L2 | IP
```

## How It Works Under the Hood

| Integration | LangBot component | Valkey features used |
|-------------|-------------------|----------------------|
| Rate limiting | `valkey_fixwin` pipeline algorithm | `EVAL` (Lua), `INCR`, `EXPIRE` |
| Vector search | `valkey_search` VDB backend | `FT.CREATE`, `FT.SEARCH`, `HSET`, `SCAN` |

Both create the `valkey-glide` client lazily (`lazy_connect=True`), so a misconfigured or down Valkey never blocks LangBot from booting — errors surface at call time instead.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `pip install 'valkey-glide>=2.4.1,<3.0.0'` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `unknown command 'FT.CREATE'` / `ft.list` fails | Use the `valkey/valkey-bundle:latest` image (includes the search module) |
| `NOAUTH Authentication required` | Set `password` in the relevant config block |
| Timeouts when Valkey is remote | Raise `request_timeout` to account for network latency |

[Next: 02 Distributed Rate Limiting →](02-distributed-rate-limiting.md)
