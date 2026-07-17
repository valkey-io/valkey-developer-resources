# Getting Started with CocoIndex + Valkey

> Build a local CocoIndex pipeline that stores searchable document vectors in
> Valkey.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers learning how to connect CocoIndex to
Valkey Search for an incremental document pipeline.

## What is CocoIndex + Valkey?

[CocoIndex](https://github.com/cocoindex-io/cocoindex) is an open-source Python
framework for building incremental data pipelines that keep AI agent context
fresh. It tracks source changes and only reprocesses the delta.

Valkey plugs in as a **vector store target**, giving you:

- **Vector search** — HNSW indexing with cosine, L2, or inner product distance
- **Incremental sync** — only changed documents are re-embedded and upserted; deletions are automatic
- **Declarative pipeline** — describe *what* your target should contain; CocoIndex handles the *how*
- **Target state** — the connector reconciles declared documents with the Valkey index

## Prerequisites

- Python 3.11 or newer
- Docker or Podman with Compose support
- Network access to PyPI and the public embedding model on first run

The default sample uses SQLite for CocoIndex state and does not require
Postgres, a GPU, an API key, or a cloud account.

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries. The `valkey-bundle` image includes it:

```bash
cd cookbooks/framework-integrations/cocoindex/sample
docker compose up -d --wait
```

The Compose health check waits for Valkey to accept connections. Substitute
`podman` for `docker` when using Podman.

> **Security:** This local example uses no authentication or TLS for
> simplicity. For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 2: Install CocoIndex with Valkey Support

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

This installs:

- `cocoindex` — the incremental pipeline framework
- `valkey-glide` — the official Valkey client with async support
- `sentence-transformers` — for generating embeddings locally
- `pytest` and `ruff` — for the sample checks

## Step 3: Verify the Connection

```python
"""Quick connectivity check."""
import asyncio
from glide import GlideClient
from cocoindex.connectors import valkey


async def check_connection():
    config = valkey.create_client_config("localhost", 6379)
    client = await GlideClient.create(config)

    try:
        result = await client.ping()
        print(f"Valkey says: {result}")

        # Search is available when the bundle exposes FT commands.
        from glide.async_commands import ft
        indexes = await ft.list(client)
        print(f"Search module loaded! ({len(indexes)} indexes found)")
    finally:
        await client.close()


asyncio.run(check_connection())
```

## Step 4: Understand CocoIndex's Valkey Connector

CocoIndex's Valkey connector uses a **target state** model:

1. You declare what documents *should* exist in the index
2. CocoIndex compares declared state vs actual state
3. Only the differences are applied (upserts and deletes)

```text
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
│    Managed hashes · HNSW index · KNN search          │
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

## How It Works

| Component | Role |
| --- | --- |
| CocoIndex source | Walks the local Markdown directory and tracks file changes |
| CocoIndex transforms | Splits text and creates one embedding per chunk |
| Valkey connector | Declares documents and reconciles the target state |
| Valkey Search | Stores the HNSW index and answers KNN queries |

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
    builder.provide(
        EMBEDDER,
        SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2"),
    )
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
        ("doc1", "Valkey is an open-source in-memory data store."),
        ("doc2", "CocoIndex builds incremental data pipelines for AI agents."),
        ("doc3", "HNSW indexes provide approximate nearest-neighbor search."),
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
.venv/bin/cocoindex update --reset -f main
```

## Step 6: Verify the Indexed Documents

```bash
.venv/bin/cocoindex update --reset -f main
.venv/bin/python main.py "open source in-memory database"
.venv/bin/python -m pytest -q
```

The sample's `verify` function uses the GLIDE API to issue a bound KNN query
against the index created by CocoIndex. The test also checks that a fixture
filename is returned, so a missing Search module or empty index fails loudly.

## Configuration Reference

| Setting | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `localhost` | Valkey hostname |
| `VALKEY_PORT` | `6379` | Valkey port |
| `COCOINDEX_DB` | `./cocoindex.db` | SQLite state path |
| `COCOINDEX_EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |

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

## Teardown

```bash
docker compose down -v
rm -rf cocoindex.db
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'glide'` | Run `.venv/bin/pip install -e ".[test]"` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:9.1.1` (includes Search) |
| `NOAUTH Authentication required` | Pass `password` to `create_client_config()` |
| `cocoindex: command not found` | Activate `.venv` or use `.venv/bin/cocoindex` |

---

[← CocoIndex overview](README.md) | [02 - RAG Pipeline with Incremental Sync →](02-rag-pipeline.md)
