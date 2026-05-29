# Getting Started with MindsDB + Valkey Vector Store

**Beginner** · Python/SQL · ~15 min

## What is MindsDB + Valkey?

[MindsDB](https://github.com/mindsdb/mindsdb) is an open-source AI platform that brings machine learning into databases using SQL. The Valkey handler connects Valkey as a **vector store backend**, giving you:

- **Sub-millisecond vector search** — HNSW indexing with cosine, L2, or inner product distance
- **SQL interface** — CREATE TABLE, INSERT, SELECT with vector search, DELETE — all via SQL
- **Knowledge Base integration** — use Valkey as the storage layer for MindsDB Knowledge Bases
- **valkey-glide client** — official async Valkey client with Rust core for high performance

## Prerequisites

- Python 3.10+
- Podman or Docker (for running Valkey)
- MindsDB installed (or the Valkey handler standalone)

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image includes it:

```bash
# Using Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Or using Docker
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and the search module is loaded:

```bash
podman exec valkey-search valkey-cli PING
# PONG

podman exec valkey-search valkey-cli MODULE LIST
# Should include "search" in the output
```

## Step 2: Install Dependencies

```bash
pip install valkey-glide numpy
```

These are the only dependencies needed for the Valkey vector store handler:
- `valkey-glide` — the official Valkey client with async support and Rust core
- `numpy` — for vector serialization (float32 byte arrays)

## Step 3: Verify the Connection

```python
"""Quick connectivity check using valkey-glide."""
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress, ft


async def check_connection():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)]
    )
    client = await GlideClient.create(config)

    result = await client.ping()
    print(f"Valkey says: {result}")  # "PONG"

    # Check search module is loaded (needed for vector indexes)
    indexes = await ft.list(client)
    print(f"Search module loaded! ({len(indexes)} indexes found)")

    await client.close()


asyncio.run(check_connection())
```

## Step 4: Understand the Handler Architecture

The MindsDB Valkey handler uses:

```
┌──────────────────────────────────────────────────────┐
│              MindsDB SQL Interface                     │
│   CREATE DATABASE · CREATE TABLE · INSERT · SELECT    │
├──────────────────────────────────────────────────────┤
│           ValkeyHandler (VectorStoreHandler)           │
│   create_table · insert · select · delete · drop      │
├──────────────────────────────────────────────────────┤
│           valkey-glide async client                    │
│   GlideClient · ft.create · ft.search · HSET/HGETALL │
├──────────────────────────────────────────────────────┤
│         Valkey Server + Search Module                  │
│   HNSW vector index · HASH-based document storage     │
└──────────────────────────────────────────────────────┘
```

Key concepts:

| Concept | Description |
|---------|-------------|
| **Database** | A connection to a Valkey instance (host, port, credentials) |
| **Table** | A vector index created with `FT.CREATE` over HASH keys |
| **Document** | A HASH key with fields: `id`, `content`, `embeddings`, `metadata` |
| **KNN Search** | `FT.SEARCH` with vector similarity query (cosine/L2/IP) |

## Step 5: Connect MindsDB to Valkey (SQL)

In the MindsDB SQL editor:

```sql
CREATE DATABASE my_valkey
WITH ENGINE = 'valkey',
PARAMETERS = {
    "host": "localhost",
    "port": 6379,
    "vector_dimension": 384,
    "distance_metric": "COSINE"
};
```

## Step 6: Use the Handler Directly (Python)

For standalone usage without the full MindsDB server:

```python
"""Direct handler usage — create index, insert docs, search."""
import asyncio
import numpy as np
from mindsdb.integrations.handlers.valkey_handler.valkey_handler import ValkeyHandler


def main():
    # Create the handler instance
    handler = ValkeyHandler(
        name="my_valkey",
        connection_data={
            "host": "localhost",
            "port": 6379,
            "vector_dimension": 3,  # small dims for demo
            "distance_metric": "COSINE",
        },
    )

    # Check connection
    status = handler.check_connection()
    print(f"Connected: {status.success}")

    # Create a vector index (table)
    handler.create_table("demo_collection")
    print("Created index: demo_collection")

    # List tables
    tables = handler.get_tables()
    print(f"Indexes: {tables.data_frame['table_name'].tolist()}")

    # Clean up
    handler.drop_table("demo_collection")
    handler.disconnect()


main()
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | `localhost` | Valkey server hostname |
| `port` | int | `6379` | Valkey server port |
| `password` | str | `None` | Authentication password |
| `db` | int | `0` | Database number (0-15) |
| `vector_dimension` | int | `384` | Default embedding dimension for new indexes |
| `distance_metric` | str | `COSINE` | Distance metric: `COSINE`, `L2`, or `IP` |
| `prefix` | str | `doc:` | Key prefix for document hash keys |

## Distance Metrics

| Metric | Description | Use Case |
|--------|-------------|----------|
| `COSINE` | Cosine similarity (1 - cos_sim) | Text embeddings, normalized vectors |
| `L2` | Euclidean distance | Image embeddings, spatial data |
| `IP` | Inner product (negative dot product) | Pre-normalized vectors, recommendations |

## What's Next

- [02 - RAG Pipeline with Vector Search →](02-rag-pipeline.md) — insert real embeddings, perform KNN search, and use metadata filtering

## Authentication Options

`valkey-glide` supports multiple authentication methods:

| Method | Use Case | Configuration |
|--------|----------|---------------|
| **Password only (`requirepass`)** | Simple deployments | `"password": "your-password"` |
| **Username/Password (ACL)** | Multi-user setups | Pass credentials via `ServerCredentials` |
| **TLS / mTLS** | Encrypted connections | Configure via `GlideClientConfiguration` |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `pip install valkey-glide` |
| `Connection refused on port 6379` | Ensure Valkey is running: `podman ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle` image (includes search module) |
| `NOAUTH Authentication required` | Set `password` in connection parameters |
| `Index already exists` | Expected — handler skips creation with `if_not_exists=True` |

[Next: 02 RAG Pipeline with Vector Search →](02-rag-pipeline.md)
