# Getting Started

> Connect a PraisonAI agent to Valkey and verify that session state persists across restarts.

**Beginner** · Python · ~10 min

**Who is this for:** Python developers new to PraisonAI who want to understand how Valkey integrates as a persistence backend before diving into agent state and vector search.

## How It Works

PraisonAI ships two pluggable persistence adapters built on `valkey-glide-sync`:

| Component | Role |
| --- | --- |
| `ValkeyStateStore` | Key-value layer: session history, counters, metadata (`SET`/`GET`/`HSET`/`EXPIRE`) |
| `ValkeyVectorKnowledgeStore` | Vector index: semantic similarity search (`FT.CREATE`/`FT.SEARCH`/`HSET`) |
| `valkey-glide-sync` | Underlying Valkey client (installed via `praisonai[valkey]`) |

Both adapters accept `host`, `port`, `password`, and `prefix` arguments so you can connect to local or managed Valkey instances without changing application code.

## Configuration Reference

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | No | `localhost` | Valkey server hostname. Override with `VALKEY_HOST` env var. |
| `port` | No | `6379` | Valkey server port. Override with `VALKEY_PORT` env var. |
| `password` | No | `None` | Valkey password for authenticated instances. Override with `VALKEY_PASSWORD` env var. |
| `prefix` | No | `"praison:"` | Key namespace prefix. Use different prefixes to isolate agents on the same Valkey instance. |

## Prerequisites

- Docker or Podman installed
- Python 3.10+
- One of:
  - [Ollama](https://ollama.com/) running locally (`ollama pull llama3.2`), OR
  - `OPENAI_API_KEY` environment variable set

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).
>
> **Note:** Substitute `podman` for `docker` if Podman is your container runtime — the commands are identical.

Verify it's running:

```bash
docker exec valkey valkey-cli ping
# Expected: PONG
```

## Step 2: Install Dependencies

```bash
pip install "praisonai[valkey]==4.6.157"
```

This installs PraisonAI with the Valkey persistence extras (`valkey-glide-sync`).

## Step 3: Connect the State Store

Create `hello_valkey.py`:

```python
import os
from praisonai.persistence.state.valkey import ValkeyStateStore

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD") or None

store = ValkeyStateStore(
    host=VALKEY_HOST,
    port=VALKEY_PORT,
    password=VALKEY_PASSWORD,
    prefix="praisonai:hello:",
)

# Write and read a value
store.set("greeting", "Hello from PraisonAI!")
value = store.get("greeting")
print(value)
# Expected: Hello from PraisonAI!

store.close()
```

Run it:

```bash
python hello_valkey.py
# Hello from PraisonAI!
```

## Step 4: Verify Data in Valkey

```bash
valkey-cli KEYS "praisonai:hello:*"
# praisonai:hello:greeting

valkey-cli GET "praisonai:hello:greeting"
# "Hello from PraisonAI!"
```

## Step 5: Teardown

```bash
docker rm -f valkey
```

This removes the container and its data. Run this when you are done experimenting.

## What's Next

You now have a working PraisonAI ↔ Valkey connection. The next cookbooks show
how to use this for persistent agent history and vector knowledge retrieval.

---

[← README](README.md) | [Next: 02 Agent State Persistence →](02-agent-state.md)
