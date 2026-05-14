# Getting Started with PraisonAI + Valkey

**Beginner** · Python · ~10 min

## What is PraisonAI + Valkey?

PraisonAI is a multi-agent orchestration framework built around OpenAI-compatible LLMs. Out of the box, agent state and knowledge are ephemeral — they vanish when your script exits. Valkey gives agents durable, fast storage so that session history, counters, and document embeddings survive across runs.

[PraisonAI](https://docs.praison.ai/) handles the agent logic and Valkey handles the memory:

- **Blazing-fast reads** — state recall via GLIDE's Rust core
- **Vector search** — `FT.SEARCH` with HNSW for semantic knowledge retrieval
- **Hash storage** — structured agent metadata in Valkey hashes
- **TTL** — state entries auto-expire with `EXPIRE`

## Step 1: Start Valkey

Docker and Python 3.10+ required.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes the ValkeySearch module needed for vector search. Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Dependencies

```bash
pip install 'praisonai[valkey]' openai
```

The `valkey` extra installs `valkey-glide-sync`, the official synchronous Valkey client with a Rust core.

## Step 3: Configure the Connection

```python
import os

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD") or None
```

## Step 4: Verify Connectivity

```python
from praisonai.persistence.state.valkey import ValkeyStateStore

store = ValkeyStateStore(
    host=VALKEY_HOST,
    port=VALKEY_PORT,
    password=VALKEY_PASSWORD,
    prefix="praisonai:demo:",
)

store.set("hello", "valkey")
print(store.get("hello"))   # valkey
store.delete("hello")
store.close()
print("✅ Connected!")
```

## How It Works Under the Hood

| Operation | Valkey Command | Latency |
|---|---|---|
| Store state | `SET praisonai:demo:hello "valkey"` | ~0.1 ms |
| Read state | `GET praisonai:demo:hello` | ~0.1 ms |
| Hash field | `HSET praisonai:demo:meta version 1` | ~0.1 ms |
| Vector index (later) | `FT.CREATE ... VECTOR HNSW` | one-time |
| Semantic search (later) | `FT.SEARCH ... [KNN 5 @embedding $vec]` | ~1–3 ms |

Connection works. Next, we'll wire `ValkeyStateStore` into a PraisonAI agent so state persists across runs.

[Next: 02 Agent State Persistence →](02-agent-state.md)
