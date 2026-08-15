# Multi-User Memory

> Isolate Mem0 memories by user, agent, and conversation while keeping the application on Mem0's public API.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers building multi-tenant agents that must keep user and agent memories separate.

## Prerequisites

- Docker
- Python 3.10 or newer
- The dependencies and local Valkey instance from
  [Getting Started](01-getting-started.md)

The API examples use Ollama for embeddings and fact extraction (no API key
required). The runnable sample uses deterministic local embeddings instead.

## Memory Isolation

Mem0 supports three levels of memory isolation through filterable fields in
Valkey:

| Level | Parameter | Use Case |
| --- | --- | --- |
| User | `user_id` | Per-user preferences across all sessions |
| Agent | `agent_id` | Per-agent knowledge, such as support or sales |
| Session | `run_id` | Per-conversation context |

## Step 1: Setup

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": "valkey://localhost:6379?socket_timeout=5",
            "collection_name": "multi_user_app",
            "embedding_model_dims": 768,
            "index_type": "hnsw",
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.2",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "embedding_dims": 768,
            "ollama_base_url": "http://localhost:11434",
        },
    },
}
memory = Memory.from_config(config)
```

For a no-credential local run, use the runnable sample in
[`sample/README.md`](sample/README.md), which replaces the embedder with
`MockEmbeddings` and passes `infer=False` to `add`.

## Step 2: Per-User Memories

```python
# User Alice
memory.add(
    [{"role": "user", "content": "I prefer dark mode and Python."}],
    user_id="alice",
)

# User Bob
memory.add(
    [{"role": "user", "content": "I use TypeScript and like light mode."}],
    user_id="bob",
)

alice_results = memory.search(
    "What are the user preferences?",
    filters={"user_id": "alice"},
)
print("Alice:", [r["memory"] for r in alice_results["results"]])

bob_results = memory.search(
    "What are the user preferences?",
    filters={"user_id": "bob"},
)
print("Bob:", [r["memory"] for r in bob_results["results"]])

# Representative output:
# Alice: ['Prefers dark mode and Python']
# Bob: ['Uses TypeScript and likes light mode']
```

**How isolation works:** Each memory stores a `user_id` TAG field. When you
search with `filters={"user_id": "alice"}`, Mem0 passes the scope to its Valkey
provider, which adds a TAG filter to the `FT.SEARCH` query so Bob's memories are
not returned.

## Step 3: Per-Agent Memories

```python
# Support agent knowledge
memory.add(
    [{"role": "user", "content": "Our refund policy is 30 days for unused items."}],
    agent_id="support_bot",
)

# Sales agent knowledge
memory.add(
    [{"role": "user", "content": "Current promotion: 20% off all premium plans."}],
    agent_id="sales_bot",
)

support_results = memory.search(
    "What is the refund policy?",
    filters={"agent_id": "support_bot"},
)
sales_results = memory.search(
    "Any promotions?",
    filters={"agent_id": "sales_bot"},
)
# Each agent only sees its own knowledge.
```

## Step 4: Combined User + Agent

```python
# Add a memory scoped to both user and agent
memory.add(
    [{"role": "user", "content": "I had an issue with order #12345."}],
    user_id="alice",
    agent_id="support_bot",
)

results = memory.search(
    "Previous issues",
    filters={"user_id": "alice", "agent_id": "support_bot"},
)
# This finds Alice's support interactions only.
```

`run_id` is available for a conversation or task scope. Use the narrowest set
of filters that matches the data-access boundary in your application.

## Valkey Data Model

```text
# Each memory is stored as a Valkey Hash at:
#   mem0:multi_user_app:<memory_id>
#
# Fields:
#   memory_id: TAG
#   user_id: TAG      (enables per-user filtering)
#   agent_id: TAG     (enables per-agent filtering)
#   run_id: TAG       (enables per-session filtering)
#   memory: TEXT      (the extracted memory text)
#   embedding: VECTOR (HNSW FLOAT32 COSINE)
#   created_at: NUMERIC
#   updated_at: NUMERIC
```

The `memory` field is `TEXT` in the current Mem0 Valkey provider so it can
support full-text search alongside vector search.

The provider implementation is documented in
[Mem0's Valkey vector store](https://github.com/mem0ai/mem0/blob/main/mem0/vector_stores/valkey.py).

## How It Works

The application calls Mem0's `search` and `get_all` methods. It does not need
to construct Valkey Search commands itself.

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `user_id` | One scope required for search | - | Scope memories to one user. |
| `agent_id` | No | - | Scope memories to one agent. |
| `run_id` | No | - | Scope memories to one run or conversation. |
| `filters` | Yes for search/list | - | Dictionary containing one or more scope fields. |

---

[<- 01 - Getting Started](01-getting-started.md) | [03 - Production ->](03-production.md)
