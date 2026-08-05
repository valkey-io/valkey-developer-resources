# Getting Started with LangBot + Valkey

> Start Valkey with the search module, verify the connection with `valkey-glide`, and enable LangBot's opt-in Valkey Search knowledge-base backend.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers running LangBot who want to back its RAG knowledge base with Valkey Search instead of the default
Chroma store, or anyone learning how valkey-glide's typed `ft` search API works.

## What is LangBot + Valkey?

[LangBot](https://github.com/langbot-app/LangBot) is an open-source, production-grade platform for building agentic IM bots across
Discord, Slack, Telegram, WeChat, Lark, DingTalk, QQ, and Matrix. It ships agent orchestration, a knowledge base (RAG), a plugin system,
and a configurable message pipeline.

Valkey plugs into LangBot's knowledge base as an **opt-in, disabled-by-default** `valkey_search` backend: it stores embeddings in Valkey
Search and serves vector, full-text, and hybrid queries, talking to Valkey through the official
[`valkey-glide`](https://github.com/valkey-io/valkey-glide) client (Rust core + async Python bindings).

## Prerequisites

- Python 3.10+
- Docker or Podman (for running Valkey)
- `valkey-glide==2.5.0` — installed in [Step 2](#step-2-install-the-valkey-client)

## Step 1: Start Valkey with the Search Module

The vector-search backend needs the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image ships it (along with JSON and other modules):

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0
```

```bash
# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify it is running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

## Step 2: Install the Valkey Client

LangBot keeps `valkey-glide` as an optional dependency for this backend (it's behind an import guard), so install it explicitly:

```bash
pip install valkey-glide==2.5.0
```

The typed search API (`ft.create`, `ft.search`) that the vector backend relies on has been available since `valkey-glide` 2.4.1.

## Step 3: Verify the Connection

This snippet connects, pings, and lists search indexes to confirm the module is present. It wraps the client in `try/finally` so the connection is always closed.

```python
"""Quick connectivity check for LangBot's Valkey Search backend."""
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
        # for a real-time chat pipeline.
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
        print("Is Valkey running? Try: docker run -d -p 6379:6379 valkey/valkey-bundle:9.1.0")
```

If `ft.list` raises an "unknown command" error, you are connected to a plain Valkey without the search module — restart with the `valkey-bundle` image from Step 1.

## Step 4: Enable the Backend in LangBot

The backend is off by default, so existing deployments are unaffected until you opt in. Set `vdb.use` to `valkey_search` and add the connection block in `config.yaml`:

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
    request_timeout: 5000     # ms; glide's own default (250ms) is too low for KNN
```

## How It Works Under the Hood

| Component | Valkey features used |
|-----------|----------------------|
| `valkey_search` VDB backend | `FT.CREATE`, `FT.SEARCH`, `HSET`, `SCAN` |

The backend creates its `valkey-glide` client lazily (`lazy_connect=True`), so a misconfigured or down Valkey never blocks LangBot from booting — errors surface at call time instead.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `pip install valkey-glide==2.5.0` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `unknown command 'FT.CREATE'` / `ft.list` fails | Use the `valkey/valkey-bundle:9.1.0` image (includes the search module) |
| `NOAUTH Authentication required` | Set `password` in the `valkey_search` config block |
| Timeouts when Valkey is remote | Raise `request_timeout` to account for network latency |

---

[Next: 02 Vector Search →](02-vector-search.md)
