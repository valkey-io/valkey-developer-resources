# RAG Pipeline with Incremental Sync

> Build and query an incremental Markdown RAG pipeline with CocoIndex and
> Valkey Search.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who already know the CocoIndex connector
and want to add chunking, HNSW indexing, and filtered semantic search.

## What You'll Build

A RAG pipeline that watches a directory of Markdown files, splits them into
chunks, embeds each chunk with sentence-transformers, and stores the results in
Valkey with an HNSW vector index. CocoIndex ensures only changed files are
reprocessed.

You'll also add a semantic search query interface using Valkey's `FT.SEARCH` KNN queries.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the Search module (`valkey/valkey-bundle:9.1.1`)
- The sample dependencies installed in [`sample/`](sample/)
- The Markdown fixtures in [`sample/markdown_files/`](sample/markdown_files/)

## Step 1: Project Setup

Use the self-contained sample directory:

```bash
cd cookbooks/framework-integrations/cocoindex/sample
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

The sample keeps the project files beside the walkthrough:
[`sample/pyproject.toml`](sample/pyproject.toml) pins the dependencies,
[`sample/.env.example`](sample/.env.example) documents local configuration, and
[`sample/docker-compose.yml`](sample/docker-compose.yml) starts the required
Search-enabled Valkey service.

## Step 2: Create Sample Documents

The sample includes two deterministic Markdown fixtures. The following
content shows the shape of the source data in
`sample/markdown_files/valkey.md`:

```markdown
# Valkey

Valkey is an open-source in-memory data store that originated as a fork of
Redis. It supports strings, hashes, lists, sets, sorted sets, streams, and
more.

## Vector Search

The valkey-search module adds vector similarity search to Valkey. It supports
HNSW (Hierarchical Navigable Small World) indexes for approximate nearest
neighbor search over vector data.

## Use Cases

