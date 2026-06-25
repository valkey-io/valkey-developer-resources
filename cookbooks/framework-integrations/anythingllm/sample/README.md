# AnythingLLM + Valkey — Cookbook Sample

Runnable Node.js code for the [AnythingLLM + Valkey cookbook series](../README.md). Each script mirrors part of AnythingLLM's Valkey vector-database provider using GLIDE's typed `GlideFt` API, and asserts its own results so a failure is loud.

## Prerequisites

1. **Docker or Podman** (for Valkey with the search module)
2. **Node.js 18+**

## Setup

```bash
# Start Valkey (valkey-bundle ships the search + JSON modules)
docker compose up -d        # or: podman compose up -d

# Install dependencies
npm install
```

> The sample pins `@valkey/valkey-glide` to `2.4.1` — the exact version AnythingLLM uses — which is the first release line exposing the typed `GlideFt` vector-search API used here.

## Running

```bash
# 01 - Getting started: create an index, store a chunk, KNN search
npm run getting-started

# 02 - Vector search: threshold filtering + pinned-source exclusion
npm run vector-search

# 03 - Production: connection probe, dimension guard, delete, reset
npm run production
```

Each script cleans up the data it creates and closes its client on exit.

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `src/getting-started.js` | [01 - Getting Started](../01-getting-started.md) | Connect, create the per-namespace HNSW index, store a chunk, run a KNN search |
| `src/vector-search.js` | [02 - Vector Search & Retrieval](../02-vector-search.md) | Ingest several chunks, score/sort/threshold, exclude pinned sources |
| `src/production.js` | [03 - Production Operations](../03-production.md) | Connection probe, dimension guard, namespace delete, bounded SCAN cleanup, reset |
| `src/valkey-lib.js` | All | Shared helpers (connection, embedding, index, search, cleanup) |

## Environment Variables

The scripts read the same variables as the AnythingLLM provider (all optional; sensible localhost defaults apply):

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_VECTOR_DB_ENDPOINT` | _(unset)_ | `redis://` / `rediss://` URL; overrides host/port |
| `VALKEY_VECTOR_DB_HOST` | `localhost` | Valkey hostname |
| `VALKEY_VECTOR_DB_PORT` | `6379` | Valkey port |
| `VALKEY_VECTOR_DB_USERNAME` | _(unset)_ | ACL username (optional) |
| `VALKEY_VECTOR_DB_PASSWORD` | _(unset)_ | AUTH password (optional) |
| `VALKEY_VECTOR_DB_USE_TLS` | `false` | `true` for TLS endpoints |
| `VALKEY_VECTOR_DB_REQUEST_TIMEOUT` | `5000` | Request timeout in ms (GLIDE's 250ms default is too low off-localhost) |

## Cleanup

```bash
docker compose down        # or: podman compose down
```

## Troubleshooting

- **`unknown command 'FT.CREATE'`** — you're not running the `valkey-bundle` image. `docker compose up -d` here uses it.
- **Connection timeout** — raise `VALKEY_VECTOR_DB_REQUEST_TIMEOUT`; GLIDE defaults to 250ms.
- **0 matches right after ingest** — indexing is asynchronous; the scripts poll `FT.INFO num_docs` via `waitForIndexCount`.
