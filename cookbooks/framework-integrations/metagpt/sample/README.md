# MetaGPT + Valkey — Cookbook Sample

Runnable code for the [MetaGPT + Valkey cookbook series](../README.md). Demonstrates the synchronous `ValkeyVectorStore` lifecycle: create index, add documents, KNN search, delete, and drop index —
using this cookbook's standalone reimplementation (`valkey_vector_store.py`), not MetaGPT itself. See [Upstream Status](../README.md#upstream-status) in the track README for why.

## Prerequisites

1. **Python 3.10+** (required by `llama-index-core` 0.14.23 — see [requirements.txt](requirements.txt))
2. **Docker or Podman** (for Valkey)
3. No API key required — embeddings are produced by a deterministic local function

## Setup

```bash
# Start Valkey with the Search + JSON modules
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

Podman alternative:

```bash
podman run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

Or with Docker Compose:

```bash
docker compose up -d
```

Install the sample's dependencies:

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

The demo uses a tiny deterministic local embedding function so it runs without any API key. In a real MetaGPT application (once FoundationAgents/MetaGPT#2063 is merged and released), embeddings come
from your configured embedding model.

## Environment Variables

Copy `.env.example` to `.env` to override these (the sample calls `load_dotenv()`), or `export` them in your shell.

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

## Testing

```bash
pytest test_valkey_vector_store.py -v
```

Tests require the same running Valkey instance as `main.py` (Search + JSON modules loaded). Each test uses a unique index name and key prefix so tests can run concurrently and don't interfere with
each other or with `main.py`'s demo data.

## Files

| File | Description |
| --- | --- |
| `valkey_vector_store.py` | Standalone reimplementation of MetaGPT's `ValkeyVectorStore`: schema, atomic batch writes, KNN query, delete-by-ref_doc_id, index lifecycle |
| `main.py` | Full lifecycle demo: create index, add documents, KNN search, delete, drop index — asserts expected behavior at each step |
| `test_valkey_vector_store.py` | Unit + integration tests against a live Valkey instance |
| `docker-compose.yml` | One-command Valkey startup |
| `requirements.txt` | Pinned Python dependencies (`valkey-glide-sync`, `llama-index-core`, `python-dotenv`, `pytest`) |
| `.env.example` | Safe local connection settings |
| `.gitignore` | Excludes `.env`, virtual environments, and Python caches |

## Troubleshooting

- **`ModuleNotFoundError: No module named 'glide_sync'`** — Run `pip install -r requirements.txt` (the package is `valkey-glide-sync`, it imports as `glide_sync`)
- **`ModuleNotFoundError: No module named 'llama_index'`** — Run `pip install -r requirements.txt`; also confirm you're on Python 3.10+ (`llama-index-core` 0.14.23 requires it)
- **`Unknown command 'FT.CREATE'`** — Use the `valkey/valkey-bundle:9.1.0` image (includes the search module)
- **`ConnectionError` / `Request timed out`** — Ensure Valkey is running (`docker ps | grep valkey`); increase `request_timeout` in `main.py` for non-local servers

## Teardown

```bash
docker compose down -v
```

Or, if started with `docker run`:

```bash
docker stop valkey && docker rm valkey
```
