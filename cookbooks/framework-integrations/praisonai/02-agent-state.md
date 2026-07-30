# Agent State Persistence

> Store conversation history in Valkey so a PraisonAI agent picks up where it left off across restarts.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who want PraisonAI agents to remember prior exchanges without a database.
Valkey provides atomic counters, JSON serialization, and optional TTL out of the box.

## What We're Building

A PraisonAI agent that stores its session history in Valkey. On every run, the agent loads prior
conversation turns from Valkey, includes them as context in its next prompt, and writes the new
exchange back. State survives across script restarts.

## Prerequisites

- Valkey running on `localhost:6379` (see [01 Getting Started](01-getting-started.md))
- `praisonai[valkey]` installed (see Step 2 in cookbook 01)
- `OPENAI_API_KEY` set, or Ollama running locally

## How `ValkeyStateStore` Works

`ValkeyStateStore` is a thin key-value layer over `valkey-glide-sync`:

| Method | Valkey Command | Use |
| --- | --- | --- |
| `store.set(key, value)` | `SET` (JSON-encoded) | Write any Python dict or list |
| `store.get(key)` | `GET` (JSON-decoded) | Read back as Python object |
| `store.incr(key)` | `INCRBY 1` | Atomic counter |
| `store.hset(key, field, value)` | `HSET` (JSON-encoded) | Hash field write |
| `store.hgetall(key)` | `HGETALL` (JSON-decoded) | Read all hash fields as dict |
| `store.expire(key, ttl)` | `EXPIRE` | Set TTL in seconds |

## Configuration Reference

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | No | `localhost` | Valkey server hostname. Override with `VALKEY_HOST` env var. |
| `port` | No | `6379` | Valkey server port. Override with `VALKEY_PORT` env var. |
| `password` | No | `None` | Valkey password for authenticated instances. Override with `VALKEY_PASSWORD` env var. |
| `prefix` | No | `"praison:"` | Key namespace prefix. Use different prefixes to isolate agents on the same instance. |

## Step 1: Set Up the State Store

```python
import os
from praisonai.persistence.state.valkey import ValkeyStateStore

store = ValkeyStateStore(
    host=os.environ.get("VALKEY_HOST", "localhost"),
    port=int(os.environ.get("VALKEY_PORT", "6379")),
    password=os.environ.get("VALKEY_PASSWORD") or None,
    prefix="praisonai:research-agent:",
)
```

## Step 2: Create a Context-Aware Agent

**Option A — Ollama (free, local, no API key):**

```python
from praisonaiagents import Agent

agent = Agent(
    instructions="You are a concise research assistant. Answer in 1-2 sentences.",
    llm="ollama/llama3.2",  # free, local — run: ollama pull llama3.2
)
```

**Option B — OpenAI (requires `OPENAI_API_KEY`):**

```python
from praisonaiagents import Agent

agent = Agent(
    instructions="You are a concise research assistant. Answer in 1-2 sentences.",
)
```

## Step 3: Load History, Run Agent, Persist Result

```python
def chat(user_message: str) -> str:
    """Send a message to the agent, with prior history injected as context."""
    # Load history from Valkey
    history = store.get("history") or []
    run_count = store.incr("run_count")

    # Build prompt with prior context (last 3 turns = 6 messages)
    if history:
        context = "\n".join(
            f"{t['role'].upper()}: {t['content']}" for t in history[-6:]
        )
        prompt = f"Previous conversation:\n{context}\n\nUser: {user_message}"
    else:
        prompt = user_message

    # Run the agent
    response = agent.start(prompt)

    # Persist the new exchange
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": str(response)})
    store.set("history", history)
    store.hset("meta", "last_query", user_message)
    store.hset("meta", "run_count", str(run_count))
    # Note: hset JSON-encodes values just like set(). str(run_count) round-trips
    # as the integer run_count when read back via hgetall() — this is expected.

    return str(response)
```

## Step 4: Run It

```python
if __name__ == "__main__":
    try:
        queries = [
            "What is Valkey?",
            "How is it different from Redis?",
            "What client library should I use?",
        ]
        for q in queries:
            print(f"\nUser: {q}")
            response = chat(q)
            print(f"Agent: {response}")

        print("\n--- Persisted state ---")
        print(f"Run count : {store.get('run_count')}")
        print(f"Metadata  : {store.hgetall('meta')}")
        history = store.get("history") or []
        print(f"History   : {len(history)} messages stored in Valkey")
    finally:
        store.close()
```

Run it again — the agent picks up where it left off because history is loaded from Valkey at the start of each run.

## TTL: Auto-expiring Sessions

```python
# Keep session history for 24 hours
store.set("history", history)
store.expire("history", ttl=86400)
```

## Connection Lifecycle

Always call `store.close()` when your script finishes. `ValkeyStateStore` holds
a `valkey-glide-sync` client that keeps an open connection pool — not closing it
causes the process to hang until the OS reclaims resources.

```python
store = ValkeyStateStore(...)
try:
    # ... use the store
finally:
    store.close()
```

## Key Design Decisions

**Prefix per agent** — `prefix="praisonai:research-agent:"` namespaces all keys for this agent. Different agents use different prefixes on the same Valkey instance without collisions.

**JSON serialization** — `ValkeyStateStore.set()` serializes Python dicts and lists to JSON automatically. `get()` deserializes on read.

**Atomic counters** — `store.incr("run_count")` maps to Valkey's `INCRBY`, which is atomic and safe under concurrent access.

---

[← 01 Getting Started](01-getting-started.md) | [Next: 03 Vector Knowledge Retrieval →](03-vector-knowledge.md)
