# Vector Memory with ChatDev + Valkey

> Store and retrieve agent memories using HNSW-indexed vector similarity search with automatic TTL expiry.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who have completed [01 - Getting Started](01-getting-started.md) and want to
understand ValkeyMemory's retrieval, filtering, and TTL mechanics in depth.

This cookbook explores ValkeyMemory's vector search capabilities in depth: how embeddings are stored, how KNN retrieval
works, how to tune similarity thresholds, and how TTL-based expiry manages memory growth. All code in this cookbook is
demonstrated end-to-end in the standalone [`sample/`](sample/) — run `python sample/quick_start.py` to see it live
against real Valkey.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Valkey running on `127.0.0.1:6379` with Search loaded)
- Docker or Podman installed
- Python 3.11+
- No API key required to follow along with the standalone sample (see [01](01-getting-started.md#try-it-the-runnable-sample))

## Step 1: Index Schema

ValkeyMemory creates an FT index at initialization with this schema:

```text
FT.CREATE chatdev_memory
  ON HASH
  PREFIX 1 "memory:"
  SCHEMA
    content_summary TEXT
    agent_role TAG
    timestamp NUMERIC
    embedding VECTOR HNSW 6 DIM 1536 DISTANCE_METRIC COSINE TYPE FLOAT32
```

The dimension is determined dynamically from a test embedding — if you use `text-embedding-3-small` (1536-dim) vs
`text-embedding-3-large` (3072-dim) vs a local 768-dim model, the index adapts automatically. The standalone sample's
default embedding provider is 64-dimensional and probed the same way (see `sample/embeddings.py` and `_ensure_index()`
in `sample/valkey_memory.py`).

## Step 2: Storing Memories

> **Note:** The snippets below show ValkeyMemory's internal implementation for reference — they are not standalone
> runnable code as written. The fully runnable, tested equivalent lives in [`sample/valkey_memory.py`](sample/valkey_memory.py).
> Use `sample/quick_start.py` or the workflow YAML to interact with ValkeyMemory.

When an agent processes input, `ValkeyMemory.update()` executes:

```python
# 1. Embed the text
embedding_vec = self.embedding.get_embedding(text)          # List[float]
embedding_bytes = struct.pack(f"<{len(embedding_vec)}f", *embedding_vec)  # float32 LE

# 2. Store as a Valkey Hash
key = f"{self.config.key_prefix}{uuid.uuid4().hex}"
self._client.hset(key, {
    "content_summary": text,
    "embedding": embedding_bytes,
    "agent_role": sanitize_tag(agent_role),
    "timestamp": str(time.time()),
})

# 3. Set TTL if configured
if self.config.ttl_seconds is not None:
    self._client.expire(key, self.config.ttl_seconds)
```

> **Note:** `HSET` and `EXPIRE` are two separate commands. If the process crashes between them, the key persists
> without a TTL. For critical TTL guarantees, consider wrapping both in a transaction or Lua script. The standalone
> sample reproduces this exact two-step, non-atomic sequence — see `test_update_calls_hset_then_expire_separately`
> in `sample/test_valkey_memory.py`, which asserts the call order.

### TAG Sanitization

`agent_role` values are sanitized before being embedded in a Valkey Search TAG field, since TAG queries use `,{}|<>`
and whitespace as syntactic delimiters. ValkeyMemory replaces each of these characters — comma, `{`, `}`, `|`, `<`,
`>`, space, tab, newline, and carriage return — with `_`:

```python
_TAG_UNSAFE_CHARS = ",{}|<> \t\n\r"

def sanitize_tag(value: str) -> str:
    return "".join("_" if ch in _TAG_UNSAFE_CHARS else ch for ch in value)
```

For example, an `agent_role` of `"team,lead"` is stored and queried as `team_lead`.

## Step 3: Retrieving Memories

`ValkeyMemory.retrieve()` runs a KNN vector search:

```python
# Build the FT.SEARCH query
ft_query = "(@agent_role:{coder})=>[KNN 3 @embedding $vec]"

# Execute search
results = ft.search(client, index_name, ft_query, FtSearchOptions(
    params={"vec": query_bytes},
    dialect=2,
))
```

When no `agent_role` filter is needed, the same method builds an unfiltered query instead:

```python
ft_query = "*=>[KNN 3 @embedding $vec]"
```

Results are filtered by `similarity_threshold` and sorted by descending cosine similarity.

## Step 4: Similarity Threshold

The `similarity_threshold` parameter controls minimum relevance:

```yaml
memories:
  - name: chatdev_memory
    top_k: 5
    similarity_threshold: 0.7   # Only return memories with ≥70% similarity
```

| Value | Behavior |
| --- | --- |
| `-1.0` | Return all top-k results (no filtering — any negative value disables the threshold check) |
| `0.0` | Return everything with non-negative similarity |
| `0.5` | Moderate filtering — good starting point |
| `0.8` | Strict — only highly relevant memories |

Cosine similarity is computed as `1.0 - distance` where distance comes from the HNSW index.

## Step 5: Agent Role Filtering

ValkeyMemory scopes search by `agent_role` using TAG field filtering:

```yaml
# In a multi-agent workflow:
nodes:
  - id: coder
    config:
      memories:
        - name: shared_memory
          read: true
          write: true
  - id: reviewer
    config:
      memories:
        - name: shared_memory
          read: true
          write: true
```

When the `coder` agent retrieves memories, the query is:

```text
(@agent_role:{coder})=>[KNN 3 @embedding $vec]
```

Each agent only sees its own memories. This uses Valkey's TAG field indexing for pre-filtering before the KNN search.

## Step 6: TTL-Based Memory Expiry

Configure `ttl_seconds` to automatically expire old memories:

```yaml
memory:
  - name: session_memory
    type: valkey
    config:
      host: localhost
      port: 6379
      index_name: session_idx
      ttl_seconds: 3600          # Memories expire after 1 hour
      embedding:
        provider: openai
        model: text-embedding-3-small
        api_key: ${API_KEY}
```

| Use Case | Recommended TTL |
| --- | --- |
| Session memory | `3600` (1 hour) |
| Daily context | `86400` (1 day) |
| Project memory | `604800` (1 week) |
| Permanent knowledge | `null` (no expiry) |

Expired keys are removed by Valkey's built-in eviction and the FT index updates automatically.

## Step 7: Embedding Providers

ValkeyMemory supports any provider configured via `EmbeddingConfig`:

```yaml
# OpenAI (default)
embedding:
  provider: openai
  model: text-embedding-3-small
  api_key: ${API_KEY}

# Local sentence-transformers
embedding:
  provider: local
  params:
    model_path: "sentence-transformers/all-MiniLM-L6-v2"
    device: cpu
```

The local provider avoids API costs but uses 384 dimensions vs OpenAI's 1536.

The standalone sample takes the same "no external dependency by default" approach: `sample/embeddings.py`'s
`LocalDeterministicEmbedding` needs no network access or API key and produces 64-dimensional vectors, probed at
runtime the same way ValkeyMemory probes any configured provider. It also documents (but does not install by
default) an `OpenAIEmbedding` and an `OllamaEmbedding` provider for readers who want real semantic similarity —
see [Configuration Reference](#configuration-reference) below.

## Step 8: Inspecting the Index

```bash
# Index info (doc count, memory usage)
docker exec valkey valkey-cli FT.INFO chatdev_memory

# Search manually
docker exec valkey valkey-cli FT.SEARCH chatdev_memory "*=>[KNN 5 @embedding \$vec]" PARAMS 2 vec "<16-byte-blob>" DIALECT 2

# Count documents (via FT.INFO — see note below)
docker exec valkey valkey-cli FT.INFO chatdev_memory
# Look for the "num_docs" field in the output
```

> **Note on counting documents:** Because this schema has a mandatory VECTOR field, a bare `FT.SEARCH chatdev_memory "*"`
> query (with no `KNN` clause) is rejected by the Search module with `Invalid: query string syntax` — every query against
> a VECTOR-indexed schema must include a KNN clause. The reliable way to get a document count is the `num_docs` field
> from `FT.INFO`, which is what `count_memories()` uses in the standalone sample (`sample/valkey_memory.py`).

## How It Works

| Component | Role |
| --- | --- |
| `valkey-glide-sync` | Synchronous client issuing `HSET`, `EXPIRE`, `FT.CREATE`, `FT.SEARCH`, `FT.INFO` |
| HNSW index | Approximate-nearest-neighbor structure over the `embedding` VECTOR field |
| TAG pre-filter | `(@agent_role:{role})` narrows the candidate set before KNN runs |
| `similarity_threshold` | Client-side post-filter applied after `1.0 - distance` is computed |
| TTL (`EXPIRE`) | Optional, separate call after `HSET` — not atomic with the write |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | — | `localhost` | Valkey server address |
| `port` | — | `6379` | Valkey server port |
| `index_name` | — | `memory_index` | FT index name |
| `key_prefix` | — | `memory:` | Hash key prefix |
| `ttl_seconds` | — | `None` | Per-entry TTL in seconds (`None` = no expiry) |
| `top_k` | — | `3` | Number of KNN results to request |
| `similarity_threshold` | — | `-1.0` | Minimum similarity to keep a result; negative disables filtering |
| `embedding.provider` | ✓ | — | `openai`, `local`, or (sample-only) `ollama` |
| `embedding.model` | — | provider-specific | Embedding model name |
| `embedding.api_key` | — | `None` | Required for the OpenAI provider |

## Next Steps

- [03 - Production](03-production.md): TLS, ACL auth, and multi-process deployment

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production →](03-production.md)
