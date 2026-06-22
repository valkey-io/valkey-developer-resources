# PraisonAI + Valkey

> 3 cookbooks for giving PraisonAI agents persistent memory and vector knowledge retrieval backed by Valkey.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey with Docker, install PraisonAI with the Valkey extra, configure the connection, and verify it works. | Beginner, ~10 min, Python |
| 02 | <nobr>[Agent State Persistence](02-agent-state.md)</nobr> | Use `ValkeyStateStore` to persist agent state across runs — counters, session history, and structured metadata stored as key-value and hash entries. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Vector Knowledge Retrieval](03-vector-knowledge.md)</nobr> | Index documents with embeddings into Valkey using `ValkeyVectorKnowledgeStore` and wire it into a PraisonAI agent for semantic knowledge retrieval. | Intermediate, ~25 min, Python |
