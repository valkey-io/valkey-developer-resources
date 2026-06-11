# Semantic Cache Backend with Valkey

> Configure the vLLM Semantic Router to use Valkey as its semantic cache so repeated or paraphrased prompts return instantly — without hitting the LLM. HNSW vector index, KNN lookup, and TTL eviction via `valkey-glide`.

**Beginner** · Go / YAML · ~15 min

The [vLLM Semantic Router](https://github.com/vllm-project/semantic-router) sits in front of your LLM endpoints and short-circuits requests it has seen before. Its semantic cache embeds each prompt, stores the response, and on the next request runs a vector similarity search: if a past prompt is close enough (cosine similarity above a threshold), the cached response is returned and the LLM is never called. This cookbook configures Valkey — with the Search module — as that cache backend.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

## How It Works

```text
Request arrives at the router
  → embed the prompt (candle BERT/Qwen3/Gemma)
  → FT.SEARCH KNN against the cache index in Valkey
  → HIT  (similarity ≥ threshold): return cached response, skip the LLM
  → MISS: forward to the LLM, then HSET the response + embedding for next time
```

Valkey stores each entry as a HASH (`request_id`, `model`, `query`, `response_body`, `embedding`, `timestamp`) and indexes the `embedding` field with HNSW so KNN lookups stay sub-millisecond.

## Prerequisites

- **Go 1.24+** (only for running the standalone sample in this cookbook)
- **Docker or Podman** (to run Valkey)
- **Valkey with the Search module** — the `valkey/valkey-bundle` image ships it
- The `github.com/valkey-io/valkey-glide/go/v2` client (pulled automatically by the sample's `go.mod`)
- For the full router: a built vLLM Semantic Router with its candle embedding bindings and at least one vLLM endpoint (see the [router docs](https://github.com/vllm-project/semantic-router)). This cookbook focuses on the Valkey cache layer.

## Step 1: Start Valkey with the Search Module

The Search module provides the `FT.CREATE` / `FT.SEARCH` commands the cache relies on. Use the bundle image, which includes it.

```bash
# Docker
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
# Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

Confirm the module is loaded:

```bash
# Docker
docker exec valkey-search valkey-cli MODULE LIST
# should list a module named "search"
```

```bash
# Podman
podman exec valkey-search valkey-cli MODULE LIST
# should list a module named "search"
```

## Step 2: Configure the Router's Cache Backend

In the router's `config.yaml`, select Valkey under `global.stores.semantic_cache`. The block below mirrors the schema added in [PR #1540](https://github.com/vllm-project/semantic-router/pull/1540).

```yaml
global:
  stores:
    semantic_cache:
      enabled: true
      backend_type: valkey      # select Valkey (alongside memory, redis, milvus, hybrid)
      similarity_threshold: 0.85 # min cosine similarity for a cache HIT (0.0–1.0)
      ttl_seconds: 3600          # entries expire after 1 hour
      embedding_model: bert      # bert | qwen3 | gemma | mmbert | multimodal
      valkey:
        connection:
          host: localhost
          port: 6379
          database: 0
          password: ""           # set for production; leave empty for local dev
          timeout: 5             # client request timeout in seconds
          tls:
            enabled: false       # enable for production
        index:
          name: semantic_cache_idx
          prefix: "doc:"         # key prefix for cached HASH documents
          vector_field:
            name: embedding
            dimension: 384        # auto-detected from the embedding model at runtime
            metric_type: COSINE   # COSINE | L2 | IP
          index_type: HNSW        # HNSW (recommended) or FLAT
          params:
            M: 16                 # HNSW links per node (higher = better recall, more RAM)
            efConstruction: 64    # build-time candidate list (higher = better quality, slower)
        search:
          topk: 1                 # only the nearest neighbor is needed for a cache lookup
        development:
          drop_index_on_startup: false  # true wipes the index on boot (dev only)
          auto_create_index: true       # create the index if it does not exist
          verbose_errors: true
```

A few values worth calling out:
- **`similarity_threshold: 0.85`** — the router converts Valkey's cosine distance `d` to a similarity score with `1 - d/2`, so the value is in `[0, 1]`. Raise it for stricter matches, lower it to cache more aggressively.
- **`dimension: 384`** — this matches BERT (`all-MiniLM-L6-v2`). The router auto-detects the real dimension from the embedding model at index-creation time, so it stays correct for Qwen3 (1024) or Gemma (768).
- **`topk: 1`** — a cache only needs the single closest match.

## Step 3: Understand the Index the Router Creates

On startup the router issues an `FT.CREATE` equivalent to this (HNSW branch):

```text
FT.CREATE semantic_cache_idx ON HASH PREFIX 1 doc: SCHEMA
  request_id TAG
  model      TAG
  query      TEXT
  embedding  VECTOR HNSW 10 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE M 16 EF_CONSTRUCTION 64
  timestamp  NUMERIC
```

The `VECTOR HNSW 10` token means "10 parameters follow" (`TYPE`, `DIM`, `DISTANCE_METRIC`, `M`, `EF_CONSTRUCTION` as key/value pairs). `request_id` and `model` are TAG fields so the router can look up a specific pending entry exactly, while `embedding` powers the similarity search.

> The runnable [`sample/`](sample/) uses `DIM 256` deterministic stub embeddings so it runs without a model; the real router auto-detects the model's dimension (384 for BERT, 768 for Gemma, 1024 for Qwen3) at index-creation time.

## Step 4: Run the Cache Sample

The [`sample/`](sample/) directory contains a small Go program that talks to Valkey the same way the router's cache does: it creates the index, stores an entry, then runs a KNN search with a paraphrased query to show a cache hit. It uses deterministic stub embeddings (no GPU or model download required) so you can see the Valkey mechanics end to end.

```bash
cd sample
go run . cache
```

Expected output:

```text
✓ Connected to Valkey at localhost:6379
== vLLM Semantic Router — Valkey cache demo ==
✓ Created index semantic_cache_idx
✓ Stored entry for: "What is the capital of France?"
→ Searching with paraphrase: "What's the capital city of France?"
✓ Cache HIT (similarity 0.89 ≥ 0.85)
  cached response: The capital of France is Paris.
✓ Cleaned up index
```

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
|-----------|---------------|-------|
| Create cache index | `FT.CREATE ... SCHEMA ... embedding VECTOR HNSW ...` | One index per cache, created once on startup |
| Store a response | `HSET doc:<id> request_id ... query ... embedding <bytes>` then `EXPIRE` | Embedding stored as little-endian FLOAT32 bytes |
| Cache lookup | `FT.SEARCH ... "*=>[KNN 1 @embedding $vec AS vector_distance]"` | `vector_distance` aliases the KNN score |
| Find pending entry | `FT.SEARCH ... "@request_id:{<escaped id>}"` | TAG lookup for the exact request |
| TTL eviction | `EXPIRE doc:<id> <ttl_seconds>` | Valkey removes stale entries automatically |

The similarity returned to the threshold check is computed as `1 - vector_distance/2` for cosine, mapping Valkey's `[0, 2]` cosine distance onto a `[0, 1]` similarity.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ERR unknown command 'FT.CREATE'` | The Search module is not loaded. Use `valkey/valkey-bundle`, not plain `valkey/valkey`, and verify with `MODULE LIST`. |
| Cache always misses | Lower `similarity_threshold`, or confirm the same `embedding_model` is used for store and lookup — different models produce incomparable vectors. |
| `connection refused` | Ensure Valkey is running and the `host`/`port` match. Raise `timeout` if you are not on localhost. |
| Entries never expire | Confirm `ttl_seconds` is greater than 0; a value of 0 disables caching for that call. |
| Dimension mismatch on insert | The index dimension is fixed at creation. If you switch embedding models, drop and recreate the index (`FT.DROPINDEX semantic_cache_idx`). |

---

[02 - Vector Store Backend →](02-vector-store.md)
