# Multi-User Memory with Mem0 + Valkey

> Scope Mem0 memories by user, agent, and session so searches return only the intended records.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers building multi-tenant agents that must keep user and agent memories separate.

## Prerequisites

- Docker or Podman
- Python 3.9 or newer
- The dependencies and local Valkey instance from [Getting Started](01-getting-started.md)

## Step 1: Create a Mem0 Store

Use the same provider configuration as the first cookbook with a collection dedicated to this application:

```python
from mem0 import Memory

memory = Memory.from_config(
    {
        "vector_store": {
            "provider": "valkey",
            "config": {
                "valkey_url": "valkey://localhost:6379?socket_timeout=5",
                "collection_name": "multi_user_app",
                "embedding_model_dims": 10,
                "index_type": "hnsw",
            }
        },
        "llm": {
            "provider": "openai",
            "config": {
                "api_key": "unused-with-infer-false",
                "model": "gpt-4o-mini",
            },
        },
    }
)
```

For a no-credential local run, assign Mem0's `MockEmbeddings` instance as shown in [Getting Started](01-getting-started.md) and pass `infer=False` to `add`.

## Step 2: Add User Memories

Pass a `user_id` to associate each memory with a user:

```python
memory.add(
    [{"role": "user", "content": "Alice prefers Python."}],
    user_id="alice",
    infer=False,
)
memory.add(
    [{"role": "user", "content": "Bob prefers TypeScript."}],
    user_id="bob",
    infer=False,
)
```

## Step 3: Search Within a Scope

Mem0 accepts scope fields through its `filters` argument:

```python
alice_results = memory.search(
    "Preferred programming language",
    filters={"user_id": "alice"},
    threshold=1.0,
)

bob_results = memory.search(
    "Preferred programming language",
    filters={"user_id": "bob"},
    threshold=1.0,
)
```

The Alice search is scoped to Alice's records, and the Bob search is scoped to Bob's records. The filter is applied by the Mem0 Valkey provider when it builds the vector query.

## Step 4: Combine User and Agent Scopes

Use more than one scope field when an agent has private knowledge for each user:

```python
memory.add(
    [{"role": "user", "content": "The refund window is 30 days."}],
    user_id="alice",
    agent_id="support",
    infer=False,
)

support_results = memory.search(
    "What is the refund window?",
    filters={"user_id": "alice", "agent_id": "support"},
    threshold=1.0,
)
```

`run_id` is available for a conversation or task scope. Use the narrowest set of filters that matches the data-access boundary in your application.

## How It Works

Mem0 stores scope fields with each memory and uses them as Valkey Search TAG filters. The application calls Mem0's `search` and `get_all` methods; it does not need to construct search commands itself.

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `user_id` | One scope required for search | - | Scope memories to one user. |
| `agent_id` | No | - | Scope memories to one agent. |
| `run_id` | No | - | Scope memories to one run or conversation. |
| `filters` | Yes for search/list | - | Dictionary containing one or more scope fields. |
| `threshold` | No | `0.1` | Minimum semantic score required by Mem0's search API. |

## Teardown

Remove the collection keys and index using the cleanup function in the sample:

```python
from main import build_memory, reset_memory

memory = build_memory("multi_user_app")
reset_memory(memory)
memory.close()
```

---

[<- 01 - Getting Started](01-getting-started.md) | [03 - Production Configuration ->](03-production.md)
