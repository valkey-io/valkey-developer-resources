# MindsDB + Valkey Vector Store — Cookbook Sample

Runnable code for the [MindsDB + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **MindsDB** installed (the Valkey handler lives inside the MindsDB codebase)

## Setup

```bash
# Start Valkey with the search module
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Clone MindsDB (the Valkey handler is part of the MindsDB repo)
git clone https://github.com/mindsdb/mindsdb.git
cd mindsdb

# Install dependencies
pip install -e .
pip install valkey-glide numpy pandas
```

> **Note**: The Valkey handler (`mindsdb.integrations.handlers.valkey_handler`) is part of the MindsDB source tree. You need the MindsDB repo on your `PYTHONPATH` for the example script to work.

## Running

```bash
# From this directory (ensure MindsDB is importable)
python main.py
```

## What It Demonstrates

| Step | Operation | Description |
|------|-----------|-------------|
| 1 | Connect | Create a `ValkeyHandler` and verify connectivity |
| 2 | Create index | Build an HNSW vector index via `FT.CREATE` |
| 3 | Insert | Store documents with embeddings as Valkey HASHes |
| 4 | KNN search | Perform vector similarity search |
| 5 | ID lookup | Retrieve documents by ID (single and batch) |
| 6 | Delete | Remove documents by ID |
| 7 | Drop index | Clean up the index and all associated data |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

## Troubleshooting

- **`ImportError: No module named 'mindsdb'`**: Ensure MindsDB is installed or its root is on your `PYTHONPATH`.
- **Connection refused**: Ensure Valkey is running on `localhost:6379` — check with `docker ps`.
- **`Unknown command 'FT.CREATE'`**: Use `valkey/valkey-bundle` image (includes the search module).
- **`ImportError: No module named 'glide'`**: Run `pip install valkey-glide`.
