# Getting Started

> Connect an Agno agent to Valkey for persistent session storage — conversations survive restarts with zero LLM cost.

**Beginner** · Python · ~10 min

**Who is this for:** Python developers who want to add persistent session storage to
Agno agents without setting up a full database — Valkey gives you fast key-value storage
with secondary indexes out of the box.

## How Agno Storage Works

Agno agents store session data (conversation history, memories, metrics) in a pluggable
storage backend. `ValkeyDb` implements the `BaseDb` interface using Valkey STRING keys
(JSON-serialized sessions) with secondary index sets for filtered lookups.

```text
Agent.print_response("Hello") → ValkeyDb.upsert_session(session) → SET agno:sessions:{id} <json>
Agent.print_response("Follow-up") → reads history from Valkey → context-aware response
```

## Prerequisites

- Docker or Podman installed
- Python 3.10+
- One of:
  - [Ollama](https://ollama.com/) running locally (`ollama pull llama3.2`), OR
  - `OPENAI_API_KEY` environment variable set (Agno's default model is OpenAI)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> ⚠️ **Security:** This example uses no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify it's running:

```bash
docker exec valkey valkey-cli ping
# Expected: PONG
```

## Step 2: Install Dependencies

```bash
pip install "agno[valkey,ollama]==2.8.0"
```

This installs the Agno framework with the Valkey storage adapter (`valkey-glide-sync`) and Ollama model support.

## Step 3: Create an Agent with Valkey Storage

By default, Agno uses OpenAI as the model provider. To use a free local model instead,
pass `model=Ollama(id="llama3.2")`.

**Option A — Ollama (free, local, no API key):**

```python
from agno.agent import Agent
from agno.db.valkey import ValkeyDb
from agno.models.ollama import Ollama

db = ValkeyDb()

agent = Agent(
    model=Ollama(id="llama3.2"),
    db=db,
    add_history_to_context=True,
)
```

**Option B — OpenAI (default, requires `OPENAI_API_KEY`):**

```python
from agno.agent import Agent
from agno.db.valkey import ValkeyDb

db = ValkeyDb()

# OpenAI is the default model — just set OPENAI_API_KEY in your environment
agent = Agent(
    db=db,
    add_history_to_context=True,
)
```

## Step 4: Verify Persistence

```python
from agno.db.base import SessionType

# First interaction
agent.print_response("My name is Alice")

# Second interaction — agent remembers context
agent.print_response("What is my name?")

# Check stored sessions
all_sessions = db.get_sessions(session_type=SessionType.AGENT)
print(f"Sessions in Valkey: {len(all_sessions)}")
```

Run this script, then run it again — the sessions persist across executions because
they're stored in Valkey, not in-memory.

## Step 5: Inspect Data in Valkey

```bash
docker exec valkey valkey-cli KEYS "agno:*" | head -5
```

Each session is stored as a STRING key containing JSON-serialized session data,
with secondary index sets for filtered lookups.

## How It Works

| Component | Role |
| --------- | ---- |
| `ValkeyDb()` | Agno storage adapter — implements `BaseDb` interface |
| `valkey-glide-sync` | Valkey client library (sync API) |
| Valkey STRING keys | One per session, keyed by `agno:sessions:{session_id}` |
| Secondary index sets | Enable filtered lookups by `user_id`, `agent_id`, etc. |
| `CLIENT SETNAME` | Connection named `agno_db_client` for observability |

## Configuration Reference

| Field | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `host` | No | `localhost` | Valkey hostname |
| `port` | No | `6379` | Valkey port |
| `username` | No | — | Auth username |
| `password` | No | — | Auth password |
| `use_tls` | No | `False` | Enable TLS |
| `database_id` | No | `0` | Logical database index |
| `expire` | No | — | Key TTL in seconds |

## Cleanup

```bash
docker stop valkey && docker rm valkey
```

---

[← README](README.md) | [02 - Knowledge Base →](02-knowledge-base.md)
