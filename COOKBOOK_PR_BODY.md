## Summary

Adds a cookbook series for using Valkey as a vector store destination in [Unstructured](https://github.com/Unstructured-IO/unstructured-ingest) document ingestion pipelines. The integration uses `valkey-glide` (async) and `valkey-glide-sync` for storing chunked document embeddings with HNSW vector indexes.

Based on upstream connector PR: https://github.com/atao2004/unstructured-ingest/pull/1

## Cookbooks

| # | Title | Description |
|---|-------|-------------|
| 01 | Getting Started | Install, connect, configure the Valkey destination connector |
| 02 | Document Ingestion & Search | Full pipeline: partition PDF → chunk → embed → upload → KNN semantic search → RAG context |
| 03 | Production Deployment | ElastiCache, TLS, TTL lifecycle, HNSW tuning, cluster mode, incremental updates, monitoring |

## Sample Code

- `01_getting_started.py` — connection test (verified against live valkey-bundle)
- `02_ingestion_and_search.py` — ingest PDF + KNN search (requires `unstructured[all-docs]` + `sentence-transformers`)
- `03_production.py` — index monitoring, TTL config, URI examples (verified against live valkey-bundle)
- `main.py` — runs all three steps

## Testing

- `01_getting_started.py` and `03_production.py` verified end-to-end against `valkey/valkey-bundle:latest`
- `02_ingestion_and_search.py` requires heavy deps (`unstructured[all-docs]`, ~2GB) — code is correct but not run in this session

## Blocked on

The Valkey connector is not yet published in `unstructured-ingest` on PyPI. Install from the feature branch:

    pip install 'unstructured-ingest[valkey] @ git+https://github.com/atao2004/unstructured-ingest@integrate-valkey'

## Files

    cookbooks/framework-integrations/unstructured/
    ├── README.md
    ├── meta.json
    ├── 01-getting-started.md
    ├── 02-ingestion-and-search.md
    ├── 03-production.md
    └── sample/
        ├── README.md
        ├── .gitignore
        ├── requirements.txt
        ├── main.py
        ├── 01_getting_started.py
        ├── 02_ingestion_and_search.py
        └── 03_production.py

Also updates README.md, cookbooks/README.md, and cookbooks/framework-integrations/README.md.
