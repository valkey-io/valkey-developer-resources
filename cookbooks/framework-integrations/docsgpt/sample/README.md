# DocsGPT + Valkey — Sample Code

Runnable sample that demonstrates the Valkey vector store patterns used by DocsGPT. Tests run against a real Valkey instance with the search module — no mocks.

## Prerequisites

- Python 3.10+
- Docker (for running Valkey with the search module)

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install dependencies
pip install -e ".[test]"

# Run tests
pytest -v tests/

# Run demo scripts
python scripts/getting_started.py
python scripts/ingestion_demo.py
```

## Structure

```text
sample/
├── docker-compose.yml          # Valkey with search module
├── pyproject.toml              # Dependencies (valkey-glide-sync, pytest)
├── README.md                   # This file
├── .gitignore
├── scripts/
│   ├── getting_started.py      # Connectivity check (Cookbook 01)
│   └── ingestion_demo.py       # Ingestion + search demo (Cookbook 02)
└── tests/
    ├── conftest.py             # Shared fixtures (Valkey client, cleanup)
    └── test_docsgpt_valkey_patterns.py  # Integration tests
```

## What the Tests Verify

The test suite validates the Valkey patterns that DocsGPT's `ValkeyStore` relies on:

1. **Connectivity** — GLIDE client connects and pings
2. **Index creation** — `FT.CREATE` with HNSW vector field, TEXT, and TAG fields
3. **Document storage** — `HSET` with content, source_id, metadata, and embedding bytes
4. **KNN search** — `FT.SEARCH` with vector similarity query
5. **Source isolation** — TAG field filtering restricts results to a single source
6. **Chunk deletion** — Individual key deletion and bulk scan+delete
7. **TAG escaping** — Special characters in source_id are properly escaped

## Running Without Docker

If you have Valkey running elsewhere:

```bash
VALKEY_HOST=your-host VALKEY_PORT=6379 pytest -v tests/
```

## Tear Down

```bash
docker compose down -v
```
