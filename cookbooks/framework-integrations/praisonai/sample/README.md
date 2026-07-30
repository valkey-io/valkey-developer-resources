# PraisonAI + Valkey — Runnable Sample

This directory contains the runnable code and CI-friendly tests for the PraisonAI + Valkey cookbook.

## Files

| File | Description |
| --- | --- |
| `main.py` | Demo covering `ValkeyStateStore` and `ValkeyVectorKnowledgeStore` |
| `test_praisonai.py` | CI tests — no LLM required, deterministic assertions |
| `docker-compose.yml` | Starts Valkey with ValkeySearch (`valkey-bundle:9.1.0`) |
| `requirements.txt` | Pinned Python dependencies |

## Quick Start

```bash
# 1. Start Valkey
docker compose up -d

# 2. Create venv and install deps
uv venv .venv
uv pip install -r requirements.txt --python .venv/bin/python3

# 3. Run the demo (no API key required)
.venv/bin/python main.py

# 4. Run CI tests
.venv/bin/python -m pytest test_praisonai.py -v

# 5. Tear down Valkey
docker compose down -v
```

Substitute `podman compose` for `docker compose` if Podman is your container runtime.

## Expected Output

```text
=== Part 1: Agent State Persistence ===

User   : What is Valkey?
Agent  : Valkey is an open-source, high-performance in-memory key-value store.
User   : Who maintains it?
Agent  : Valkey is maintained by the Linux Foundation Valkey community.

Run count  : 1
Metadata   : {'last_query': 'Who maintains it?', 'run_count': 1}
History    : 4 messages persisted in Valkey
=== Part 2: Vector Knowledge Retrieval ===

Indexed 6 documents.

Q: What client library should I use for Valkey?
  -> Valkey GLIDE is the official client with a Rust core supporting standalone and cluster modes.
  ...

Q: How does vector search work in Valkey?
  -> ValkeySearch adds FT.CREATE and FT.SEARCH commands for full-text and vector similarity search.
  ...

Demo complete.
```

Test output:

```text
14 passed in 0.47s
```

## Requirements

- Python 3.10+
- Docker or Podman (for Valkey container)
