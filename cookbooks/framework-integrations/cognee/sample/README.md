# Cognee + Valkey Cookbook Sample

Runnable code for the [Cognee + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.11+**
2. **Docker** or **Podman** (for Valkey)
3. **[Ollama](https://ollama.com/)** installed locally with the default models pulled (see below) — no API key or cloud account needed

## Setup

```bash
# Start Valkey
docker compose up -d

# Pull the default local models (qwen2.5:7b ~4.7 GB, nomic-embed-text ~274 MB)
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# 01 - Quick start
python quick_start.py

# 02 - Knowledge graph search types
python knowledge_graph.py

# 03 - Production patterns
python production_patterns.py
```

## Testing

```bash
pytest test_valkey_adapter.py -v
```

`test_valkey_adapter.py` exercises the Valkey vector adapter directly with a deterministic stub embedder — no LLM, no Ollama required. It's the test CI runs.

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|--------------|
| `quick_start.py` | [01 - Getting Started](../01-getting-started.md) | Configure Valkey adapter, add documents, cognify, search |
| `knowledge_graph.py` | [02 - Knowledge Graph](../02-knowledge-graph.md) | Multi-document relationships, search types comparison |
| `production_patterns.py` | [03 - Production Patterns](../03-production.md) | Error handling, batch operations, monitoring |
| `test_valkey_adapter.py` | All | CI test suite — adapter CRUD + search, no LLM |
| `common.py` | All | Shared Ollama/Cognee configuration bootstrap imported by the three scripts above |

## Environment Variables

| Variable | Default | Description |
|----------|---------|--------------|
| `VECTOR_DB_URL` | `valkey://localhost:6379` | Valkey connection URL (use `valkeys://` for TLS) |
| `LLM_PROVIDER` | `ollama` | LLM provider — `ollama`, `openai`, or `bedrock` |
| `LLM_MODEL` | `qwen2.5:7b` | LLM model for knowledge extraction and search completion |
| `EMBEDDING_PROVIDER` | `ollama` | Embedding provider — `ollama`, `openai`, or `bedrock` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `768` | Must match the embedding model's output dimension |

See [.env.example](.env.example) for OpenAI and Amazon Bedrock alternatives.

## Troubleshooting

- **Connection refused**: ensure Valkey is running on `localhost:6379` (`docker compose ps`).
- **Module errors**: use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **`ModuleNotFoundError: No module named 'transformers'`**: the Ollama embedding path needs a local HuggingFace tokenizer for token counting; `pip install -r requirements.txt` includes it.
- **Structured-output / retry errors from `cognify()` or `search()`**: this means the LLM isn't reliably following the JSON schema Cognee
  expects. Smaller local models (1B–3B parameters) are prone to this — `qwen2.5:7b` is the smallest model verified to work reliably for this cookbook.
- **Ollama connection errors**: confirm `ollama serve` is running and `curl http://localhost:11434/api/tags` returns your pulled models.

## Teardown

```bash
docker compose down -v
```
