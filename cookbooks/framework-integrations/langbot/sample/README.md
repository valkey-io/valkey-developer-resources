# LangBot + Valkey — Cookbook Sample

Runnable code for the [LangBot + Valkey cookbook series](../README.md). Two self-contained scripts exercise both integrations against a local Valkey.

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **valkey-glide** (installed below)

## Setup

```bash
# Start Valkey with the search module (needed for vector_search.py)
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies (use a virtual environment)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Podman works identically — replace `docker` with `podman`.

## Running

```bash
# 02 - Distributed rate limiting (single-client + shared-counter demos)
.venv/bin/python rate_limiter.py

# 03 + 04 - Vector, full-text, and hybrid search + file_id filtering/deletion
.venv/bin/python vector_search.py
```

Both scripts assert their expected outcomes and exit non-zero on failure, so a
clean run means every step worked.

## Sample Scripts

| Script | Cookbook | Description |
|--------|----------|-------------|
| `rate_limiter.py` | [02 - Rate Limiting](../02-distributed-rate-limiting.md) | Atomic fixed-window limiter; proves two workers share one counter |
| `vector_search.py` | [03](../03-vector-search.md) / [04](../04-hybrid-and-filtering.md) | HNSW index, KNN, full-text, hybrid filter-then-KNN, `file_id` deletion |

> `vector_search.py` uses a tiny deterministic local embedding (word hashing) so
> it needs no API keys or model downloads. It illustrates the Valkey Search
> mechanics only — real LangBot deployments use a proper embedding model.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

Set them inline, e.g. `VALKEY_PORT=6380 .venv/bin/python vector_search.py`.

## Troubleshooting

- **`ModuleNotFoundError: glide`**: Run `.venv/bin/pip install -r requirements.txt`.
- **Connection refused**: Ensure Valkey is running (`docker ps`).
- **`unknown command 'FT.CREATE'`**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the search module.
- **Empty results right after insert**: Indexing is asynchronous; the script already polls/retries.
