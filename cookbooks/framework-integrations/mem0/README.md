# Mem0 + Valkey

> Use Mem0's memory API with Valkey as the vector store for scoped, searchable agent memory.

**Who is this for:** Python developers building agents that need persistent memory without implementing vector storage and filtering themselves.

Mem0 is an open-source memory layer with a [Valkey vector-store integration](https://github.com/mem0ai/mem0). This track uses Mem0's public API while Valkey Search handles vector indexing and scoped retrieval.

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- No external model credentials for the default sample path

## Run the Sample

The runnable sample is in [`sample/`](sample/). Its default path uses Mem0's deterministic local embedding stub and does not call an LLM:

```bash
cd sample
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure Mem0 with Valkey, add a memory, search it, and list scoped memories. | Beginner, ~15 min, Python |
| 02 | <nobr>[Multi-User Memory](02-multi-user-memory.md)</nobr> | Use Mem0 filters to isolate memories by user, agent, and session. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Configuration](03-production.md)</nobr> | Configure generic TLS, authentication, HNSW settings, and operational cleanup. | Advanced, ~20 min, Python |
