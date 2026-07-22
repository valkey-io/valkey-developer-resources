# Memory Storage Backend

> Build a `ValkeyStorageBackend` that implements CrewAI's `StorageBackend` protocol — giving agents persistent, vector-searchable memory in Valkey.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who completed the getting-started cookbook and want to build a production-ready CrewAI memory backend with Valkey's HNSW vector search.

## How CrewAI Memory Works

CrewAI's unified `Memory` class handles embedding, scope inference, and consolidation.
It delegates storage to a pluggable `StorageBackend`. The backend receives pre-computed
`MemoryRecord` objects (with embeddings already populated) and must implement save, search, delete, and discovery operations.

```text
Memory.remember("fact") → LLM infers scope/categories → embed → StorageBackend.save([record])
Memory.recall("query")  → embed query → StorageBackend.search(embedding) → rank → return
```

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module
- `pip install valkey-glide==2.5.0 crewai==1.15.5 numpy==2.2.6`

## Step 1: The StorageBackend Protocol

CrewAI's `StorageBackend` (at `crewai.memory.storage.backend`) defines these key methods:

| Method | Purpose |
|--------|---------|
| `save(records)` | Persist a list of `MemoryRecord` objects |
| `search(query_embedding, ...)` | Find records by vector similarity with optional filters |
| `delete(...)` | Remove records by ID, scope, or category |
| `get_record(record_id)` | Retrieve a single record |
| `count(scope_prefix)` | Count records in a scope |
| `reset(scope_prefix)` | Delete all records (optionally scoped) |

Each `MemoryRecord` has: `id`, `content`, `scope`, `categories`, `metadata`, `importance`, `created_at`, `last_accessed`, `embedding`, `source`, `private`.

## Step 2: Index Schema

We store records as HASH keys with a vector index for similarity search:

```python
from glide import ft, VectorField
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType, DistanceMetricType, FtCreateOptions, NumericField, TagField,
    VectorAlgorithm, VectorFieldAttributesHnsw, VectorType,
)

INDEX_NAME = "crewai_memory_idx"
KEY_PREFIX = "crewai:mem:"

hnsw = VectorFieldAttributesHnsw(
    dimensions=384,  # Match your embedding model
    distance_metric=DistanceMetricType.COSINE,
    type=VectorType.FLOAT32,
)
schema = [
    TagField("scope"),
    TagField("categories", separator="|"),
    NumericField("importance"),
    NumericField("created_at"),
    VectorField("embedding", VectorAlgorithm.HNSW, hnsw),
]
await ft.create(
    client, INDEX_NAME, schema,
    FtCreateOptions(DataType.HASH, prefixes=[KEY_PREFIX]),
)
```

**Why TAG not TEXT?** TAG fields do exact-match filtering (`@scope:{/project/alpha}`). Scopes and categories are structured paths — we don't need tokenization or stemming. TAG is faster and simpler.

## Step 3: Serialize Records to HASH

```python
import json
import struct
from crewai.memory.types import MemoryRecord

def record_to_hash(record: MemoryRecord) -> dict[str, str | bytes]:
    embedding_bytes = b""
    if record.embedding:
        embedding_bytes = struct.pack(f"<{len(record.embedding)}f", *record.embedding)
    return {
        "id": record.id,
        "content": record.content,
        "scope": record.scope,
        "categories": "|".join(record.categories),
        "metadata_json": json.dumps(record.metadata),
        "importance": str(record.importance),
        "created_at": str(record.created_at.timestamp()),
        "last_accessed": str(record.last_accessed.timestamp()),
        "embedding": embedding_bytes,
        "source": record.source or "",
        "private": "1" if record.private else "0",
    }
```

Embeddings are packed as FLOAT32 bytes — the format `FT.SEARCH` expects for KNN queries.

## Step 4: Vector Search with Filters

```python
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions

# All 32 token separator characters from RediSearch/valkey-search ToksepMap_g
_TAG_SPECIAL = set(' \t,./(){}[]:;~!@#$%^&*-=+|\'`"<>?\\')

def _sanitize_tag_value(value: str) -> str:
    """Escape TAG-special characters to prevent query injection."""
    return "".join(f"\\{ch}" if ch in _TAG_SPECIAL else ch for ch in value)

async def search(client, query_embedding, scope=None, categories=None, limit=10):
    filters = []
    if scope:
        escaped = _sanitize_tag_value(scope)
        filters.append(f"@scope:{{{escaped}}}")
    if categories:
        sanitized = [_sanitize_tag_value(c) for c in categories]
        joined = "|".join(sanitized)
        filters.append(f"@categories:{{{joined}}}")

    filter_str = " ".join(filters) if filters else "*"
    query = f"({filter_str})=>[KNN {limit} @embedding $query_vec AS score]"
    vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

    count, docs = await ft.search(
        client, INDEX_NAME, query,
        FtSearchOptions(params={"query_vec": vec_bytes}, dialect=2),
    )

    results = []
    for key, fields in docs.items():
        score = float(fields[b"score"])
        similarity = 1.0 - score  # COSINE distance → similarity
        record = hash_to_record(fields)
        results.append((record, similarity))
    return sorted(results, key=lambda x: x[1], reverse=True)
```

The `(filter)=>[KNN ...]` syntax combines pre-filtering with vector search in a single atomic operation.

## Step 5: Sync Wrappers

CrewAI calls `StorageBackend` methods synchronously, but GLIDE is async. Use a persistent background event loop:

```python
import asyncio
import threading

class ValkeyStorageBackend:
    def _get_loop(self):
        if not hasattr(self, "_loop") or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
            self._loop_thread.start()
        return self._loop

    def _run_sync(self, coro):
        loop = self._get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)

    def save(self, records):
        self._run_sync(self.asave(records))

    def search(self, query_embedding, **kwargs):
        return self._run_sync(self.asearch(query_embedding, **kwargs))
```

This avoids "event loop already running" errors when CrewAI calls from various contexts.

## Step 6: The Complete Implementation

See [`sample/valkey_storage.py`](sample/valkey_storage.py) for the full ~300-line implementation covering all 14 protocol methods. Key points:

- Lazy client initialization (connects on first use)
- `FT.INFO` for fast total count
- TAG-based scope/category filtering
- `SCAN` + `DELETE` for reset
- Explicit `close()` for connection cleanup

## How It Works

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| Create index | `FT.CREATE ... ON HASH PREFIX crewai:mem:` | One-time index setup |
| Store record | `HSET crewai:mem:{id} content ... embedding <bytes>` | Persist memory |
| Search | `FT.SEARCH idx "(@scope:{...})=>[KNN k @embedding $vec]"` | Filtered vector search |
| Count | `FT.INFO idx` → `num_docs` | Fast record count |
| Delete | `DEL crewai:mem:{id}` | Remove by key |
| Reset | `FT.DROPINDEX` + `SCAN`/`DEL` + recreate | Full cleanup |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `host` | No | `localhost` | Valkey hostname |
| `port` | No | `6379` | Valkey port |
| `embedding_dim` | ✓ | `384` | Must match your embedding model's output dimension |
| `index_name` | No | `crewai_memory_idx` | FT.CREATE index name |
| `key_prefix` | No | `crewai:mem:` | HASH key prefix |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Agent Memory in Action →](03-agent-memory.md)
