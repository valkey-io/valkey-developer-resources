# Open WebUI + Valkey Sample

Validates the vector store patterns that Open WebUI uses against Valkey. Tests exercise
the same commands the `ValkeyClient` backend performs: `FT.CREATE` with HNSW/FLAT on
HASH data, `HSET` for document storage, `FT.SEARCH` with KNN queries, TAG-filtered
searches, and collection management.

## Quick Start

```bash
# Start Valkey with search module
docker compose up -d

# Install and test
uv venv && uv pip install -e ".[test]"
.venv/bin/pytest tests/ -v

# Tear down
docker compose down -v
```

## What the Tests Validate

- Connectivity, server version detection, and search module availability
- HASH document storage with float32 vector bytes
- FT index creation (HNSW with COSINE, configurable M/EF)
- KNN vector search with distance scoring
- TAG field filtering (exact match, $in, $ne patterns)
- Collection prefix isolation
- Document deletion and collection reset
- Startup version validation logic

## Requirements

- Python 3.10+
- Docker (for Valkey)
