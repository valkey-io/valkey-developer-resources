# DB-GPT + Valkey Cookbook Sample

Runnable sample code and integration tests for the DB-GPT + Valkey cookbook.

## Prerequisites

- Python 3.10+
- Docker (for Valkey)

## Quick Start

```bash
# Start Valkey with the search module
docker compose up -d

# Wait for healthy status
docker compose ps

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"

# Run the connectivity check
python scripts/getting_started.py

# Run the vector store demo (uses mock embeddings)
python scripts/vector_store_demo.py

# Run the cache demo
python scripts/cache_demo.py

# Run integration tests
pytest -v tests/

# Tear down
docker compose down -v
```

## Project Structure

```text
sample/
├── docker-compose.yml       # Valkey with valkey-search module
├── pyproject.toml           # Dependencies (pinned)
├── pytest.ini               # Test configuration
├── scripts/
│   ├── getting_started.py   # Connectivity verification
│   ├── vector_store_demo.py # Vector store CRUD with mock embeddings
│   └── cache_demo.py        # LLM cache operations
└── tests/
    ├── conftest.py          # Shared fixtures
    └── test_dbgpt_valkey_patterns.py  # Integration tests
```

## Notes

- All demo scripts use **mock embeddings** (random float vectors) — no paid API keys required.
- Tests validate the underlying Valkey patterns used by DB-GPT's `ValkeyStore` and `ValkeyCacheStorage`.
- The docker-compose binds only to `127.0.0.1` for security.
