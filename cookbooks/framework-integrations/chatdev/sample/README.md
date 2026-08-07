# ChatDev + Valkey — Sample Code

Runnable, standalone sample demonstrating a `ValkeyMemory`-style store/retrieve API,
independently reproducing the verified Valkey behavior from ChatDev's
[`ValkeyMemory` backend](https://github.com/OpenBMB/ChatDev/pull/634) (open/unmerged
upstream PR). This sample does not import ChatDev — see [Upstream Status](../README.md#upstream-status)
in the track README for why.

## Prerequisites

1. **Valkey** running with the Search module:

   ```bash
   docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
   ```

   Podman alternative:

   ```bash
   podman run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
   ```

   Or with Docker Compose:

   ```bash
   docker compose up -d
   ```

2. **Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   No API key or model download is required — the default embedding provider
   is deterministic and local (see `embeddings.py`).

## Running

```bash
python quick_start.py
```

### Expected Output

```text
=== ChatDev + Valkey: Quick Start ===

--- Storing Memories ---
  [coder] Python is great for data science and ML pipelines -> quickstart:<uuid>
  [designer] The dashboard should use a dark theme with high contrast -> quickstart:<uuid>
  [coder] We need integration tests for the authentication module -> quickstart:<uuid>
  [designer] Use material design icons for the navigation bar -> quickstart:<uuid>

--- Filtered Retrieval (agent_role='coder', query='Python testing') ---
  [0.xxx] (coder) ...

--- Unfiltered Retrieval (agent_role=None, query='design theme') ---
  [0.xxx] (designer) ...

--- Threshold Filtering (similarity_threshold=0.99) ---
  0 result(s) passed the 0.99 threshold

Total memories stored: 4

All quick start checks passed.
```

## Testing

```bash
pytest test_valkey_memory.py -v
```

Tests require the same running Valkey instance as `quick_start.py`.

## Files

| File | Description |
| --- | --- |
| `valkey_memory.py` | Standalone reimplementation of ValkeyMemory: schema, sanitization, store/retrieve/expire, error degradation |
| `embeddings.py` | Deterministic default embedding provider + optional OpenAI/Ollama providers |
| `quick_start.py` | Store and retrieve memories, asserting expected behavior at each step |
| `test_valkey_memory.py` | Unit + integration tests against a live Valkey instance |
| `docker-compose.yml` | One-command Valkey startup |
| `requirements.txt` | Pinned Python dependencies (`valkey-glide-sync`, `pytest` only) |
| `.env.example` | Safe local connection and optional provider settings |
| `.gitignore` | Excludes `.env`, virtual environments, and Python caches |

## Teardown

```bash
docker compose down -v
```

Or, if started with `docker run`:

```bash
docker stop valkey && docker rm valkey
```
