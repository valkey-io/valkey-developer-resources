# Google ADK + Valkey — Cookbook Sample

Runnable code for the [Google ADK + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.10+**
2. **Docker or Podman** (for Valkey)
3. **google-adk-community[valkey]** — includes `valkey-glide` client
4. **Google GenAI API key** — for embedding generation (set `GOOGLE_API_KEY` env var)

## Setup

```bash
# Start Valkey with the Search module
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Or using Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# Set your embedding provider API key
export GOOGLE_API_KEY="your-api-key-here"

# Run the full lifecycle demo
python main.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `GOOGLE_API_KEY` | (required) | Google GenAI API key for embeddings |
| `MEMORY_TTL_SECONDS` | `3600` | TTL for memory entries in seconds |

## Troubleshooting

- **`ConnectionError`** — Ensure Valkey is running: `docker ps | grep valkey`
- **`ModuleNotFoundError: No module named 'glide'`** — Run `pip install -r requirements.txt`
- **Embedding errors** — Verify `GOOGLE_API_KEY` is set and valid
- **`Request timed out`** — Increase the request_timeout in the script (default 5000ms)
