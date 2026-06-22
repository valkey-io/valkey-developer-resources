# CocoIndex

CocoIndex is an open-source Python framework for building incremental data
pipelines that keep AI agent context continuously fresh.

## Key Features

- **Incremental processing** — only the delta is reprocessed on every change
- **Declarative** — describe what your target should contain
- **Parallel execution** — Rust core handles parallelism automatically
- **Lineage tracking** — every target row traces back to its source

## Supported Targets

CocoIndex supports Postgres (pgvector), Qdrant, LanceDB, TurboPuffer,
Valkey, Neo4j, FalkorDB, Kafka, and more as target stores.
