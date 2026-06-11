# Agentic Memory Backend with Valkey

> Back the vLLM Semantic Router's agentic memory with Valkey — per-user vector recall, hybrid reranking, atomic access tracking, scoped deletion, and TLS for production.

**Advanced** · Go / YAML · ~20 min

Agentic memory is what lets the router remember facts about a user across conversations and inject them into future prompts. [PR #1739](https://github.com/vllm-project/semantic-router/pull/1739) adds Valkey (with the Search module) as a full memory backend alongside Milvus, implementing the complete `Store` interface: store, retrieve by vector similarity, get, update, list, forget, and forget-by-scope. This cookbook covers that backend and the production concerns — TLS, hybrid search, and concurrency-safe access counts.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

## Why Valkey for Memory?

| Concern | Valkey | Milvus |
|---------|--------|--------|
| Deployment | Single binary with the Search module | Requires etcd, MinIO/S3, optional Pulsar |
| Best for | Dev/test, existing Valkey infra, small-to-medium workloads | Large-scale production, billions of vectors |
| Vector index | HNSW via `FT.CREATE` | HNSW, IVF variants, and more |

Memory similarity thresholds are portable across backends: the Valkey backend maps cosine distance to similarity with `1 - d/2`, the same `[0, 1]` range Milvus returns directly.

## Prerequisites

- Completed [01](01-getting-started.md) and [02](02-vector-store.md)
- **Go 1.24+** (for the sample)
- **Docker or Podman**
- **Valkey 8.0+ with the Search module** — `valkey/valkey-bundle`
- The `github.com/valkey-io/valkey-glide/go/v2` client (pulled by the sample's `go.mod`)

## Step 1: Configure the Memory Backend

Select Valkey under `global.stores.memory`, matching the `MemoryValkeyConfig` schema:

```yaml
global:
  stores:
    memory:
      enabled: true
      backend: valkey            # "" or "milvus" → Milvus (default); "valkey" → Valkey
      auto_store: true
      valkey:
        host: localhost
        port: 6379
        database: 0
        password: ""             # set for production
        timeout: 10              # connection/request timeout in seconds
        collection_prefix: "mem:"
        index_name: mem_idx
        dimension: 384           # must match the embedding model
        metric_type: COSINE       # COSINE | L2 | IP
        index_m: 16               # HNSW links per node
        index_ef_construction: 256  # HNSW build-time search width
        tls_enabled: false        # enable TLS for production
        tls_ca_path: ""          # PEM CA cert; empty = system trust store
        tls_insecure_skip_verify: false  # development only — never in production
      embedding_model: bert
      default_retrieval_limit: 5
      default_similarity_threshold: 0.70
      hybrid_search: true
      hybrid_mode: rerank
      adaptive_threshold: true
```

## Step 2: The Memory Index Schema

The memory store creates a richer index than the cache or vector store, with fields for scoping and ranking:

```text
FT.CREATE mem_idx ON HASH PREFIX 1 mem: SCHEMA
  id          TAG
  user_id     TAG
  project_id  TAG
  memory_type TAG
  content     TEXT
  source      TAG
  embedding   VECTOR HNSW 10 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE M 16 EF_CONSTRUCTION 256
  created_at  NUMERIC SORTABLE
  updated_at  NUMERIC
  access_count NUMERIC
  importance  NUMERIC
```

`user_id` and `project_id` TAG fields enforce per-user and per-project isolation; `created_at` is `SORTABLE` so `List` can page in chronological order without an in-memory sort.

## Step 3: Retrieval, Reranking, and Access Tracking

A retrieval runs a user-scoped KNN search, then optionally reranks:

```text
FT.SEARCH mem_idx "(@user_id:{u1})=>[KNN 40 @embedding $BLOB AS vector_distance]"
  PARAMS 2 BLOB <query-embedding>
  RETURN 5 id content memory_type metadata vector_distance
  LIMIT 0 40
  DIALECT 2
```

After the vector search the backend can apply **hybrid reranking** (BM25 + n-gram fused with the vector score, when `hybrid_search: true`) and an **adaptive threshold** before truncating to the requested limit.

Crucially, access tracking is concurrency-safe. When memories are retrieved, the backend increments the access count atomically and updates the timestamp:

```text
HINCRBY mem:<id> access_count 1
HSET    mem:<id> updated_at <now>
```

`access_count` lives **only** as a top-level HASH field, never inside the `metadata` JSON blob. This avoids a read-modify-write race where two concurrent retrievals could clobber each other's counts. The metadata JSON holds only immutable-per-write fields (`user_id`, `project_id`, `source`, `importance`, `last_accessed`).

## Step 4: Atomic Store and Scoped Deletion

`Store` uses `HSETNX` on the `id` field as an atomic reservation — if the key already exists it returns "already exists" without overwriting, avoiding a check-then-set race:

```text
HSETNX mem:<id> id <id>      # false if it already exists → duplicate error
HSET   mem:<id> <all fields> # only runs if the reservation succeeded
```

`ForgetByScope` deletes all memories matching a scope (`user_id`, optional `project_id`, optional types) in pages, re-querying at offset 0 each round since the prior `DEL` shifts results forward:

```text
FT.SEARCH mem_idx "@user_id:{u1} @memory_type:{semantic | procedural}" RETURN 1 id LIMIT 0 1000
DEL <found keys>
# repeat until no matches remain
```

## Step 5: Enable TLS for Production

For production, terminate the connection over TLS. The backend wires the GLIDE client with a CA certificate:

```yaml
      valkey:
        host: valkey.prod.svc.cluster.local
        port: 6380
        password: "${VALKEY_PASSWORD}"
        tls_enabled: true
        tls_ca_path: "/etc/valkey/certs/ca.pem"  # PEM-encoded CA cert
        tls_insecure_skip_verify: false           # keep false in production
```

When `tls_ca_path` is empty and TLS is enabled, the system trust store is used. `tls_insecure_skip_verify: true` disables certificate verification and is logged as a warning — only use it against a local test server, never in production.

## Step 6: Run the Memory Sample

The [`sample/`](sample/) program stores a few per-user memories, retrieves them by semantic query (showing user isolation), updates one, lists them in order, and deletes by scope. It uses deterministic stub embeddings so it runs without a GPU.

```bash
cd sample
go run . memory
```

Expected output:

```text
✓ Connected to Valkey at localhost:6379
== vLLM Semantic Router — Valkey agentic memory demo ==
✓ Created index mem_idx
✓ Stored 3 memories for user "alice"
→ Retrieve: "what does the user prefer?"
  [0.64] alice's preferred programming language is Go
✓ User isolation: "bob" sees 0 of alice's memories
✓ Access count incremented to 1 after retrieval
✓ ForgetByScope deleted 3 memories for "alice"
✓ Cleaned up index
```

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
|-----------|---------------|-------|
| Ensure index | `FT.INFO mem_idx` then `FT.CREATE ...` | Created once; skipped if present |
| Store (atomic) | `HSETNX mem:<id> id <id>` + `HSET ...` | `HSETNX` prevents duplicate overwrite |
| Retrieve | `FT.SEARCH "(@user_id:{...})=>[KNN ...]"` | User-scoped, then hybrid rerank + threshold |
| Access tracking | `HINCRBY mem:<id> access_count 1` | Atomic; not stored in metadata JSON |
| List | `FT.SEARCH @user_id:{...} SORTBY created_at DESC` | Total count from the FT.SEARCH header |
| Forget | `DEL mem:<id>` | — |
| Forget by scope | paged `FT.SEARCH` + batch `DEL` | Re-query offset 0 each round |

Cleanup uses cursor-based `SCAN` + `DEL` (never `KEYS`) so it is safe to run against a production server.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `valkey memory already exists` | Expected when storing a duplicate ID — `Store` is non-overwriting by design. Use `Update` to modify an existing memory. |
| Retrieval returns other users' data | Confirm `user_id` is set on every memory; the backend filters by `@user_id:{...}` and isolation depends on it. |
| `failed to load TLS CA certificate` | Check `tls_ca_path` points to a readable PEM file, or leave it empty to use the system trust store. |
| Access counts look wrong under load | Ensure you read `access_count` from the HASH field, not the metadata JSON — only the HASH field is authoritative. |
| `List` returns fewer than expected | `List` caps at 100 results per call; page with the `limit` option. |
| Switching from Milvus loses data | Backends do not auto-migrate. Export from Milvus and re-import before switching `backend`. |

---

For full deployment details — Docker, Kubernetes StatefulSet, sizing, and persistence — see the router's [Valkey Agentic Memory guide](https://github.com/vllm-project/semantic-router/blob/main/website/docs/installation/valkey-memory.md).
