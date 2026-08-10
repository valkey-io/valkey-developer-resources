# Getting Started with DocsGPT and Valkey

> Start a Valkey instance with the search module, configure DocsGPT to use Valkey as its vector store, and verify connectivity from Python.

**Beginner** · Python · ~15 min

**Who is this for:** Developers running DocsGPT who want to use Valkey's native vector search instead of a separate vector database (FAISS, Qdrant, Milvus, etc.).

## Prerequisites

- Python 3.10+
- Docker (for running Valkey)
- Git

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey with the Search Module

DocsGPT's vector store requires the `valkey-search` module for `FT.CREATE` and `FT.SEARCH` commands. Use the `valkey-bundle` image which includes it:

```bash
docker run -d --name valkey-docsgpt \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

Verify the search module is loaded:

```bash
docker exec valkey-docsgpt valkey-cli MODULE LIST
# Should show "search" in the output
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Clone and Configure DocsGPT

```bash
git clone https://github.com/arc53/DocsGPT.git
cd DocsGPT
cp .env-template .env
```

Edit `.env` and set:

```env
VECTOR_STORE=valkey
VALKEY_HOST=localhost
VALKEY_PORT=6379
# VALKEY_PASSWORD=
# VALKEY_USE_TLS=false
# VALKEY_INDEX_NAME=docsgpt
# VALKEY_PREFIX=doc:
# VALKEY_DISTANCE_METRIC=cosine
# VALKEY_VECTOR_ALGORITHM=hnsw
```

## Step 3: Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r application/requirements.txt
```

This installs `valkey-glide-sync` (≥2.3.1 required) which provides the synchronous GLIDE client for Valkey.

## Step 4: Verify Connectivity

Create a script to verify Valkey is reachable and the search module is loaded:

```python
"""Verify Valkey connectivity and search module availability."""
from __future__ import annotations

import struct

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)


def main() -> None:
    """Connect to Valkey and verify the search module is available."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)]
    )
    client = GlideClient.create(config)

    # Basic connectivity
    pong = client.ping()
    print(f"✓ Connected to Valkey: {pong}")

    # Verify search module via FT.CREATE + FT.DROPINDEX
    test_index = "__docsgpt_connectivity_test__"
    client.custom_command(
        ["FT.CREATE", test_index, "ON", "HASH", "PREFIX", "1", "__test__:",
         "SCHEMA", "vec", "VECTOR", "FLAT", "6",
         "TYPE", "FLOAT32", "DIM", "3", "DISTANCE_METRIC", "COSINE"]
    )
    print("✓ valkey-search module is available (FT.CREATE succeeded)")

    # Clean up test index
    client.custom_command(["FT.DROPINDEX", test_index])
    print("✓ Cleanup complete (FT.DROPINDEX succeeded)")

    # Verify HASH operations (the storage pattern DocsGPT uses)
    test_key = "__docsgpt_test_hash__"
    embedding = [0.1, 0.2, 0.3]
    vector_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
    client.hset(test_key, {"vector": vector_bytes, "content": "test"})
    result = client.hget(test_key, "content")
    assert result == b"test", f"Expected b'test', got {result}"
    client.delete([test_key])
    print("✓ HASH operations work (vector store pattern)")

    client.close()
    print("\n✅ All checks passed — Valkey is ready for DocsGPT!")


if __name__ == "__main__":
    main()
```

Run the connectivity check:

```bash
python sample/scripts/getting_started.py
```

Expected output:

```text
✓ Connected to Valkey: PONG
✓ valkey-search module is available (FT.CREATE succeeded)
✓ Cleanup complete (FT.DROPINDEX succeeded)
✓ HASH operations work (vector store pattern)

✅ All checks passed — Valkey is ready for DocsGPT!
```

## Step 5: Run DocsGPT

Start the backend:

```bash
flask --app application/app.py run --host=0.0.0.0 --port=7091
```

DocsGPT creates the Valkey search index on first use. You can now ingest documents through the UI or API — they'll be stored as vector embeddings in Valkey.

## How It Works Under the Hood

When you ingest a document, DocsGPT:

1. **Chunks** the document into passages
2. **Embeds** each chunk using the configured embedding model
3. **Stores** each chunk as a Valkey HASH with fields: `content`, `source_id`, `metadata`, `embedding`
4. **Indexes** the embeddings with an HNSW vector index via `FT.CREATE`

When you ask a question:

1. The query is embedded into a vector
2. `FT.SEARCH` performs KNN search filtered by `source_id`
3. Top-k results are returned as context for the LLM

| Operation | Valkey Command | What It Does |
| --- | --- | --- |
| Create index | `FT.CREATE docsgpt ON HASH PREFIX doc: SCHEMA ...` | One-time index setup |
| Store chunk | `HSET doc:{uuid} content "..." source_id "..." embedding <bytes>` | Store document with vector |
| Search | `FT.SEARCH docsgpt @source_id:{id} =>[KNN k @embedding $BLOB]` | Vector similarity search |
| Delete source | `FT.SEARCH` + `DEL` per key | Remove all chunks for a source |

## Configuration Reference

| Environment Variable | Default | Description |
| --- | --- | --- |
| `VECTOR_STORE` | `faiss` | Set to `valkey` to use Valkey |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `VALKEY_PASSWORD` | (none) | Password for authentication |
| `VALKEY_USE_TLS` | `false` | Enable TLS connections |
| `VALKEY_INDEX_NAME` | `docsgpt` | Name of the search index |
| `VALKEY_PREFIX` | `doc:` | Key prefix for document hashes |
| `VALKEY_DISTANCE_METRIC` | `cosine` | Distance metric: `cosine`, `l2`, `ip` |
| `VALKEY_VECTOR_TYPE` | `float32` | Vector element type |
| `VALKEY_VECTOR_ALGORITHM` | `hnsw` | Index algorithm: `hnsw` or `flat` |

## Troubleshooting

| Issue | Solution |
| --- | --- |
| `ImportError: No module named 'glide_sync'` | Run `pip install valkey-glide-sync` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:9.1.0` or add `--loadmodule` flag |
| Empty search results | Verify `source_id` matches what was used during ingestion |
| `NOAUTH Authentication required` | Set `VALKEY_PASSWORD` in your `.env` file |

## What's Next

- [Ingestion & Retrieval](./02-ingestion-and-retrieval.md) — Deep dive into chunking, HNSW indexing, and filtered vector search

---

[← Back to cookbook index](./README.md)
