# Getting Started with CrewAI + Valkey

> Connect to Valkey with valkey-glide, create an HNSW vector index, store memory records, and run your first KNN similarity search.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers new to Valkey vector search who want to understand the building blocks before implementing a full CrewAI memory backend.

## What is CrewAI + Valkey?

[CrewAI](https://github.com/crewAIInc/crewAI) orchestrates teams of AI agents that collaborate on tasks.
By default, agents forget everything between runs. Valkey gives them persistent, searchable memory
so a code review agent remembers past vulnerabilities and a research agent builds on previous findings.

This cookbook uses [valkey-glide](https://github.com/valkey-io/valkey-glide) (the official high-performance Valkey client) and Valkey's built-in Search module for vector similarity.

## Prerequisites

- Docker or Podman installed
- Python 3.10+
- No API keys or external services needed

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify Valkey is running with the search module:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should show "search" in the output
```

## Step 2: Install Dependencies

```bash
pip install valkey-glide==2.5.0 numpy==2.2.6
```

## Step 3: Connect with GLIDE

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        request_timeout=5000,
    )
    client = await GlideClient.create(config)
    try:
        print(await client.ping())  # b'PONG'
    finally:
        await client.close()

asyncio.run(main())
```

Always wrap client usage in `try/finally` to ensure the connection is closed.

## Step 4: Create a Vector Index

Define an HNSW index on HASH keys. This lets Valkey search by vector similarity:

```python
from glide import ft, VectorField
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType, DistanceMetricType, FtCreateOptions, TagField,
    VectorAlgorithm, VectorFieldAttributesHnsw, VectorType,
)

INDEX_NAME = "memory-demo"
PREFIX = "mem:"
EMBEDDING_DIM = 4  # Small for demo; real models use 384-1536

hnsw = VectorFieldAttributesHnsw(
    dimensions=EMBEDDING_DIM,
    distance_metric=DistanceMetricType.COSINE,
    type=VectorType.FLOAT32,
)
schema = [
    TagField("scope"),
    VectorField("embedding", VectorAlgorithm.HNSW, hnsw),
]
await ft.create(
    client, INDEX_NAME, schema,
    FtCreateOptions(DataType.HASH, prefixes=[PREFIX]),
)
```

## Step 5: Store and Search

```python
import numpy as np

# Store a record with its embedding
vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
await client.hset("mem:doc1", {
    "scope": "tech",
    "content": "Valkey uses HNSW for vector search",
    "embedding": vec.tobytes(),
})

import time
time.sleep(0.3)  # Wait for indexing

# KNN search — find the nearest vector
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions

query_vec = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
query_vec = query_vec / np.linalg.norm(query_vec)

count, docs = await ft.search(
    client, INDEX_NAME,
    "(*)=>[KNN 1 @embedding $query_vec AS score]",
    FtSearchOptions(params={"query_vec": query_vec.tobytes()}, dialect=2),
)

for key, fields in docs.items():
    score = float(fields[b"score"])
    similarity = 1.0 - score  # COSINE: distance → similarity
    print(f"{key.decode()}: similarity={similarity:.3f}")
```

## How It Works

| Component | Role |
|-----------|------|
| `FT.CREATE` | Defines a vector index on HASH keys with HNSW algorithm |
| `HSET` | Stores records with embedding bytes + metadata fields |
| `FT.SEARCH ... KNN` | Finds the K nearest vectors by cosine similarity |
| TAG fields | Enable exact-match filtering alongside vector search |

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | No | `6379` | Valkey server port |

## Teardown

```bash
docker rm -f valkey
```

---

[02 - Memory Storage Backend →](02-memory-storage.md)
