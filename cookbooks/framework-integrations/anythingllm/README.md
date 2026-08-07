# AnythingLLM + Valkey Vector Database Cookbook

> Use Valkey as the vector database backend for [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm)
> (Mintplex Labs), storing and retrieving document embeddings with per-workspace namespace isolation
> via `VECTOR_DB=valkey`.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Configure `VECTOR_DB=valkey`, understand the storage model, and run your first KNN search |
| [Vector Search & Retrieval](./02-vector-search.md) | Intermediate | KNN with bound parameters, similarity scoring, threshold filtering, and pinned-source exclusion |
| [Production Operations](./03-production.md) | Advanced | TLS/auth, dimension-mismatch guard, namespace lifecycle, bounded cleanup, and full reset |

## Prerequisites

- **Valkey 8+** with the `valkey-search` module (`valkey/valkey-bundle`)
- **Docker** and **Docker Compose**
- **Node.js 18+**
- **`@valkey/valkey-glide` 2.5.0** (installed via `npm install`)

## How AnythingLLM Uses Valkey

AnythingLLM's Valkey provider stores document chunks as HASH keys with FLOAT32 vectors, one HNSW index per workspace namespace:

- **FT.CREATE** — Create a COSINE HNSW index (`allm_idx_{ns}`) over prefix `allm:{ns}:`
- **HSET** — Store a chunk: `vector` (FLOAT32 bytes) + `text` + `metadata` (JSON)
- **FT.SEARCH** — KNN query with bound `$BLOB` parameter (no string interpolation)
- **FT.DROPINDEX** + **SCAN/DEL** — Namespace deletion with orphan key sweep
- **FT.INFO** — Dimension guard and vector count

## Upstream Status

> **Note:** The Valkey vector database provider is introduced in
> PR [Mintplex-Labs/anything-llm#5929](https://github.com/Mintplex-Labs/anything-llm/pull/5929)
> (currently OPEN, awaiting maintainer review). This cookbook documents the
> integration patterns. The sample tests validate the underlying Valkey
> operations independently using `@valkey/valkey-glide`.

## Quick Start

```bash
cd sample/
docker compose up -d
npm install
npm test
```

## Running the Sample Tests

```bash
cd sample/
docker compose up -d          # Start Valkey with search module
npm install                   # Install pinned dependencies
npm test                      # Run integration tests via vitest
docker compose down           # Cleanup
```

The tests validate all three cookbook scenarios against a live Valkey container — no LLM calls, no external APIs.

---

[← Back to Valkey Samples](../../../README.md)
