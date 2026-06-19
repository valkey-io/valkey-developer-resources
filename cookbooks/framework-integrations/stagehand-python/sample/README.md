# Stagehand Python + Valkey Cookbook Sample

Runnable code for the [Stagehand Python + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.9+**
2. **Docker** (for Valkey)
3. **Node.js 18+** (for the Stagehand server)
4. **The Stagehand server** running 
5. **A MODEL_API_KEY** (OpenAI, Anthropic, Google, or any Stagehand-supported LLM provider)

## Setup

```bash
# Start Valkey
docker compose up -d

# Start the Stagehand server with Valkey env vars (if hasn't been started yet)
git clone https://github.com/browserbase/stagehand.git
cd stagehand/packages/server-v3
VALKEY_HOST=localhost VALKEY_PORT=6379 VALKEY_KEY_PREFIX=stagehand-demo \
  CACHE_TTL=3600 PORT=3000 npx tsx src/server.ts

# In another terminal, install Python dependencies
pip install -r requirements.txt
```

## Running

```bash
MODEL_API_KEY=your-key python demo.py
```

On the first run, Stagehand calls the LLM to resolve the browser action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed instantly.

Verify with:

```bash
valkey-cli KEYS "stagehand-demo:*"
# 1) "stagehand-demo:act:<hash>"
```

## What It Demonstrates

| Topic | Cookbook | Config Used |
|-------|---------|-------------|
| Basic cached action | [01 - Getting Started](../01-getting-started.md) | `valkey_host`, `valkey_port` (server env) |
| Key prefix and TTL | [02 - Cache Categories and TTL](../02-cache-categories-and-ttl.md) | `VALKEY_KEY_PREFIX`, `CACHE_TTL` (server env) |
| TLS and auth | [03 - Production Configuration](../03-production-configuration.md) | `valkey_tls`, `valkey_username`, `valkey_password` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_API_KEY` | (required) | LLM API key |
| `STAGEHAND_SERVER_URL` | `http://localhost:3000` | Stagehand server URL |

## Troubleshooting

- **Connection refused on port 3000**: Start the Stagehand server first.
- **Connection refused on port 6379**: Start Valkey (`docker compose up -d`).
- **Missing MODEL_API_KEY**: Export the variable or prefix the run command.
- **No cache keys in Valkey**: Ensure the server was started with `VALKEY_HOST=localhost`.
