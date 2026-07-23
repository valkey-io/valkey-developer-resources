# Agno + Valkey

> Give Agno agents persistent session storage and vector-searchable knowledge backed by Valkey.

**Who is this for:** Python developers building AI agents with Agno who want sessions to persist across restarts and knowledge to be searchable by semantic similarity — all backed by Valkey.

## Prerequisites

- Docker or Podman (container runtime)
- Python 3.10 or newer
- [Ollama](https://ollama.com/) for the knowledge base cookbooks (02, 03)

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect an Agno agent to Valkey for persistent session storage. | Beginner, ~10 min, Python |
| 02 | <nobr>[Knowledge Base](02-knowledge-base.md)</nobr> | Build a vector-searchable knowledge base with `ValkeyDB` and Ollama embeddings. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Per-User Isolation](03-per-user-isolation.md)</nobr> | Multi-tenant knowledge: each user sees only their own documents plus shared ones. | Intermediate, ~15 min, Python |

## Affiliation Disclosure

Agno is an open-source project maintained by [Agno AGI](https://github.com/agno-agi) (Apache-2.0 licensed).

---

[01 - Getting Started →](01-getting-started.md)
