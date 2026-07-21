# CrewAI + Valkey

> Give CrewAI agents persistent, searchable memory backed by Valkey — implement the `StorageBackend` protocol with valkey-glide and HNSW vector search.

**Who is this for:** Python developers building multi-agent systems with CrewAI who want agent memories to persist across executions and be searchable by semantic similarity.

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- No credentials for the default CI test path
- [Ollama](https://ollama.com/) for the full Memory demo (cookbook 03)

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect to Valkey with GLIDE, create a vector index, store and search embeddings. | Beginner, ~15 min, Python |
| 02 | <nobr>[Memory Storage Backend](02-memory-storage.md)</nobr> | Build `ValkeyStorageBackend` — a custom CrewAI `StorageBackend` with HNSW vector search, TAG filtering, and JSON serialization. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Agent Memory in Action](03-agent-memory.md)</nobr> | Wire `ValkeyStorageBackend` into CrewAI `Memory`. Agents remember and recall across executions. | Intermediate, ~15 min, Python |
