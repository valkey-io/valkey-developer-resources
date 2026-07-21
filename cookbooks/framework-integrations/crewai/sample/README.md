# CrewAI + Valkey Cookbook Sample

> Runnable Python sample demonstrating a custom Valkey `StorageBackend` for CrewAI's unified Memory system using valkey-glide.

## Prerequisites

- Python 3.10 or newer
- Docker Compose or Podman Compose
- No external services for the default CI test path
- [Ollama](https://ollama.com/) installed for `memory_demo.py` (the full CrewAI Memory demo)

## Setup

Run these commands from this directory:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Running Tests (CI path — no LLM needed)

```bash
.venv/bin/python -m pytest test_storage.py -v
```

Tests verify:

- Index creation and record storage
- KNN vector search with similarity scoring
- Scope and category filtering
- Delete by ID and by scope
- Count and reset operations

All tests use deterministic fixed vectors — no Ollama, no OpenAI, no LLM.

## Running the Full Demo (requires Ollama)

```bash
# Pull required models (one-time)
ollama pull nomic-embed-text
ollama pull llama3.2:1b

# Run the demo
.venv/bin/python memory_demo.py
```

## Sample Scripts

| Script | Cookbook | Description |
| --- | --- | --- |
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Connect to Valkey with GLIDE, store and search vectors |
| `valkey_storage.py` | [02 - Memory Storage](../02-memory-storage.md) | The `ValkeyStorageBackend` implementation |
| `memory_demo.py` | [03 - Agent Memory](../03-agent-memory.md) | Full CrewAI Memory integration (requires Ollama) |

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `OPENAI_API_KEY` | unset | Optional: use OpenAI instead of Ollama for Memory LLM/embedder |

## Teardown

```bash
docker compose down
```

Replace `docker compose` with `podman compose` when using Podman.
