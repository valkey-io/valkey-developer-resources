# LangBot + Valkey — Cookbook Sample

Runnable code for the [LangBot + Valkey cookbook series](../README.md). A self-contained script exercises the Valkey Search knowledge-base backend against a local Valkey.

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **valkey-glide** (installed below)

## Setup

```bash
# Start Valkey with the search module (needed for vector_search.py)
docker compose up -d

# Install dependencies (use a virtual environment)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Or without compose:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0
```

Podman works identically — replace `docker` with `podman`.

## Running

```bash
# 02 + 03 - Vector, full-text, and hybrid search + file_id filtering/deletion
.venv/bin/python vector_search.py
```

The script asserts its expected outcomes and exits non-zero on failure, so a clean run means every step worked.

### Expected output

```text
=== Vector search: 'similar vector embeddings' ===
  chunk-1: distance=0.3453 :: 'Vector search finds similar embeddings using KNN'
  chunk-0: distance=0.8174 :: 'Valkey is a high performance in-memory data store'
  chunk-3: distance=1.0000 :: 'Rate limiting protects services from request floods'

=== Full-text search: 'bots' ===
  chunk-2 :: 'LangBot builds agentic instant messaging bots'

=== Hybrid: file_id=fileB + KNN ===
  chunk-2: distance=0.4226 :: 'LangBot builds agentic instant messaging bots'
  chunk-3: distance=1.0000 :: 'Rate limiting protects services from request floods'

=== Delete by file_id: fileA ===
  removed 2 chunk(s)

All vector-search demos passed.
```

Captured from an actual run against `valkey/valkey-bundle:9.1.0` with `valkey-glide==2.5.0`. Exact distance values can vary slightly run
to run (HNSW is an approximate index) but the ranking and pass/fail assertions do not.

### Tests

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest test_vector_search.py -v
```

`test_vector_search.py` covers index creation, KNN, full-text, hybrid, `file_id` filtering, and delete-by-file-id independently of the demo script above.

## Teardown

```bash
docker compose down -v
```

## Sample Files

| File | Cookbook | Description |
|------|----------|-------------|
| `vector_search.py` | [02](../02-vector-search.md) / [03](../03-hybrid-and-filtering.md) | HNSW index, KNN, full-text, hybrid filter-then-KNN, `file_id` deletion — runnable demo |
| `test_vector_search.py` | [02](../02-vector-search.md) / [03](../03-hybrid-and-filtering.md) | Pytest suite covering the same operations, CI-friendly |

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
