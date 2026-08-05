# Upsonic + Valkey Cookbook Sample

Runnable code for the [Upsonic + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **upsonic[valkey]** package available on PyPI

> **⚠️ Dependency note:** This sample requires [Upsonic PR #607](https://github.com/Upsonic/Upsonic/pull/607)
> to be merged and released. `pip install "upsonic[valkey]"` will not resolve until then.
> Update the version in `requirements.txt` to the actual release version once published.

## Setup

```bash
# Start Valkey with Search module
docker compose up -d

# Wait for healthcheck to pass
docker compose ps   # verify status is "healthy"

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# 01 - Getting started
python getting_started.py

# 02 - Search strategies (dense, full-text, hybrid, filtered)
python search_strategies.py

# 03 - Production patterns (batch ingest, dedup, error handling)
python production_deployment.py
```

## Expected Output

### getting_started.py

```text
Indexed 3 chunks

Dense search results:
  [1.000] chunk_3: HNSW provides fast approximate nearest neighbor search
  [0.707] chunk_1: Valkey is a high-performance in-memory data store

Done!
```

### search_strategies.py

```text
Indexed 5 chunks

--- Dense Search (KNN) ---
  [1.000] Valkey is a high-performance in-memory data store for caching
  [0.999] Vector similarity search finds nearest neighbors in embedding space
  [0.998] HNSW algorithm provides fast approximate nearest neighbor queries

--- Full-Text Search ---
  [results matching "nearest neighbor"]

--- Hybrid Search (RRF) ---
  [combined results]

--- Filtered Search (document_name=valkey_intro.md) ---
  [only valkey_intro.md chunks]

--- Filtered Search (knowledge_base_id=kb_ml) ---
  [only kb_ml chunks]

Done!
```

## Sample Scripts

| Script | Cookbook | Description |
| --- | --- | --- |
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Connect, index documents, run dense search |
| `search_strategies.py` | [02 - Search Strategies](../02-search-strategies.md) | Dense, full-text, hybrid (RRF), and filtered search |
| `production_deployment.py` | [03 - Production Deployment](../03-production-deployment.md) | Batch ingest with dedup, error handling, delete operations |

## Teardown

```bash
docker compose down -v
```

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379` (`docker compose ps`).
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **ImportError for valkey-glide**: Install with `pip install "upsonic[valkey]"`.
- **"Index not found"**: Call `provider.acreate_collection()` before searching.
