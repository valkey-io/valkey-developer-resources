# Managing Session Data

> Understand exactly what strands-valkey-session-manager stores in Valkey - the key structure, the shape of each object, and how to use the built-in API methods to inspect and manage session data.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers who need to inspect and resume Strands session state stored in Valkey.

## Prerequisites

- Python 3.11
- Docker or Podman with the sample Valkey service running
- The sample Ollama service with `llama3.2:1b` pulled
- The pinned dependencies in [`sample/requirements.txt`](sample/requirements.txt)

## Step 1: Understand What Gets Stored

### Session Record

One record per conversation. Stores the session type and when the session was
created and last updated. This is a representative `Session.to_dict()` result:

```json
{
  "session_id": "user-42",
  "session_type": "AGENT",
  "created_at": "2026-07-20T10:00:00+00:00",
  "updated_at": "2026-07-20T10:05:32+00:00"
}
```

### Agent State

One record per agent within a session. It stores user-managed state,
conversation-manager state, internal state, and timestamps. This is a
representative `SessionAgent.to_dict()` result:

```json
{
  "agent_id": "default",
  "state": {},
  "conversation_manager_state": {
    "__name__": "SlidingWindowConversationManager",
    "removed_message_count": 0,
    "model_call_count": 0
  },
  "_internal_state": {
    "interrupt_state": {
      "interrupts": {},
      "context": {},
      "activated": false
    },
    "model_state": {}
  },
  "created_at": "2026-07-20T10:00:00+00:00",
  "updated_at": "2026-07-20T10:05:32+00:00"
}
```

### Conversation Messages

One record per turn. The serialized `SessionMessage` nests the Strands
message and also stores its numeric ID, optional redaction, and timestamps.

```json
{
  "message": {
    "role": "user",
    "content": [
      {"text": "My name is Alex and I'm building a RAG pipeline."}
    ],
    "tracking_id": "..."
  },
  "message_id": 0,
  "redact_message": null,
  "created_at": "2026-07-20T10:00:01+00:00",
  "updated_at": "2026-07-20T10:00:01+00:00"
}
```

Assistant message with tool use:

```json
{
  "message": {
    "role": "assistant",
    "content": [
      {"text": "Nice to meet you, Alex! ..."},
      {"toolUse": {"toolUseId": "...", "name": "search", "input": {"query": "RAG pipeline"}}}
    ],
    "tracking_id": "..."
  },
  "message_id": 1,
  "redact_message": null,
  "created_at": "2026-07-20T10:00:03+00:00",
  "updated_at": "2026-07-20T10:00:03+00:00"
}
```

## Step 2: Pick Up Where You Left Off

Create a new `Agent` with the same `session_id` - Strands reloads the full conversation history from Valkey automatically:

```python
import os

import valkey
from strands import Agent
from strands.models.ollama import OllamaModel
from strands_valkey_session_manager import ValkeySessionManager

# In a new Python process - history is restored from Valkey
client = valkey.Valkey(
    host=os.getenv("VALKEY_HOST", "localhost"),
    port=int(os.getenv("VALKEY_PORT", "6379")),
    decode_responses=True,
)
session_manager = ValkeySessionManager(
    session_id="user-42",  # same session ID
    client=client,
)
agent = Agent(
    model=OllamaModel(
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model_id=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
    ),
    session_manager=session_manager,
)

response = agent("What was I just telling you about?")
print(response)
```

The default sample uses Ollama. Pull the model and run it from the sample
directory:

```bash
cd sample
docker compose exec -T ollama ollama pull "${OLLAMA_MODEL:-llama3.2:1b}"
.venv/bin/python demo.py
cd ..
```

## Step 3: See What Got Saved

```python
# List all messages for the agent in this session
messages = session_manager.list_messages("user-42", "default")
for msg in messages:
    message = msg.to_message()
    preview = str(message["content"])[:80]
    print(f"[{message['role']}] {preview}")

# Raw key inspection is useful for diagnostics only.
keys = client.keys("session:user-42*")
for k in sorted(keys):
    print(k)
```

## Step 4: Read and Update Session Data

The `ValkeySessionManager` exposes methods for all CRUD operations. You don't need to touch Valkey directly for most tasks:

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

# Read the session record
session = sm.read_session("user-42")
if session:
    print(f"Created: {session.created_at}")

# Read agent state
agent_state = sm.read_agent("user-42", "default")
if agent_state:
    print(f"Message count: {agent_state.conversation_manager_state}")

# List all messages in order
messages = sm.list_messages("user-42", "default")
print(f"{len(messages)} messages in session")
for msg in messages:
    text_blocks = [b["text"] for b in msg.to_message()["content"] if "text" in b]
    preview = text_blocks[0][:80] if text_blocks else "[tool use/result]"
    print(f"  [{msg.to_message()['role']:9}] {preview}")
```

## Full API Reference

| Method | Description |
| --- | --- |
| `create_session(session: Session)` | Create a new session record |
| `read_session(session_id)` | Read the session record |
| `delete_session(session_id)` | Delete a session and all its data |
| `create_agent(session_id, session_agent: SessionAgent)` | Create agent state record |
| `read_agent(session_id, agent_id)` | Read agent state |
| `update_agent(session_id, session_agent: SessionAgent)` | Update agent state |
| `create_message(session_id, agent_id, session_message: SessionMessage)` | Store a new message |
| `read_message(session_id, agent_id, message_id)` | Read a single message by ID |
| `update_message(session_id, agent_id, session_message: SessionMessage)` | Update an existing message |
| `list_messages(session_id, agent_id, limit=None, offset=0)` | List messages for one agent in session order |

## How Keys Are Organized

The package uses a hierarchical key scheme. Every key is scoped to a session ID:

```text
session:{session_id}                                         # Session record
session:{session_id}:agent:{agent_id}                        # Agent state
session:{session_id}:agent:{agent_id}:message:{message_id}   # Individual messages; message_id is numeric
```

## Configuration Reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname. |
| `VALKEY_PORT` | No | `6379` | Valkey server port. |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL. |
| `OLLAMA_MODEL` | No | `llama3.2:1b` | Ollama model tag. |

## Teardown

Use the integration API to delete all data for the session:

```python
session_manager.delete_session("user-42")
```

For the complete local cleanup flow:

```bash
cd sample
.venv/bin/python -m pytest -q
docker compose down -v
cd ..
```

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Managing Your Session Store →](03-managing-your-session-store.md)
