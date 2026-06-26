# OpenAI + Valkey Cookbook Sample

Runnable code for the [OpenAI + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **An OpenAI API key** ([get one here](https://platform.openai.com/account/api-keys))

## Setup

```bash
# Start Valkey with the search module
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies
pip install -r requirements.txt

# Provide your OpenAI API key
cp .env.example .env
# then edit .env and set OPENAI_API_KEY
```

## Running

```bash
# 01 - Getting started: index documents and run a KNN vector search
python getting_started.py

# 02 - Vector search: HNSW index and hybrid (TAG filter + KNN) search
python vector_search.py
```

## Sample Scripts

| Script | Cookbook | Description |
|--------|----------|-------------|
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Connect, create a FLAT JSON vector index, store documents, run KNN search |
| `vector_search.py` | [02 - Vector Search](../02-vector-search.md) | HNSW index and hybrid search combining a TAG pre-filter with KNN |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | Your OpenAI API key for generating embeddings |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

## Troubleshooting

- **`Missing dependency`**: Run `pip install -r requirements.txt`.
- **Connection refused**: Ensure Valkey is running on `localhost:6379` (`docker ps`).
- **`Unknown command 'FT.CREATE'`**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **`AuthenticationError` from OpenAI**: Confirm `OPENAI_API_KEY` is set in your `.env`.
- **Empty search results**: Verify the embedding dimension (`EMBED_DIM`) matches the model output.
