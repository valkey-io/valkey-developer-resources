# Unstructured + Valkey Sample

Runnable code for the [Unstructured + Valkey cookbook](../README.md).

## Prerequisites

- Docker or Podman
- Python 3.11+

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install dependencies
pip install -r requirements.txt

# Run the getting started script
python scripts/getting_started.py

# Run the ingestion & search demo
python scripts/ingest_and_search.py
```

## Run Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Expected Output

### getting_started.py

```text
Connecting to Valkey at localhost:6379...
✓ PING → PONG
✓ Search module loaded (FT._LIST succeeded)

✓ Valkey is ready for document ingestion!
```

### ingest_and_search.py

```text
============================================================
Unstructured + Valkey: Document Ingestion & Search Demo
============================================================

--- Uploading documents ---
✓ Uploaded 5 document chunks
✓ Created HNSW index 'documents_index'

--- Semantic search ---

Query: 'vector similarity search'
Found 3 results (showing top 3):
  ...

--- Cleanup ---
✓ Dropped index 'documents_index'
✓ Deleted 5 keys

✓ Demo complete!
```

## Tear Down

```bash
docker compose down -v
```

## File Structure

| File | Purpose |
| ------ | --------- |
| `docker-compose.yml` | Valkey with Search module |
| `requirements.txt` | Pinned Python dependencies |
| `scripts/getting_started.py` | Connectivity check (cookbook 01) |
| `scripts/ingest_and_search.py` | Full ingestion demo (cookbook 02) |
| `tests/conftest.py` | Shared test fixtures |
| `tests/test_unstructured_patterns.py` | Integration tests |
| `pytest.ini` | Pytest configuration |

## Notes

The `unstructured-ingest[valkey]` package is not yet released (blocked on
[upstream PR #747](https://github.com/Unstructured-IO/unstructured-ingest/pull/747)).
The sample scripts demonstrate the same Valkey patterns (hash storage, HNSW
index, KNN search) using `valkey-glide` directly. Once the upstream is
released, scripts can be updated to use the connector API.
