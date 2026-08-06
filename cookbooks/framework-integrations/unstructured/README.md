# Unstructured + Valkey

> Transform documents (PDFs, HTML, DOCX) into searchable vector embeddings
> stored in Valkey with HNSW indexes for low-latency semantic retrieval.

[Unstructured](https://github.com/Unstructured-IO/unstructured-ingest) is an
ETL framework that partitions, chunks, and embeds raw documents into
AI-ready data. The Valkey destination connector stores the output as hashes
with vector embeddings and creates FT Search indexes for KNN similarity
queries.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install dependencies, start Valkey, configure the connector, and verify connectivity. | Beginner, ~10 min, Python |
| 02 | <nobr>[Document Ingestion & Search](02-ingestion-and-search.md)</nobr> | End-to-end pipeline: partition a document, embed chunks, upload to Valkey, and run KNN vector search. | Intermediate, ~25 min, Python |
| 03 | <nobr>[Production Deployment](03-production.md)</nobr> | TLS, authentication, TTL lifecycle, HNSW tuning, batch strategies, and monitoring. | Advanced, ~20 min, Python |

## Architecture

```text
┌────────────┐    ┌───────────┐    ┌──────────┐    ┌────────────┐    ┌─────────┐
│  Documents │───▶│ Partition │───▶│  Chunk   │───▶│   Embed    │───▶│  Valkey │
│ PDF / HTML │    │(structure)│    │(semantic)│    │(vectorize) │    │ (store) │
└────────────┘    └───────────┘    └──────────┘    └────────────┘    └─────────┘
                                                                          │
                                                                     FT.SEARCH
                                                                     KNN query
                                                                          │
                                                                          ▼
                                                                   ┌─────────────┐
                                                                   │  Results    │
                                                                   │ (top-K)     │
                                                                   └─────────────┘
```

## Key Concepts

| Component | Role |
| ----------- | ------ |
| `unstructured-ingest` | ETL framework — reads documents, partitions into elements, chunks, embeds |
| Valkey destination connector | Stores document chunks as Valkey hashes with vector embeddings |
| `valkey-glide` | Official Valkey client (async) used by the connector |
| Valkey Search (FT) | Indexes hashes with HNSW vector fields for KNN similarity queries |
| `valkey/valkey-bundle` | Docker image with Search module pre-loaded |

## Prerequisites

- Python 3.11+
- Docker (or Podman)
- No paid API keys required for the default path (uses local embeddings)

## Quick Start

```bash
cd cookbooks/framework-integrations/unstructured/sample
docker compose up -d
pip install -r requirements.txt
python scripts/getting_started.py
```
