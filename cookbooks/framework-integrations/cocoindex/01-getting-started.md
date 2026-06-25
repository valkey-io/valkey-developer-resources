# Getting Started with CocoIndex + Valkey

**Beginner** · Python · ~15 min

## What is CocoIndex + Valkey?

[CocoIndex](https://github.com/cocoindex-io/cocoindex) is an open-source Python framework for building incremental data pipelines that keep AI agent context continuously fresh. It tracks source changes and only reprocesses the delta — no stale batches, no wasted compute.

Valkey plugs in as a **vector store target**, giving you:

- **Sub-millisecond vector search** — HNSW indexing with cosine, L2, or inner product distance
- **Incremental sync** — only changed documents are re-embedded and upserted; deletions are automatic
- **Declarative pipeline** — describe *what* your target should contain; CocoIndex handles the *how*
- **Production-grade** — Rust core with retries, lineage tracking, and parallel execution

## Prerequisites

- Python 3.10+
- Docker (for running Valkey)
- A Postgres instance for CocoIndex internal state (or use SQLite with `COCOINDEX_DB=./cocoindex.db`)

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image includes it:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" in the output
```

## Step 2: Install CocoIndex with Valkey Support

```bash
pip install "cocoindex[valkey,sentence_transformers]"
```

This installs:
- `cocoindex` — the core framework with its Rust-powered incremental engine
- `valkey-glide` — the official Valkey client with async support
- `sentence-transformers` — for generating embeddings locally

## Step 3: Verify the Connection

```python
"""Quick connectivity check."""
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def check_connection():
    config = GlideClientConfiguration(
        [NodeAddress(host="localhost", port=6379)]
    )
    client = await GlideClient.create(config)

    result = await client.ping()
    print(f"Valkey says: {result}")  # b"PONG"

    # Check search module is loaded (needed for vector indexes)
    from glide.async_commands import ft
    indexes = await ft.list(client)
    print(f"Search module loaded! ({len(indexes)} indexes found)")

    await client.close()


asyncio.run(check_connection())
```

## Step 4: Understand CocoIndex's Valkey Connector

CocoIndex's Valkey connector uses a **target state** model:

1. You declare what documents *should* exist in the index
2. CocoIndex compares declared state vs actual state
3. Only the differences are applied (upserts and deletes)

```
┌──────────────────────────────────────────────────────┐
│               CocoIndex Pipeline                      │
├────────────────┬─────────────────────────────────────┤
│  Sources       │  Transformations                    │
│  (local files, │  (chunk, embed, extract)            │
│   S3, APIs)    │                                     │
├────────────────┴─────────────────────────────────────┤
│           Incremental Engine (Rust core)              │
│    Tracks lineage · Only reprocesses Δ · Parallel     │
├──────────────────────────────────────────────────────┤
│         Valkey Target (valkey-glide client)           │
│    HSET documents · FT.CREATE index · FT.SEARCH      │
├──────────────────────────────────────────────────────┤
│         Valkey Server + Search Module                 │
└──────────────────────────────────────────────────────┘
```

Key concepts:

| Concept | Description |
|---------|-------------|
| `ContextKey` | Stable identity for a Valkey connection across pipeline runs |
| `IndexTarget` | Represents a search index you declare documents into |
| `Document` | A record with `id`, `vector`, and optional `payload` fields |
| `IndexSchema` | Defines vector configuration (dimensions, distance, algorithm) |

## Step 5: Minimal Pipeline Example

```python
"""Minimal CocoIndex + Valkey pipeline."""
import asyncio
from typing import AsyncIterator
from glide import GlideClient

import cocoindex as coco
from cocoindex.connectors import valkey
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder


VALKEY_DB = coco.ContextKey[GlideClient]("my_valkey")
EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder", detect_change=True)


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    config = valkey.create_client_config("localhost", 6379)
    client = await GlideClient.create(config)
    builder.provide(VALKEY_DB, client)
    builder.provide(EMBEDDER, SentenceTransformerEmbedder("all-MiniLM-L6-v2"))
    yield
    await client.close()


@coco.fn
async def index_document(text: str, doc_id: str, target: valkey.IndexTarget) -> None:
    embedder = coco.use_context(EMBEDDER)
    embedding = await embedder.embed(text)
    target.declare_document(valkey.Document(
        id=doc_id,
        vector=embedding.tolist(),
        payload={"text": text},
    ))


@coco.fn
async def app_main() -> None:
    index = await valkey.mount_index_target(
        VALKEY_DB,
        "my_documents",
        await valkey.IndexSchema.create(
            vectors=valkey.VectorDef(schema=EMBEDDER, distance="cosine"),
        ),
    )

    # In a real pipeline, documents come from a source connector
    docs = [
        ("doc1", "Valkey is a high-performance in-memory data store."),
        ("doc2", "CocoIndex builds incremental data pipelines for AI agents."),
        ("doc3", "HNSW indexes provide sub-millisecond approximate nearest neighbor search."),
    ]
    for doc_id, text in docs:
        await coco.mount(
            coco.component_subpath("doc", doc_id),
            index_document, text, doc_id, index,
        )


app = coco.App(coco.AppConfig(name="MinimalValkey"), app_main)
```

Run it:

```bash
export COCOINDEX_DB=./cocoindex.db
cocoindex update main
```

## Step 6: Verify Data in Valkey

```bash
# Check the index was created
docker exec valkey valkey-cli FT._LIST
# Should show "my_documents"

# Check stored documents
docker exec valkey valkey-cli HGETALL "my_documents:doc1"
# Shows text payload and vector blob
```

## What's Next

- [02 - RAG Pipeline with Incremental Sync →](02-rag-pipeline.md) — build a complete pipeline that watches a directory, chunks files, embeds them into Valkey, and supports live semantic search

## Authentication Options

`valkey-glide` supports multiple authentication methods depending on your deployment:

| Method | Use Case | Documentation |
|--------|----------|---------------|
| **Username/Password (ACL)** | Self-managed Valkey with ACL users configured | [Authentication Guide](https://glide.valkey.io/how-to/security/authentication/) |
| **Password only (`requirepass`)** | Simple deployments with a single shared password | [Authentication Guide](https://glide.valkey.io/how-to/security/authentication/) |
| **TLS / mTLS** | Encrypt in-transit data; verify client identity with certificates | [TLS Guide](https://glide.valkey.io/how-to/security/tls/) |
| **AWS IAM** | Amazon ElastiCache / MemoryDB clusters (auto token rotation) | [IAM Integration](https://glide.valkey.io/how-to/security/iam-integration/) |

Pass credentials via `valkey.create_client_config()`:

```python
config = valkey.create_client_config(
    "my-valkey-host.example.com",
    6379,
    password="my-secret",
    use_tls=True,
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `pip install "cocoindex[valkey]"` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` image (includes search module) |
| `NOAUTH Authentication required` | Pass `password` to `create_client_config()` |
| `cocoindex: command not found` | Run `pip install cocoindex` or check your PATH |

[Next: 02 RAG Pipeline with Incremental Sync →](02-rag-pipeline.md)
