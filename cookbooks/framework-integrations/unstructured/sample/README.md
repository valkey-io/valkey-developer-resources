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

## Configuration

The scripts use these defaults (hardcoded for simplicity):

- **Valkey host**: `localhost`
- **Valkey port**: `6379`
- **Sample PDF**: `sample.pdf` (place any PDF with this name in this directory)
- **Index name**: `documents_index`

Edit the constants at the top of each script if your setup differs.

## Troubleshooting

- **`ConnectionError`** — Ensure Valkey is running: `docker ps | grep valkey`
- **`ModuleNotFoundError: No module named 'glide'`** — Run `pip install -r requirements.txt`
- **`DestinationConnectionError`** — Check host/port, ensure Valkey is listening on 6379
- **No search results** — Run ingestion first (`python 02_ingestion_and_search.py`)
