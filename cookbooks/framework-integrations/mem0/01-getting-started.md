# Getting Started with Mem0 + Valkey

> Configure Mem0 to store searchable agent memories in a Valkey vector index.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers adding persistent memory to an agent and wanting Mem0 to manage the memory API.

## Prerequisites

- Docker or Podman
- Python 3.9 or newer
- A working terminal

## Step 1: Start Valkey

Start Valkey with the Search module using the pinned bundle image:

```bash
docker run -d --name valkey-mem0 -p 6379:6379 valkey/valkey-bundle:9.1.0
```

> **Security:** This local example uses no authentication or TLS. For any non-localhost deployment, enable authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify that the container is ready:

```bash
docker exec valkey-mem0 valkey-cli ping
# PONG
```

> **Note:** Substitute `podman` for `docker` if Podman is your container runtime.

## Step 2: Install Dependencies

Create an environment and install the pinned sample dependencies:

```bash
cd cookbooks/framework-integrations/mem0/sample
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The sample uses Mem0 2.0.12, the Valkey Python client 6.1.1, and a deterministic local embedding stub. No API key is required for the default path.

## Step 3: Configure Mem0

Mem0 creates the Valkey vector index from the `vector_store` configuration. The sample uses ten-dimensional deterministic embeddings so its tests do not require a model download:

```python
import os

os.environ["MEM0_TELEMETRY"] = "false"

from mem0 import Memory
from mem0.embeddings.mock import MockEmbeddings

memory = Memory.from_config(
    {
        "vector_store": {
            "provider": "valkey",
            "config": {
                "valkey_url": "valkey://localhost:6379?socket_timeout=5",
                "collection_name": "mem0_demo",
                "embedding_model_dims": 10,
                "index_type": "hnsw",
            },
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

# The sample replaces the configured embedder with Mem0's local mock.
memory.embedding_model = MockEmbeddings()
```

The sample disables Mem0 telemetry for local reproducibility. The configured LLM
is not called because the next step sets `infer=False`. The `socket_timeout`
query parameter prevents a stalled Valkey connection from blocking indefinitely.

## Step 4: Add a Memory

Call Mem0's `add` method with a user scope. With `infer=False`, Mem0 stores the supplied message directly instead of asking an LLM to extract facts:

```python
memory.add(
    [{"role": "user", "content": "Alice prefers Python for data work."}],
    user_id="alice",
    infer=False,
)
```

The `user_id` becomes a filterable field in Mem0's Valkey-backed store.

## Step 5: Search and List Memories

Use the same scope when searching:

```python
results = memory.search(
    "What programming language does Alice prefer?",
    filters={"user_id": "alice"},
    threshold=1.0,
)
print(results["results"][0]["memory"])

all_memories = memory.get_all(filters={"user_id": "alice"})
print(all_memories["results"])
```

The sample's `MockEmbeddings` makes the result deterministic. A production embedder should use the model's documented dimensions and a threshold selected for that model.

## How It Works

| Component | Role |
| --- | --- |
| Mem0 `Memory` | Provides memory creation, scoped search, and retrieval APIs. |
| Mem0 Valkey provider | Creates the collection and maps memory records to Valkey fields. |
| Valkey Search | Indexes metadata and vectors for filtered nearest-neighbor queries. |
| Local mock embedder | Makes the default sample deterministic without external credentials. |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `valkey_url` | Yes | - | Valkey connection URL, such as `valkey://localhost:6379`. |
| `collection_name` | Yes | - | Name of the Mem0 collection and Valkey index. |
| `embedding_model_dims` | Yes | - | Number of values produced by the embedder. |
| `index_type` | No | `hnsw` | `hnsw` for approximate search or `flat` for exact search. |
| `hnsw_m` | No | `16` | HNSW connections per layer. |
| `hnsw_ef_construction` | No | `200` | HNSW construction search width. |
| `hnsw_ef_runtime` | No | `10` | HNSW query search width. |

## Teardown

The sample removes its `mem0:<collection>:` keys and index when it exits. Stop the container when finished:

```bash
docker rm -f valkey-mem0
```

---

[02 - Multi-User Memory ->](02-multi-user-memory.md)
