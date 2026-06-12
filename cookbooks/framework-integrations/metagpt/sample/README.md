# MetaGPT + Valkey — Cookbook Sample

Runnable code for the [MetaGPT + Valkey cookbook series](../README.md). Demonstrates the synchronous `ValkeyVectorStore` lifecycle: create index, add documents, KNN search, delete, and drop index.

## Prerequisites

1. **Python 3.9–3.11** (MetaGPT requires `<3.12`)
2. **Docker or Podman** (for Valkey)
3. **MetaGPT with the Valkey RAG backend** — currently in review, install from the feature branch (see below)

## Setup

```bash
# Start Valkey with the Search + JSON modules
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Or using Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install the sample's direct dependencies
pip install -r requirements.txt

# Install MetaGPT (with the Valkey backend) from the feature branch.
# The Valkey RAG backend is not yet part of the published metagpt package.
pip install "metagpt[rag] @ git+https://github.com/daric93/MetaGPT.git@feat/valkey-rag-vector-store"
```

## Running

```bash
python main.py
```

The demo uses a tiny deterministic local embedding function so it runs without any API key. In a real MetaGPT application, embeddings come from your configured embedding model.

## Environment Variables

Copy `.env.example` to `.env` to override these (the sample calls `load_dotenv()`), or `export` them in your shell.

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

## Troubleshooting

- **`ModuleNotFoundError: No module named 'glide_sync'`** — Run `pip install -r requirements.txt` (the package is `valkey-glide-sync`, it imports as `glide_sync`)
- **`ModuleNotFoundError: No module named 'metagpt'`** — Install MetaGPT from the feature branch (see Setup)
- **`Unknown command 'FT.CREATE'`** — Use the `valkey/valkey-bundle:latest` image (includes the search module)
- **`ConnectionError` / `Request timed out`** — Ensure Valkey is running (`docker ps | grep valkey`); increase `request_timeout` in `main.py` for non-local servers
