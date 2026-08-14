# vLLM Semantic Router Agentic Memory with Valkey

> Configure the Router to store and retrieve its agentic memory through Valkey.

**Advanced** · Go · ~10 min

**Who is this for:** Engineers who want Router-managed cross-session memory backed by Valkey Search.

## Prerequisites

- Completed [01 - Semantic Cache](01-getting-started.md)
- vLLM Semantic Router v0.3.0

## Step 1: Add the memory backend

Add this block under `global.stores` in the Router configuration.

```yaml
memory:
  enabled: true
  backend: valkey
  auto_store: true
  embedding_model: bert
  default_retrieval_limit: 5
  default_similarity_threshold: 0.70
  valkey:
    host: host.docker.internal
    port: 6379
    database: 0
    timeout: 10
    collection_prefix: "mem:"
    index_name: mem_idx
    dimension: 384
    metric_type: COSINE
    index_m: 16
    index_ef_construction: 256
    tls_enabled: false
    tls_ca_path: ""
    tls_insecure_skip_verify: false
```

## Step 2: Validate and run the Router

```bash
vllm-sr validate
vllm-sr serve --config config.yaml
```

When memory is enabled for a Router decision, the Router performs retrieval and persistence. Client code sends normal
requests through the Router; it does not create memory indexes or update memory hashes directly.

## Configuration Reference

| Field | Required | Value in this guide | Description |
| --- | --- | --- | --- |
| `backend` | ✓ | `valkey` | Selects Valkey for Router memory. |
| `auto_store` | — | `true` | Lets the Router persist eligible memories. |
| `default_similarity_threshold` | — | `0.70` | Default threshold for Router memory retrieval. |
| `collection_prefix` | — | `mem:` | Namespace for Router-managed memory records. |
| `index_name` | — | `mem_idx` | Router-managed Valkey Search index name. |
| `tls_enabled` | — | `false` | Enable with authentication and certificate settings outside local development. |

---

[← 02 - Vector Store Configuration](02-vector-store.md)
