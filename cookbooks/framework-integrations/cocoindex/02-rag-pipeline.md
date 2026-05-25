# RAG Pipeline with Incremental Sync

**Intermediate** · Python · ~20 min

## What You'll Build

A production-ready RAG pipeline that watches a directory of markdown files, splits them into chunks, embeds each chunk with sentence-transformers, and stores the results in Valkey with an HNSW vector index — all with CocoIndex's incremental engine ensuring only changed files are reprocessed.

You'll also add a semantic search query interface using Valkey's `FT.SEARCH` KNN queries.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module (`valkey/valkey-bundle:latest`)
- Some markdown files to index (we'll provide samples)

## Step 1: Project Setup

Create a new project directory:

```bash
mkdir cocoindex-valkey-rag && cd cocoindex-valkey-rag
```

Create `pyproject.toml`:

```toml
[project]
name = "cocoindex-valkey-rag"
version = "0.1.0"
description = "CocoIndex RAG pipeline with Valkey vector store"
requires-python = ">=3.11"
dependencies = [
    "cocoindex[valkey,sentence_transformers]>=1.0.4",
    "numpy",
    "python-dotenv>=1.0.1",
]

[tool.setuptools]
packages = []
```

Create `.env`:

```env
COCOINDEX_DB=./cocoindex.db
PYTORCH_ENABLE_MPS_FALLBACK=1
```

Install:

```bash
pip install -e .
```

## Step 2: Create Sample Documents

```bash
mkdir markdown_files
```

Create `markdown_files/valkey.md`:

```markdown
# Valkey

Valkey is a high-performance, open-source in-memory data store that originated
as a fork of Redis. It supports strings, hashes, lists, sets, sorted sets,
streams, and more.

## Vector Search

The valkey-search module adds vector similarity search to Valkey. It supports
HNSW (Hierarchical Navigable Small World) indexes for approximate nearest
neighbor search with sub-millisecond latency.

## Use Cases

- Session storage and caching
- Real-time leaderboards
- Pub/sub messaging
- Vector similarity search for RAG pipelines
- Rate limiting and distributed locks
```

Create `markdown_files/cocoindex.md`:

```markdown
# CocoIndex

CocoIndex is an open-source Python framework for building incremental data
pipelines that keep AI agent context continuously fresh.

## Key Features

- **Incremental processing** — only the delta is reprocessed on every change
- **Declarative** — describe what your target should contain
- **Parallel execution** — Rust core handles parallelism automatically
- **Lineage tracking** — every target row traces back to its source

## Supported Targets

CocoIndex supports Postgres (pgvector), Qdrant, LanceDB, TurboPuffer,
Valkey, Neo4j, FalkorDB, Kafka, and more as target stores.
```

## Step 3: Build the Pipeline

Create `main.py`:

```python
"""
CocoIndex + Valkey RAG Pipeline

Index (use `-L` for live mode, omit for one-shot catch-up):
    cocoindex update main
    cocoindex update -L main

Query the index:
    python main.py "your query"

Pipeline: walk markdown files -> chunk -> embed -> store in Valkey (HNSW index).
"""

from __future__ import annotations

import asyncio
import pathlib
import struct
import sys
from typing import AsyncIterator

from dotenv import load_dotenv
from glide import GlideClient
from glide.async_commands import ft
from glide.async_commands.ft import FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_search_options import ReturnField

import cocoindex as coco
from cocoindex.connectors import localfs, valkey
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike, PatternFilePathMatcher
from cocoindex.resources.id import IdGenerator


# Configuration
VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
INDEX_NAME = "rag_documents"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5

# Context keys — stable identities for the Valkey client and embedder
VALKEY_DB = coco.ContextKey[GlideClient]("rag_valkey")
EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder", detect_change=True)

_splitter = RecursiveSplitter()


# ============================================================================
# Lifespan — manages the Valkey connection and embedder
# ============================================================================


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)
    builder.provide(VALKEY_DB, client)
    builder.provide(EMBEDDER, SentenceTransformerEmbedder(EMBED_MODEL))
    yield
    await client.close()


# ============================================================================
# Pipeline functions
# ============================================================================


@coco.fn
async def process_chunk(
    chunk: Chunk,
    filename: pathlib.PurePath,
    id_gen: IdGenerator,
    target: valkey.IndexTarget,
) -> None:
    """Embed a single chunk and declare it in the Valkey index."""
    embedder = coco.use_context(EMBEDDER)
    embedding = await embedder.embed(chunk.text)

    doc_id = await id_gen.next_id(chunk.text)
    target.declare_document(valkey.Document(
        id=str(doc_id),
        vector=embedding.tolist(),
        payload={
            "filename": str(filename),
            "text": chunk.text,
            "chunk_start": str(chunk.start.char_offset),
            "chunk_end": str(chunk.end.char_offset),
        },
    ))


@coco.fn(memo=True)
async def process_file(
    file: FileLike,
    target: valkey.IndexTarget,
) -> None:
    """Split a file into chunks and process each one.

    memo=True means CocoIndex caches the result keyed by hash(file content).
    If the file hasn't changed, this function is skipped entirely.
    """
    text = await file.read_text()
    chunks = _splitter.split(
        text, chunk_size=2000, chunk_overlap=500, language="markdown"
    )
    id_gen = IdGenerator()
    await coco.map(process_chunk, chunks, file.file_path.path, id_gen, target)


@coco.fn
async def app_main(sourcedir: pathlib.Path) -> None:
    """Declare the pipeline: source -> transform -> target."""
    # Declare the Valkey index target
    target_index = await valkey.mount_index_target(
        VALKEY_DB,
        INDEX_NAME,
        await valkey.IndexSchema.create(
            vectors=valkey.VectorDef(schema=EMBEDDER, distance="cosine"),
        ),
    )

    # Declare the source: walk markdown files with live watching support
    files = localfs.walk_dir(
        sourcedir,
        recursive=True,
        path_matcher=PatternFilePathMatcher(included_patterns=["**/*.md"]),
        live=True,
    )

    # Connect source to target through the processing functions
    await coco.mount_each(process_file, files.items(), target_index)


# Register the app
app = coco.App(
    coco.AppConfig(name="ValkeyRAG"),
    app_main,
    sourcedir=pathlib.Path("./markdown_files"),
)


# ============================================================================
# Query demo — semantic search using Valkey FT.SEARCH
# ============================================================================


async def query_once(
    client: GlideClient,
    embedder: SentenceTransformerEmbedder,
    query_text: str,
    *,
    top_k: int = TOP_K,
) -> None:
    """Run a KNN vector search against the Valkey index."""
    query_vec = await embedder.embed(query_text)
    vec_blob = struct.pack(f"<{len(query_vec)}f", *query_vec.tolist())

    knn_query = f"*=>[KNN {top_k} @vector $query_vec AS score]"

    results = await ft.search(
        client,
        INDEX_NAME,
        knn_query,
        options=FtSearchOptions(
            params={"query_vec": vec_blob},
            return_fields=[
                ReturnField("text"),
                ReturnField("filename"),
                ReturnField("score"),
            ],
        ),
    )

    print(f"\nResults for: \"{query_text}\"\n{'=' * 60}")

    if not results or len(results) < 2:
        print("No results found.")
        return

    # FT.SEARCH returns [total_count, {key: {field: value}, ...}]
    total = results[0]
    print(f"Total matches: {total}\n")

    docs = results[1]  # dict of {key: {field: value}}
    for key, fields in docs.items():
        key_str = key.decode() if isinstance(key, bytes) else key
        score = fields.get(b"score", fields.get("score", b"?"))
        filename = fields.get(b"filename", fields.get("filename", b"<unknown>"))
        text = fields.get(b"text", fields.get("text", b""))

        # Decode bytes
        if isinstance(score, bytes):
            score = score.decode()
        if isinstance(filename, bytes):
            filename = filename.decode()
        if isinstance(text, bytes):
            text = text.decode()

        print(f"[score: {score}] {filename}")
        print(f"    {text[:120]}...")
        print("---")


async def query(initial_query: str | None = None) -> None:
    """Interactive or one-shot query mode."""
    embedder = SentenceTransformerEmbedder(EMBED_MODEL)
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)

    try:
        if initial_query is not None:
            await query_once(client, embedder, initial_query)
            return

        while True:
            q = input("\nEnter search query (or Enter to quit): ").strip()
            if not q:
                break
            await query_once(client, embedder, q)
    finally:
        await client.close()


if __name__ == "__main__":
    load_dotenv()
    initial = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    asyncio.run(query(initial))
```

## Step 4: Run the Pipeline

Build the index (one-shot catch-up):

```bash
cocoindex update main
```

You should see CocoIndex processing the markdown files, splitting them into chunks, embedding them, and upserting documents into Valkey.

## Step 5: Query the Index

```bash
python main.py "what is vector search?"
```

Expected output:

```
Results for: "what is vector search?"
============================================================
Total matches: 2

[score: 0.629616558552] markdown_files/valkey.md
    # Valkey

Valkey is a high-performance, open-source in-memory data store that originated
as a fork of Redis. It supports...
---
[score: 0.83438450098] markdown_files/cocoindex.md
    # CocoIndex

CocoIndex is an open-source Python framework for building incremental data
pipelines that keep AI agent con...
---
```

## Step 6: Test Incremental Updates

Edit `markdown_files/valkey.md` — add a new section:

```markdown
## Persistence

Valkey supports RDB snapshots and AOF (Append-Only File) persistence.
RDB creates point-in-time snapshots at configured intervals.
AOF logs every write operation for maximum durability.
```

Re-run the pipeline:

```bash
cocoindex update main
```

Only the modified file is re-chunked and re-embedded. Unchanged files are skipped entirely thanks to `memo=True` on `process_file`.

## Step 7: Live Mode

For continuous synchronization, run in live mode:

```bash
cocoindex update -L main
```

CocoIndex watches the source directory for changes and automatically reprocesses only the modified files. The Valkey index stays fresh without full re-indexing.

## How It Works Under the Hood

| Operation | Valkey Command | When It Happens |
|-----------|---------------|-----------------|
| Create index | `FT.CREATE rag_documents ON HASH PREFIX 1 rag_documents: SCHEMA vector VECTOR HNSW ...` | First run (auto-managed) |
| Upsert document | `HSET rag_documents:{id} text "..." filename "..." vector <bytes>` | Document added or changed |
| Delete document | `DEL rag_documents:{id}` | Source chunk no longer exists |
| KNN search | `FT.SEARCH rag_documents "*=>[KNN 5 @vector $vec]"` | Query time |

### Incremental Behavior

```
First run:
  file_a.md (new)     → chunk → embed → HSET 3 documents
  file_b.md (new)     → chunk → embed → HSET 2 documents

Second run (file_a.md edited):
  file_a.md (changed) → chunk → embed → HSET 3 documents (updated)
  file_b.md (same)    → SKIPPED (memo cache hit)

Third run (file_b.md deleted):
  file_a.md (same)    → SKIPPED
  file_b.md (gone)    → DEL 2 documents (automatic cleanup)
```

## HNSW vs FLAT Index

| Parameter | HNSW (default) | FLAT |
|-----------|----------------|------|
| Speed | Sub-millisecond | Scales linearly with data |
| Accuracy | Approximate (~99%+ recall) | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Production (>1000 docs) | Small datasets or testing |

Switch algorithm in the pipeline:

```python
await valkey.IndexSchema.create(
    vectors=valkey.VectorDef(schema=EMBEDDER, distance="cosine", algorithm="flat"),
)
```

## Distance Metrics

| Metric | Use Case | Score Interpretation |
|--------|----------|---------------------|
| `cosine` (default) | Text embeddings, normalized vectors | Lower = more similar |
| `l2` | Euclidean distance | Lower = more similar |
| `ip` | Inner product (dot product) | Higher = more similar |

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| Embed chunk (all-MiniLM-L6-v2) | ~5ms | CPU; faster on GPU |
| HSET document | ~0.1ms | Single hash write |
| FT.SEARCH KNN (10K docs) | <1ms | HNSW approximate |
| FT.SEARCH KNN (1M docs) | ~2-5ms | HNSW approximate |
| Full re-index (1000 files) | Minutes | One-time cost |
| Incremental update (1 file) | Seconds | Only Δ reprocessed |

## Production Deployment

### Docker Compose

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:latest
    ports:
      - "6379:6379"
    volumes:
      - valkey_data:/data
    command: valkey-server --save 60 1 --loglevel warning

  cocoindex-pipeline:
    build: .
    environment:
      - COCOINDEX_DB=postgres://cocoindex:cocoindex@postgres/cocoindex
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6379
    depends_on:
      - valkey
      - postgres
    command: cocoindex update -L main

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=cocoindex
      - POSTGRES_PASSWORD=cocoindex
      - POSTGRES_DB=cocoindex
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  valkey_data:
  pg_data:
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COCOINDEX_DB` | — | CocoIndex state store (Postgres URL or SQLite path) |
| `VALKEY_HOST` | `localhost` | Valkey server host |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `VALKEY_PASSWORD` | None | Authentication password |

## Comparison with Other Vector Targets

| Feature | Valkey | Postgres (pgvector) | Qdrant |
|---------|--------|--------------------:|--------|
| Latency | ~0.5ms | ~5-10ms | ~1-2ms |
| Persistence | Optional (RDB/AOF) | Always | Always |
| Filtering | TAG + NUMERIC fields | SQL WHERE | Full payload filter |
| Hosted options | ElastiCache, MemoryDB | RDS, Aurora | Qdrant Cloud |
| Extra infra | Valkey server | Already have Postgres? | Separate service |

**When to choose Valkey**: You need the lowest possible latency, already run Valkey for caching/sessions, or want a single service for both cache and vector search.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ImportError: glide` | Package not installed | `pip install "cocoindex[valkey]"` |
| `Connection refused` | Valkey not running | Start Valkey container |
| `Unknown command FT.CREATE` | Search module not loaded | Use `valkey/valkey-bundle:latest` |
| Empty search results | Index empty or wrong name | Check `FT._LIST` and re-run pipeline |
| `memo` not skipping files | Changed embedder model | Expected — model change invalidates cache |

[← Back: 01 Getting Started](01-getting-started.md)
