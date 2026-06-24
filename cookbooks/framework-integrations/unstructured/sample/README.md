# Unstructured + Valkey — Cookbook Sample

Runnable code for the [Unstructured + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.11+**
2. **Docker or Podman** (for Valkey)
3. **A sample PDF** — place any PDF as `sample.pdf` in this directory

## Setup

```bash
# Start Valkey with the Search module
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Or using Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# Run individual steps:
python 01_getting_started.py          # Connection test
python 02_ingestion_and_search.py     # Ingest sample.pdf + KNN search
python 03_production.py               # Index monitoring, TTL config, URI examples
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `SAMPLE_PDF` | `sample.pdf` | Path to a PDF to ingest |
| `INDEX_NAME` | `documents_index` | Index name for monitoring |

## Troubleshooting

- **`ConnectionError`** — Ensure Valkey is running: `docker ps | grep valkey`
- **`ModuleNotFoundError: No module named 'glide'`** — Run `pip install -r requirements.txt`
- **`DestinationConnectionError`** — Check host/port, ensure Valkey is listening on 6379
- **No search results** — Run ingestion first (`python 02_ingestion_and_search.py`)
