# Getting Started with Mem0 + Valkey

> Configure Mem0 to store searchable agent memories in a Valkey vector index.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers adding persistent memory to an agent and wanting Mem0 to manage the memory API.

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- A working terminal

The default sample path is credential-free. The OpenAI-backed examples in this
page require an `OPENAI_API_KEY`.

## What is Mem0?

[Mem0](https://github.com/mem0ai/mem0) is an open-source memory layer for AI
applications. It includes a dedicated Valkey connector that uses the `valkey`
Python client for vector-based memory storage and retrieval.

## Step 1: Install

Install the pinned Mem0 and Valkey client versions:

```bash
python -m venv .venv
.venv/bin/python -m pip install "mem0ai==2.0.12" "valkey==6.1.1"
```

For the credential-free runnable sample, use the pinned dependencies in
[`sample/requirements.txt`](sample/requirements.txt) and follow
[`sample/README.md`](sample/README.md).

## Step 2: Start Valkey with Search Module

Start Valkey with the Search module using the pinned bundle image:

```bash
docker run -d --name valkey-mem0 -p 6379:6379 valkey/valkey-bundle:9.1.0
until [ "$(docker exec valkey-mem0 valkey-cli ping 2>/dev/null)" = "PONG" ]; do sleep 1; done
```

The bundle includes the Search module required by Mem0's Valkey provider.

> **Security:** This local example uses no authentication or TLS. For any
> non-localhost deployment, enable authentication and TLS. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

<!-- markdownlint-disable-next-line MD028 -->

> **Note:** Substitute `podman` for `docker` if Podman is your container
> runtime.

## Step 3: Configure Mem0 with Valkey

Configure the Valkey vector store and the application-level LLM and embedder:

```python
import os

from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": "valkey://localhost:6379?socket_timeout=5",
            "collection_name": "mem0",
            "embedding_model_dims": 1536,
            "index_type": "hnsw",
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model": "gpt-4o-mini",
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model": "text-embedding-3-small",
        },
    },
}

memory = Memory.from_config(config)
print("Mem0 connected to Valkey!")
```

The `embedding_model_dims` value must match the configured embedder. The
credential-free sample replaces the configured embedder with Mem0's
deterministic `MockEmbeddings` implementation and uses `infer=False`.

## Step 4: Add Memories

```python
# Add memories from a conversation
messages = [
    {"role": "user", "content": "I love Italian food, especially pasta carbonara."},
    {"role": "assistant", "content": "Great choice! Carbonara is a classic Roman dish."},
]
result = memory.add(messages, user_id="user_001")
print(f"Added: {result}")

# Add more context
messages2 = [
    {"role": "user", "content": "I'm allergic to shellfish and prefer spicy food."},
    {"role": "assistant", "content": "Noted! I'll keep that in mind for recommendations."},
]
memory.add(messages2, user_id="user_001")
```

## Step 5: Search Memories

Mem0 2.0 uses the `filters` argument for entity scoping:

```python
results = memory.search(
    query="What food does this user like?",
    filters={"user_id": "user_001"},
    top_k=3,
)

for entry in results["results"]:
    print(f"Memory: {entry['memory']}")
    print(f"Score: {entry.get('score', 'N/A')}\n")
```

## Step 6: Get All Memories for a User

`get_all` defaults to 20 results. Set `top_k` to an application-appropriate
bound when retrieving a larger collection:

```python
all_memories = memory.get_all(
    filters={"user_id": "user_001"},
    top_k=1000,
)
for m in all_memories["results"]:
    print(f"  - {m['memory']}")
```

## Step 7: Use Memories in a Chatbot

```python
from openai import OpenAI

openai_client = OpenAI()


def chat_with_memory(message: str, user_id: str) -> str:
    relevant = memory.search(
        query=message,
        filters={"user_id": user_id},
        top_k=3,
    )
    memories_str = "\n".join(
        f"- {entry['memory']}" for entry in relevant["results"]
    )

    system = f"You are a helpful AI. Use these memories about the user:\n{memories_str}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini", messages=messages,
    )
    answer = response.choices[0].message.content

    memory.add(
        [{"role": "user", "content": message},
         {"role": "assistant", "content": answer}],
        user_id=user_id,
    )
    return answer


response = chat_with_memory("Recommend me a restaurant", "user_001")
print(response)
```

## How It Works Under the Hood

| Operation | Mem0 API | Valkey operation |
| --- | --- | --- |
| Add memory | `memory.add(messages, user_id)` | Stores a hash under the collection prefix |
| Search | `memory.search(query, filters={"user_id": user_id})` | KNN search with a TAG filter |
| Get all | `memory.get_all(filters={"user_id": user_id})` | Filtered collection search |
| Index creation | Automatic on init | Creates an HNSW vector index |

The official connector implementation is in
[Mem0's Valkey vector store](https://github.com/mem0ai/mem0/blob/main/mem0/vector_stores/valkey.py).

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `valkey_url` | Yes | - | Valkey connection URL, such as `valkey://localhost:6379`. |
| `socket_timeout` | No | None (no timeout) | Seconds before a socket read/write times out. Passed as a URL query parameter. |
| `collection_name` | Yes | - | Name of the Mem0 collection and Valkey index. |
| `embedding_model_dims` | Yes | - | Number of values produced by the embedder. |
| `index_type` | No | `hnsw` | `hnsw` for approximate search or `flat` for exact search. |

## Teardown

```bash
docker rm -f valkey-mem0
```

---

[Next -> 02 - Multi-User Memory](02-multi-user-memory.md)
