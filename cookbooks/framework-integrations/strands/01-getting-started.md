# Getting Started with Strands + Valkey

> Use the `strands-valkey-session-manager` community package to give your Strands agent persistent conversation history, session records, and agent state backed by Valkey.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building Strands agents who need
Valkey-backed conversation history and session state.

Strands agents are stateless by default. Without a session manager, every
conversation starts from scratch. Valkey stores the full conversation history,
agent state, and tool results so your agent remembers context across requests
and can resume interrupted workflows.

The `strands-valkey-session-manager` package provides a ready-to-use `ValkeySessionManager` that plugs directly into Strands' `Agent(session_manager=...)` parameter. No custom implementation is needed.

## What Gets Stored

The session manager persists three types of data to Valkey:

| Data | Key Pattern | Description |
| --- | --- | --- |
| Session Record | `session:{id}` | Top-level record for a conversation. Stores the session type and creation/update timestamps. |
| Agent State | `session:{id}:agent:{agent_id}` | Per-agent record containing user state, conversation-manager state, and internal state such as interrupt state. |
| Conversation Messages | `session:{id}:agent:{agent_id}:message:{message_id}` | A serialized `SessionMessage` containing the nested message, numeric message ID, optional redaction, and creation/update timestamps. |

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- Valkey 8.1+ with the JSON module (use `valkey/valkey-bundle` for local development)
- The pinned dependencies in [`sample/requirements.txt`](sample/requirements.txt)
- Enough local disk and memory for the `llama3.2:1b` Ollama model

## Step 1: Start Valkey

```bash
docker compose -f sample/docker-compose.yml up -d --wait
docker compose -f sample/docker-compose.yml exec -T ollama ollama pull "${OLLAMA_MODEL:-llama3.2:1b}"
```

> **Security:** This local example uses no authentication or TLS. For any non-localhost deployment, configure authentication and TLS; see the [Valkey security documentation](https://valkey.io/topics/security/).

```bash
docker compose -f sample/docker-compose.yml exec -T valkey valkey-cli PING
# PONG
```

Use `podman compose` instead of `docker compose` when Podman is your container runtime.

## Step 2: Install Dependencies

```bash
cd sample
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..
```

**Package:** `strands-valkey-session-manager` is a community package. Source: [GitHub](https://github.com/jeromevdl/strands-valkey-session-manager) - Docs: [strandsagents.com](https://strandsagents.com/docs/community/session-managers/strands-valkey-session-manager/)

## Step 3: Connect to Valkey

```python
import os

import valkey
from strands_valkey_session_manager import ValkeySessionManager

# Connect to Valkey
client = valkey.Valkey(
    host=os.getenv("VALKEY_HOST", "localhost"),
    port=int(os.getenv("VALKEY_PORT", "6379")),
    decode_responses=True,
)

# Create the session manager - one per session
session_manager = ValkeySessionManager(
    session_id="user-42",
    client=client,
)
```

## Step 4: Run the Ollama Agent

The sample uses `OllamaModel` and the local `llama3.2:1b` model by default. The
model generates the response, while the session manager persists the user and
assistant messages:

```bash
cd sample
.venv/bin/python demo.py
```

The output includes the number of persisted messages and the resumed response.

## Optional: Use Another Model Provider

When you have configured a supported Strands model provider, the same session
manager plugs directly into `Agent`:

```python
from strands import Agent

agent = Agent(system_prompt="You are a helpful assistant.", session_manager=session_manager)

# Strands automatically persists every turn to Valkey
response = agent("My name is Alex and I'm building a RAG pipeline.")
print(response)
```

## How It Works

| Component | Role |
| --- | --- |
| `Agent` | Runs the Strands conversation and emits session events. |
| `ValkeySessionManager` | Translates session events into persistent session, agent, and message records. |
| Valkey JSON | Stores the structured records used for resume and inspection. |

## Configuration Reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname. |
| `VALKEY_PORT` | No | `6379` | Valkey server port. |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_MODEL` | No | `llama3.2:1b` | Ollama model tag. |

## Teardown

Run the sample's cleanup test and stop the local service:

```bash
cd sample
.venv/bin/python -m pytest -q
docker compose down -v
cd ..
```

---

[02 - Managing Session Data →](02-session-internals.md)
