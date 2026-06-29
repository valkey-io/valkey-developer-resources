# Portkey AI Gateway + Valkey Cookbook Sample

Runnable code for the [Portkey AI Gateway + Valkey cookbook series](../README.md).

All samples use the official **`portkey-ai`** SDK pointed at a local gateway that
is backed by Valkey.

## Prerequisites

1. **Docker or Podman** (for Valkey)
2. **Node.js 18+** (for the gateway and JS samples)
3. **Python 3.10+** (for the Python samples)

## Setup

```bash
# Start Valkey
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Start the gateway (from the gateway repo root)
export VALKEY_CONNECTION_STRING="valkey://localhost:6379"
npm run build && node build/start-server.js
```

## Running

```bash
# Python (uses the portkey-ai SDK)
cd python
pip install -r requirements.txt
python getting_started.py
python vector_search.py
python production.py

# JavaScript (uses the portkey-ai SDK)
cd js
npm install
node getting_started.mjs
node vector_search.mjs
node production.mjs
```

## Structure

```
sample/
  python/
    getting_started.py    # Cookbook 01 — Portkey SDK + cache backend verification
    vector_search.py      # Cookbook 02 — SDK index CRUD + KNN + filtered search
    production.py         # Cookbook 03 — SDK typed exceptions + monitoring
    requirements.txt
  js/
    getting_started.mjs   # Cookbook 01 — Portkey SDK + cache backend verification
    vector_search.mjs     # Cookbook 02 — SDK index CRUD + KNN + filtered search
    production.mjs        # Cookbook 03 — SDK error handling + monitoring
    package.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8787` | Portkey Gateway base URL (the SDK appends `/v1`) |
| `VALKEY_CUSTOM_HOST` | `valkey://localhost:6379` | Valkey address passed to the gateway as `custom_host` |
| `PROVIDER` | `ollama` | LLM provider for the cached completion (cookbook 01) |
| `PROVIDER_API_KEY` | (unset) | Provider key for a cloud provider (not needed for `ollama`) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL when `PROVIDER=ollama` |
| `MODEL` | `llama3.2:latest` | Model for the cached completion demo |

## Notes

- **Caching requires `"cache": true` in the gateway's `conf.json`** (set before
  `npm run build`). Otherwise responses return `x-portkey-cache-status: DISABLED`.
- `getting_started` runs a real cached completion against a local **Ollama** by
  default (no API key needed). Set `PROVIDER` + `PROVIDER_API_KEY` to use a cloud
  provider instead. Without either, it still verifies SDK → gateway → Valkey.
- The `valkey-search` provider endpoints are reached through the SDK's generic
  `post` / `get` / `delete` methods, the same client used for LLM calls.
