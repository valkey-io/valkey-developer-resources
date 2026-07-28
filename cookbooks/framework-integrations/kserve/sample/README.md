# KServe + Valkey Sample

Validates the Valkey access patterns used by KServe's LLM inference stack:

- **LMCache pattern** — binary KV cache chunk storage (`SET`/`GET`) with model-specific
  key naming (`model@worker@layer@hash@dtype`)
- **Prefix-cache index pattern** — hash-to-pod mapping (block index entries)
- **Feast pattern** — feature serialization and retrieval via Redis-compatible commands

## Quick Start

```bash
# Start Valkey
docker compose up -d

# Install and test
uv venv && uv pip install -e ".[test]"
.venv/bin/pytest tests/ -v

# Tear down
docker compose down -v
```

## What the Tests Validate

- Connectivity, server version, and protocol compatibility
- Binary blob storage for KV cache chunks (multi-MB values)
- Key naming patterns matching LMCache's `ValkeyConnector`
- Concurrent writes from multiple "replicas" (idempotent keys)
- Prefix-cache index CRUD (block hash → pod IP mapping)
- Feature vector storage matching Feast's online store protocol
- TTL and eviction behavior for cache data
- Pipeline/batch operations for bulk feature retrieval

## Requirements

- Python 3.10+
- Docker (for Valkey)
