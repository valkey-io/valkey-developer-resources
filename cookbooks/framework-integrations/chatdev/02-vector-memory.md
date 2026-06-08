# Vector Memory with ChatDev + Valkey

> Store and retrieve agent memories using HNSW-indexed vector similarity search with automatic TTL expiry.

**Intermediate** · Python · ~20 min

This cookbook explores ValkeyMemory's vector search capabilities in depth: how embeddings are stored, how KNN retrieval works, how to tune similarity thresholds, and how TTL-based expiry manages memory growth.

## Index Schema

ValkeyMemory creates an FT index at initialization with this schema:

```
FT.CREATE chatdev_memory
  ON HASH
  PREFIX 1 "memory:"
  SCHEMA
    content_summary TEXT
    agent_role TAG
    timestamp NUMERIC
    embedding VECTOR HNSW 6 DIM 1536 DISTANCE_METRIC COSINE TYPE FLOAT32
```

The dimension is determined dynamically from a test embedding — if you use `text-embedding-3-small` (1536-dim) vs `text-embedding-ada-002` (1536-dim) vs a local 768-dim model, the index adapts automatically.

## Storing Memories

When an agent processes input, `ValkeyMemory.update()` executes:

```python
# 1. Embed the text
embedding_vec = self.embedding.get_embedding(text)          # List[float]
embedding_bytes = struct.pack(f"{len(embedding_vec)}f", *embedding_vec)  # float32 LE

# 2. Store as a Valkey Hash
key = f"memory:{uuid4().hex}"
self._client.hset(key, {
    "content_summary": text,
    "embedding": embedding_bytes,
    "agent_role": sanitize_tag(agent_role),
    "timestamp": str(time.time()),
})

# 3. Set TTL if configured
if self.config.ttl_seconds:
    self._client.expire(key, self.config.ttl_seconds)
```

## Retrieving Memories

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

Results are filtered by `similarity_threshold` and sorted by descending cosine similarity.

## Similarity Threshold

The `similarity_threshold` parameter controls minimum relevance:

```yaml
memories:
  - name: chatdev_memory
    top_k: 5
    similarity_threshold: 0.7   # Only return memories with ≥70% similarity
```

| Value | Behavior |
|-------|----------|
| `-1.0` | Return all top-k results (no filtering) |
| `0.0` | Return everything with non-negative similarity |
| `0.5` | Moderate filtering — good starting point |
| `0.8` | Strict — only highly relevant memories |

Cosine similarity is computed as `1.0 - distance` where distance comes from the HNSW index.

## Agent Role Filtering

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
```
(@agent_role:{coder})=>[KNN 3 @embedding $vec]
```

Each agent only sees its own memories. This uses Valkey's TAG field indexing for O(1) pre-filtering before the KNN search.

## TTL-Based Memory Expiry

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
|----------|----------------|
| Session memory | `3600` (1 hour) |
| Daily context | `86400` (1 day) |
| Project memory | `604800` (1 week) |
| Permanent knowledge | `null` (no expiry) |

Expired keys are removed by Valkey's built-in eviction and the FT index updates automatically.

## Embedding Providers

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

The local provider avoids API costs but uses 768 dimensions vs OpenAI's 1536.

## Inspecting the Index

```bash
# Index info (doc count, memory usage)
docker exec valkey valkey-cli FT.INFO chatdev_memory

# Search manually
docker exec valkey valkey-cli FT.SEARCH chatdev_memory "*" LIMIT 0 5

# Count documents
docker exec valkey valkey-cli FT.SEARCH chatdev_memory "*" LIMIT 0 0
# Returns total count without fetching docs
```

## Next Steps

- [03 - Production](03-production.md): TLS, ACL auth, and multi-process deployment
