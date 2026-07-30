# PraisonAI + Valkey

> Add persistent session state and vector-searchable knowledge to PraisonAI agents using Valkey.

**Who is this for:** Python developers building multi-agent systems with PraisonAI who want conversation
history to survive restarts and knowledge bases to be searchable by semantic similarity — all backed by Valkey.

## Prerequisites

- Docker or Podman (container runtime)
- Python 3.10 or newer
- An OpenAI-compatible API key, or [Ollama](https://ollama.com/) for a free local option

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect a PraisonAI agent to Valkey and verify the integration end-to-end. | Beginner, ~10 min, Python |
| 02 | <nobr>[Agent State Persistence](02-agent-state.md)</nobr> | Store and reload conversation history across agent restarts using `ValkeyStateStore`. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Vector Knowledge Retrieval](03-vector-knowledge.md)</nobr> | Build a semantic knowledge base with `ValkeyVectorKnowledgeStore` and HNSW indexing. | Intermediate, ~25 min, Python |

## Affiliation Disclosure

PraisonAI is an open-source project maintained by [Mervin Praison](https://github.com/MervinPraison) (MIT licensed).

---

[01 - Getting Started →](01-getting-started.md)
