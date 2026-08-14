# vLLM Semantic Router Vector Store with Valkey

> Configure the Router's released Valkey vector-store backend rather than implementing vector storage in the client.

**Intermediate** · Go · ~10 min

**Who is this for:** Engineers enabling the Router's OpenAI-compatible vector-store feature with Valkey.

## Prerequisites

- Completed [01 - Semantic Cache](01-getting-started.md)
- vLLM Semantic Router v0.3.0

## Step 1: Add the backend configuration

Add this block under `global.stores` in the Router configuration.

```yaml
vector_store:
  enabled: true
  backend_type: valkey
  valkey:
    host: host.docker.internal
    port: 6379
    database: 0
    connect_timeout: 10
    collection_prefix: "vsr_vs_"
    metric_type: COSINE
    index_m: 16
    index_ef_construction: 200
```

## Step 2: Validate and start the Router

```bash
vllm-sr validate
vllm-sr serve --config config.yaml
```

The Router exposes its vector-store feature through its public API. Create and ingest vector stores through that API;
the Router, not Go application code, creates collections, embeds chunks, and writes them to Valkey.

## Configuration Reference

| Field | Required | Default in this guide | Description |
| --- | --- | --- | --- |
| `backend_type` | ✓ | `valkey` | Selects Valkey for Router vector stores. |
| `host` | ✓ | `host.docker.internal` | Valkey endpoint seen by the Router container. |
| `collection_prefix` | — | `vsr_vs_` | Namespace for Router-managed collections. |
| `metric_type` | — | `COSINE` | Similarity metric used by the backend. |
| `index_m` | — | `16` | HNSW graph connectivity setting. |
| `index_ef_construction` | — | `200` | HNSW build-time search scope. |

---

[← 01 - Semantic Cache](01-getting-started.md) | [03 - Agentic Memory Configuration →](03-agentic-memory.md)