- Session storage and caching
- Real-time leaderboards
- Pub/sub messaging
- Vector similarity search for RAG pipelines
- Rate limiting and distributed locks
```

The second fixture, `sample/markdown_files/cocoindex.md`, describes the
incremental pipeline and its supported target pattern:

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

> **Note:** The full working code is available in
> [`sample/main.py`](sample/main.py). The code below is kept in sync with that
> file.

```python
"""
CocoIndex + Valkey RAG Pipeline

Index (use `-L` for live mode, omit for one-shot catch-up):
    .venv/bin/cocoindex update --reset -f main
    .venv/bin/cocoindex update -L main

Query the index:
    python main.py "your query"

Pipeline: walk markdown files -> chunk -> embed -> store in Valkey (HNSW index).
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import struct
import sys
from typing import AsyncIterator

from dotenv import load_dotenv
from glide import GlideClient
from glide.async_commands import ft
from glide.async_commands.ft import FtSearchOptions
# NOTE: ReturnField lives in glide_shared today; import path may change in future
# valkey-glide releases. Pin your valkey-glide version to avoid surprises.
from glide_shared.commands.server_modules.ft_options.ft_search_options import ReturnField

import cocoindex as coco
from cocoindex.connectors import localfs, valkey
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike, PatternFilePathMatcher
from cocoindex.resources.id import IdGenerator


load_dotenv()

# Configuration
COCOINDEX_DB = os.environ.setdefault("COCOINDEX_DB", "./cocoindex.db")
VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
DEFAULT_INDEX_NAME = "rag_documents"
DEFAULT_FILTER_FILENAME = "markdown_files/valkey.md"
EMBED_MODEL = os.environ.get(
    "COCOINDEX_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
TOP_K = 5


def get_index_name() -> str:
    """Return the configured Valkey index name."""
    return os.environ.get("COCOINDEX_INDEX_NAME", DEFAULT_INDEX_NAME)


def format_result_count(count: int) -> str:
    """Label the number of rows returned by the top-k query."""
    return f"Returned results: {count}"


# Context keys — stable identities for the Valkey client and embedder
VALKEY_DB = coco.ContextKey[GlideClient]("rag_valkey")
EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder", detect_change=True)

_splitter = RecursiveSplitter()


def build_knn_query(top_k: int, filter_filename: str | None = None) -> str:
    """Build the Valkey Search KNN expression with a bound vector parameter."""
    pre_filter = f"@filename:{{{filter_filename}}}" if filter_filename else "*"
    return f"{pre_filter}=>[KNN {top_k} @vector $query_vec AS score]"


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
    # Declare the Valkey index target with indexed fields for hybrid search
    target_index = await valkey.mount_index_target(
        VALKEY_DB,
        get_index_name(),
        await valkey.IndexSchema.create(
            vectors=valkey.VectorDef(schema=EMBEDDER, distance="cosine"),
            fields=[
                valkey.FieldDef("filename", "tag"),
                valkey.FieldDef("text", "text"),
            ],
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


def _decode_value(value: object, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


async def search_results(
    client: GlideClient,
    embedder: SentenceTransformerEmbedder,
    query_text: str,
    *,
    top_k: int = TOP_K,
    filter_filename: str | None = None,
) -> list[dict[str, str]]:
    """Return decoded KNN results from the CocoIndex-managed Valkey index."""
    query_vec = await embedder.embed(query_text)
    vec_blob = struct.pack(f"<{len(query_vec)}f", *query_vec.tolist())

    # Hybrid search: combine optional TAG filter with KNN vector search
    knn_query = build_knn_query(top_k, filter_filename)

    results = await ft.search(
        client,
        get_index_name(),
        knn_query,
        options=FtSearchOptions(
            params={"query_vec": vec_blob},
            return_fields=[
                ReturnField("text"),
                ReturnField("filename"),
                ReturnField("score"),
            ],
            dialect=2,
        ),
    )

    if not results or len(results) < 2:
        return []

    # FT.SEARCH returns [total_count, {key: {field: value}, ...}]
    docs = results[1]  # dict of {key: {field: value}}
    return [
        {
            "key": _decode_value(key),
            "score": _decode_value(
                fields.get(b"score", fields.get("score")),
                default="?",
            ),
            "filename": _decode_value(
                fields.get(b"filename", fields.get("filename")),
                default="<unknown>",
            ),
            "text": _decode_value(fields.get(b"text", fields.get("text"))),
        }
        for key, fields in docs.items()
    ]


async def verify(query_text: str) -> list[dict[str, str]]:
    """Run one deterministic search and fail when indexing produced no result."""
    embedder = SentenceTransformerEmbedder(EMBED_MODEL)
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)
    try:
        results = await search_results(client, embedder, query_text)
        assert results, f"No results returned for query: {query_text!r}"
        return results
    finally:
        await client.close()


async def query(initial_query: str | None = None) -> None:
    """Interactive or one-shot query mode."""
    embedder = SentenceTransformerEmbedder(EMBED_MODEL)
    config = valkey.create_client_config(VALKEY_HOST, VALKEY_PORT)
    client = await GlideClient.create(config)

    try:
        if initial_query is not None:
            await query_once(client, embedder, initial_query)
            # Demonstrate hybrid search (vector + TAG filter)
            print("\n\n--- Hybrid search (filtered to valkey.md only) ---")
            await query_once(
                client,
                embedder,
                initial_query,
                filter_filename=DEFAULT_FILTER_FILENAME,
            )
            return

        while True:
            q = input("\nEnter search query (or Enter to quit): ").strip()
            if not q:
                break
            await query_once(client, embedder, q)
    finally:
        await client.close()


async def query_once(
    client: GlideClient,
    embedder: SentenceTransformerEmbedder,
    query_text: str,
    *,
    top_k: int = TOP_K,
    filter_filename: str | None = None,
) -> None:
    """Print a KNN vector search against the Valkey index."""
    results = await search_results(
        client,
        embedder,
        query_text,
        top_k=top_k,
        filter_filename=filter_filename,
    )

    print(f"\nResults for: \"{query_text}\"\n{'=' * 60}")
    if not results:
        print("No results found.")
        return

    print(f"{format_result_count(len(results))}\n")
    for result in results:
        print(f"[score: {result['score']}] {result['filename']}")
        print(f"    {result['text'][:120]}...")
        print("---")


if __name__ == "__main__":
    initial = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    asyncio.run(query(initial))
```

## Step 4: Run the Pipeline

Build the index (one-shot catch-up):

```bash
.venv/bin/cocoindex update --reset -f main
```

This processes the Markdown fixtures, splits them into chunks, embeds them, and
declares the documents through the CocoIndex Valkey target.

## Step 5: Query the Index

```bash
.venv/bin/python main.py "what is vector search?"
```

The output includes matching fixture filenames and a distance score. Exact
scores can vary when the embedding model or library version changes:

```text
Results for: "what is vector search?"
============================================================
Returned results: <number>
[score: <distance>] markdown_files/valkey.md
```

## Step 6: Test Incremental Updates

Edit `markdown_files/valkey.md` and add a new section:

```markdown
## Persistence

Valkey supports RDB snapshots and AOF (Append-Only File) persistence.
RDB creates point-in-time snapshots at configured intervals.
AOF logs every write operation for maximum durability.
```

Re-run the pipeline:

```bash
.venv/bin/cocoindex update -f main
```

Only the modified file is re-chunked and re-embedded. Unchanged files are skipped entirely thanks to `memo=True` on `process_file`.

## Step 7: Live Mode

For continuous synchronization, run in live mode:

```bash
.venv/bin/cocoindex update -L main
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

```text
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
| Search behavior | Approximate | Exact |
| Memory | Higher (graph structure) | Lower |
| Best for | Larger collections and repeated search | Small datasets or testing |

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

## Operational Considerations

- **Embedding dimensions:** The index schema is created from the configured
  embedder. Changing the embedding model can change the vector dimensions and
  invalidates the existing target state, so treat model changes as an index
  migration.
- **Index algorithm:** HNSW is the default for approximate nearest-neighbor
  search. FLAT is useful when exact search is more important than index
  efficiency or the collection is small.
- **Incremental state:** CocoIndex stores lineage and memoization state
  separately from the Valkey documents. Keep that state durable in production
  so a restart can resume reconciliation instead of rebuilding blindly.
- **Valkey durability:** Configure RDB or AOF persistence according to the
  recovery requirements for the indexed data. The local Compose service is
  intentionally ephemeral.
- **Index lifecycle:** Coordinate schema, embedding-model, and source changes.
  Drop and rebuild the index when a schema or model migration cannot be
  reconciled incrementally.

## Production Deployment

The local sample intentionally uses SQLite and an unauthenticated
localhost-only Valkey service. For production, use a managed or self-hosted
Valkey deployment with ACL credentials, TLS, persistence, monitoring, and a
separate durable CocoIndex state store.

### Deployment Components

| Component | Responsibility |
|-----------|----------------|
| CocoIndex worker | Reads sources, chunks content, creates embeddings, and declares target state |
| Valkey with Search | Stores document hashes, maintains the vector index, and serves KNN queries |
| Durable CocoIndex state | Stores lineage and memoization state across worker restarts |
| Source storage | Provides the documents and change notifications consumed by the pipeline |

The worker and Valkey service can run in separate containers or on separate
hosts. Keep the Valkey endpoint private, restrict access with ACLs, and enable
TLS for traffic that leaves the local host or trusted network. Back up the
Valkey data and the CocoIndex state store together when both are needed for
recovery.

### Docker Compose Topology

The checked-in [`sample/docker-compose.yml`](sample/docker-compose.yml) is
intentionally local and ephemeral. A production deployment typically adds a
pipeline worker and a durable CocoIndex state store. The following is an
illustrative topology, not a drop-in deployment: provide the worker image,
secrets, ACL/TLS settings, and durable storage policy for your environment.

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.1
    volumes:
      - valkey_data:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  cocoindex-pipeline:
    build: .
    environment:
      COCOINDEX_DB: postgresql://cocoindex:${COCOINDEX_DB_PASSWORD}@postgres:5432/cocoindex
      VALKEY_HOST: valkey
      VALKEY_PORT: "6379"
      VALKEY_PASSWORD: ${VALKEY_PASSWORD}
    depends_on:
      valkey:
        condition: service_healthy
      postgres:
        condition: service_healthy
    command: [".venv/bin/cocoindex", "update", "-L", "main"]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: cocoindex
      POSTGRES_PASSWORD: ${COCOINDEX_DB_PASSWORD}
      POSTGRES_DB: cocoindex
    volumes:
      - cocoindex_state:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cocoindex -d cocoindex"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  valkey_data:
  cocoindex_state:
```

Keep provider-specific deployment instructions outside the default walkthrough.
The GLIDE connector accepts the generic host, port, password, and TLS settings:

```python
import os

from cocoindex.connectors import valkey

config = valkey.create_client_config(
    os.environ["VALKEY_HOST"],
    int(os.environ.get("VALKEY_PORT", "6379")),
    password=os.environ["VALKEY_PASSWORD"],
    use_tls=True,
)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COCOINDEX_DB` | `./cocoindex.db` | CocoIndex state store; use a durable backend for production |
| `COCOINDEX_INDEX_NAME` | `rag_documents` | Valkey Search index name |
| `VALKEY_HOST` | `localhost` | Valkey server host |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `VALKEY_PASSWORD` | unset | ACL or password authentication secret |
| `COCOINDEX_EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model identifier |

## Comparison with Other Vector Targets

| Feature | Valkey | Postgres (pgvector) | Qdrant |
|---------|--------|--------------------:|--------|
| Index management | Valkey Search | Database extension | Service-managed |
| Persistence | RDB/AOF configuration | Database-managed | Service-managed |
| Filtering | TAG and TEXT fields | SQL predicates | Payload filters |
| State | Valkey data plus CocoIndex state | Database data plus CocoIndex state | Service data plus CocoIndex state |
| Additional infrastructure | Valkey with Search | Postgres with pgvector | Qdrant service |

**When to choose Valkey:** You want the same datastore to serve cache, session,
and vector-search workloads, or your application already operates Valkey. A
different target may be a better fit when relational queries, an existing
vector-specific service, or database-managed persistence is the primary
requirement.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ImportError: glide` | Package not installed | `.venv/bin/pip install -e ".[test]"` |
| `Connection refused` | Valkey not running | Start Valkey container |
| `Unknown command FT.CREATE` | Search module not loaded | Use `valkey/valkey-bundle:9.1.1` |
| Empty search results | Index empty or wrong name | Check `FT._LIST` and re-run pipeline |
| `memo` not skipping files | Changed embedder model | Expected — model change invalidates cache |
| `NOAUTH Authentication required` | Valkey requires credentials | Pass the ACL password to `create_client_config()` |
| `cocoindex: command not found` | Virtual environment is not active | Use `.venv/bin/cocoindex` from the sample directory |

## Teardown

From the sample directory, remove the local service and SQLite state:

```bash
docker compose down -v
rm -rf cocoindex.db
```

---

[← 01 - Getting Started](01-getting-started.md) | [CocoIndex overview →](README.md)
