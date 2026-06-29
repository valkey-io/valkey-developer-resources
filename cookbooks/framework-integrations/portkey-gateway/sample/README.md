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

# JavaScript (uses the portkey-ai SDK)
cd js
npm install
node getting_started.mjs
node vector_search.mjs
```

## Structure

```
sample/
  python/
    getting_started.py    # Cookbook 01 — Portkey SDK + cache backend verification
    vector_search.py      # Cookbook 02 — SDK index CRUD + KNN + filtered search
    requirements.txt
  js/
    getting_started.mjs   # Cookbook 01 — Portkey SDK + cache backend verification
    vector_search.mjs     # Cookbook 02 — SDK index CRUD + KNN + filtered search
    package.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8787` | Portkey Gateway base URL (the SDK appends `/v1`) |
| `VALKEY_CUSTOM_HOST` | `valkey://localhost:6379` | Valkey address passed to the gateway as `custom_host` |
| `PROVIDER` | `openai` | LLM provider for the cached completion (cookbook 01) |
| `PROVIDER_API_KEY` | (falls back to `OPENAI_API_KEY`) | Provider key for the LLM provider |
| `MODEL` | `gpt-4o-mini` | Model for the cached completion demo |

## Notes

- **Caching requires `"cache": true` in the gateway's `conf.json`** (set before
  `npm run build`). Otherwise responses return `x-portkey-cache-status: DISABLED`.
- `getting_started` runs a cached completion against **OpenAI** by default.
  Set `OPENAI_API_KEY` in your environment. Use `PROVIDER` + `PROVIDER_API_KEY`
  to use a different cloud provider instead.
- The `valkey-search` provider endpoints are reached through the SDK's generic
  `post` / `get` / `delete` methods, the same client used for LLM calls.
