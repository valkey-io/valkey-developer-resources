# Agno + Valkey Sample

Runnable examples demonstrating Agno's Valkey integration for agent storage and vector search.

## Prerequisites

- Docker or Podman (container runtime)
- Python 3.10+
- [Ollama](https://ollama.com/) (for knowledge base examples)

## Quick Start

```bash
# Start Valkey
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0

# Install dependencies
pip install -r requirements.txt

# Run storage demo (no LLM needed)
python agent_storage.py

# Run knowledge base demo (requires Ollama + nomic-embed-text)
ollama pull nomic-embed-text
python knowledge_base.py

# Run per-user isolation demo
python per_user_isolation.py
```

## Running Tests (CI-Friendly)

Tests use the storage adapter only — no LLM or embedding model required:

```bash
python -m pytest test_storage.py -v
```

## Expected Output

### agent_storage.py

```text
Sessions stored in Valkey: 1
✓ Session persistence verified
```

### knowledge_base.py

```text
Inserted 4 documents into ValkeyDB

--- Vector Search: 'search capabilities' ---
  [valkey-search] The valkey-search module adds full-text and vector search capabilities.
  [valkey-intro] Valkey is an open-source, high-performance key/value datastore.

--- Keyword Search: 'BSD' ---
  [valkey-license] Valkey is BSD-3 licensed under the Linux Foundation.

✓ All operations successful
```

### per_user_isolation.py

```text
=== Per-User Isolation Demo ===

Alice asks about salary → 2 results
  - Alice's salary is $180,000. Reviewed annually in March.
  - The company is closed on January 1, July 4, and December 25.

  ✓ Isolation holds: Bob's salary NOT visible to Alice

Bob asks about holidays → 2 results
  - The company is closed on January 1, July 4, and December 25.
  - Bob's salary is $215,000. Reviewed annually in June.

Admin search → 3 results (sees all)
  - Alice's salary is $180,000. Reviewed annually in March.
  - Bob's salary is $215,000. Reviewed annually in June.
  - The company is closed on January 1, July 4, and December 25.

✓ Demo complete
```

## Teardown

```bash
docker stop valkey && docker rm valkey
```

## Images Used

| Image | Version | Purpose |
| ----- | ------- | ------- |
| `valkey/valkey-bundle` | `9.1.0` | Valkey with search module |

## References

- [Agno Valkey PR #8141](https://github.com/agno-agi/agno/pull/8141) — integration implementation
- [Agno Docs PR #700](https://github.com/agno-agi/docs/pull/700) — official documentation
- [Agno Documentation](https://docs.agno.com/)
