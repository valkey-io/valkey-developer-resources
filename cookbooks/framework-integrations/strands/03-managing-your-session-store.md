# Managing Your ValkeySession Store

> Delete sessions on logout, query raw keys to see exactly what's in Valkey, and share a single session across multiple agents in an orchestrator pattern.

**Intermediate** · Python · ~15 min

**Who is this for:** Developers coordinating multiple Strands agents that need
shared session history and explicit cleanup.

## Prerequisites

- Python 3.10 or newer
- Valkey 8.1+ with the JSON module (use `valkey/valkey-bundle` for local development)
- Docker or Podman with the sample Valkey service running
- The sample Ollama service with `llama3.2:1b` pulled
- The pinned dependencies in [`sample/requirements.txt`](sample/requirements.txt)

## Step 1: Share a Session Across Multiple Agents

A single session can hold state for multiple agents - each gets its own agent
key and message keys under the same session ID. This is the foundation for
orchestrator/subagent patterns where agents need to share context:

```python
import os

from strands import Agent
from strands.models.ollama import OllamaModel
from strands_valkey_session_manager import ValkeySessionManager
import valkey

client = valkey.Valkey(
    host=os.getenv("VALKEY_HOST", "localhost"),
    port=int(os.getenv("VALKEY_PORT", "6379")),
    decode_responses=True,
)
model = OllamaModel(
    host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    model_id=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
)

# Two agents sharing the same session_id
researcher = Agent(
    system_prompt="You are a research agent.",
    model=model,
    agent_id="researcher",
    session_manager=ValkeySessionManager(
        session_id="workflow-001", client=client
    ),
)
writer = Agent(
    system_prompt="You are a writing agent.",
    model=model,
    agent_id="writer",
    session_manager=ValkeySessionManager(
        session_id="workflow-001", client=client
    ),
)

researcher("Research the key benefits of Valkey for AI workloads.")
writer("Write a short blog intro about Valkey for AI.")

# Each agent has its own message keys under the same session
# session:workflow-001:agent:researcher:message:0
# session:workflow-001:agent:writer:message:0
```

Both agents use the same local Ollama model and share the session ID while
keeping separate agent state and message histories.

## Step 2: Clean Up on Logout

Call `delete_session()` to remove all keys for a session - the session record, agent state, and every message - in one call:

```python
import os

import valkey
from strands_valkey_session_manager import ValkeySessionManager

client = valkey.Valkey(
    host=os.getenv("VALKEY_HOST", "localhost"),
    port=int(os.getenv("VALKEY_PORT", "6379")),
    decode_responses=True,
)
sm = ValkeySessionManager(session_id="user-42", client=client)

# Removes session, agent state, and all messages for this session
sm.delete_session("user-42")
print("Session deleted")
```

## Step 3: Query Valkey Directly

Raw key inspection is a diagnostic technique. Use the session-manager API for
normal reads and cleanup:

```python
# List all keys for a session with their TTLs
keys = client.keys("session:user-42*")
for k in sorted(keys):
    ttl = client.ttl(k)
    print(f"{k}  (TTL: {ttl}s)")

# Each line reports the current server TTL; -1 means no expiry is configured.
# Example keys:
# session:user-42
# session:user-42:agent:default
# session:user-42:agent:default:message:0
```

> **Production note:** Set a TTL on every key belonging to a session to
> prevent unbounded growth. The session manager stores the session record,
> agent state, and each message as separate keys, so expire all matching keys
> and refresh them when the session is active:
>
> ```python
> for key in client.scan_iter(match="session:user-42*"):
>     client.expire(key, 86400)
> ```

## Configuration Reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname. |
| `VALKEY_PORT` | No | `6379` | Valkey server port. |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_MODEL` | No | `llama3.2:1b` | Ollama model tag. |

## Teardown

Run the sample test suite to verify cleanup, then stop the service:

```bash
cd sample
.venv/bin/python -m pytest -q
docker compose down -v
cd ..
```

---

[← 02 - Managing Session Data](02-session-internals.md)
