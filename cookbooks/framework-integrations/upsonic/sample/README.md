# Upsonic + Valkey Cookbook Sample

Runnable code for the [Upsonic + Valkey cookbook series](../README.md).

> **⚠️ Blocked:** Requires [Upsonic PR #607](https://github.com/Upsonic/Upsonic/pull/607) to be merged and released. `pip install "upsonic[valkey]"` will not work until then.

> **✅ Tested:** All scripts validated against Valkey 9.1 with valkey-search module v1.2 using a local editable install of the Upsonic PR branch.

## Prerequisites

1. **Python 3.10+**
2. **Docker** (for Valkey)

## Setup

```bash
# Start Valkey with Search module (choose one)
docker compose up -d
# or
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1

# Install dependencies (available after Upsonic PR #607 is released)
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

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Connect, index documents, run dense search |
| `search_strategies.py` | [02 - Search Strategies](../02-search-strategies.md) | Dense, full-text, hybrid (RRF), and filtered search |
| `production_deployment.py` | [03 - Production Deployment](../03-production-deployment.md) | Batch ingest with dedup, error handling, delete operations |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **ImportError for valkey-glide**: Install with `pip install "upsonic[valkey]"`.
- **"Index not found"**: Call `provider.acreate_collection()` before searching.
