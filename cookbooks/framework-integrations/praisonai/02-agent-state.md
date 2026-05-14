# Agent State Persistence with PraisonAI + Valkey

**Intermediate** · Python · ~20 min

## What We're Building

A PraisonAI agent that stores its session history in Valkey. On every run, the agent loads prior conversation turns from Valkey, includes them as context in its next prompt, and writes the new exchange back. State survives across script restarts.

## Prerequisites

- Valkey running on `localhost:6379` (see [01 Getting Started](01-getting-started.md))
- `praisonai[valkey]` and `openai` installed
- `OPENAI_API_KEY` set in your environment

## How It Works

`ValkeyStateStore` is used as a lightweight key-value layer alongside the agent:

1. **Load** prior turns from Valkey at the start of each run
2. **Build** a context-aware prompt that includes the history
3. **Run** the agent with `agent.start(prompt)`
4. **Save** the new exchange back to Valkey

This keeps the agent stateless while Valkey provides the durable memory.

## Full Example

```python
import os
from praisonaiagents import Agent
from praisonai.persistence.state.valkey import ValkeyStateStore

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD") or None

store = ValkeyStateStore(
    host=VALKEY_HOST,
    port=VALKEY_PORT,
    password=VALKEY_PASSWORD,
    prefix="praisonai:research-agent:",
)

agent = Agent(
    instructions="You are a concise research assistant. Answer in 1-2 sentences.",
)


def chat(user_message: str) -> str:
    """Send a message to the agent, with prior history injected as context."""
    # Load history from Valkey
    history = store.get("history") or []
    run_count = store.incr("run_count")

    # Build prompt with prior context
    if history:
        context = "\n".join(
            f"{t['role'].upper()}: {t['content']}" for t in history[-6:]  # last 3 turns
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

    return str(response)


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

## Running It

```bash
export OPENAI_API_KEY=sk-...
python 02_agent_state.py
```

Run it again — the agent picks up where it left off because history is loaded from Valkey at the start of each run.

## TTL: Auto-expiring Sessions

```python
# Keep session history for 24 hours
store.set("history", history)
store.expire("history", ttl=86400)
```

## Key Design Decisions

**Prefix per agent** — `prefix="praisonai:research-agent:"` namespaces all keys for this agent. Different agents use different prefixes on the same Valkey instance without collisions.

**JSON serialisation** — `ValkeyStateStore.set()` serialises Python dicts and lists to JSON automatically. `get()` deserialises on read.

**Atomic counters** — `store.incr("run_count")` maps to Valkey's `INCRBY`, which is atomic and safe under concurrent access.

[← 01 Getting Started](01-getting-started.md) | [Next: 03 Vector Knowledge Retrieval →](03-vector-knowledge.md)
