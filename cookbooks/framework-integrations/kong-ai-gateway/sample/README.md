# Kong AI Gateway + Valkey Sample

Validates the vector store patterns that Kong AI Gateway's semantic plugins use
against Valkey. Tests exercise the same commands Kong performs: `FT.CREATE` with
HNSW on JSON data, `JSON.SET` for document storage, `FT.SEARCH` with KNN queries,
and cosine distance scoring.

## Quick Start

```bash
# Start Valkey with search + JSON modules
docker compose up -d

# Install and test
uv venv && uv pip install -e ".[test]"
.venv/bin/pytest tests/ -v

# Tear down
docker compose down -v
```

## What the Tests Validate

- Connectivity and search module availability
- JSON document storage with vector embeddings
- FT index creation (HNSW with COSINE on JSON paths)
- KNN vector search with distance scoring
- Cosine distance threshold filtering (semantic similarity matching)
- Multiple index isolation (one per plugin)
- Server name detection (auto-detect Valkey vs Redis)
- Embedding dimension validation

## Requirements

- Python 3.10+
- Docker (for Valkey)
