# Haystack + Valkey Sample

This sample exercises Haystack's `ValkeyDocumentStore` and
`ValkeyEmbeddingRetriever` against a local Valkey Bundle instance.

## Prerequisites

- Python 3.10 or newer
- Docker or Podman with Compose support
- No API key or model download

The sample uses fixed four-dimensional vectors so the default path is
deterministic and can run in CI without an external embedding or LLM service.

## Setup and Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d --wait
.venv/bin/python -m pytest -q
.venv/bin/python main.py
```

Expected output includes:

```text
Indexed 3 documents
Top result: valkey-search
Filtered result: valkey-search
Sample completed successfully
```

The sample uses an unauthenticated localhost connection for development only.
Enable authentication and TLS before connecting to a non-localhost Valkey
deployment.

## Cleanup

```bash
docker compose down -v
```

The application also drops its Search index and documents after each run.
Valkey Search documents do not expire automatically through this integration.
Production applications should define a retention policy and schedule cleanup
for data that can grow without bound.

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname. |
| `VALKEY_PORT` | No | `6379` | Valkey server port. |
| `VALKEY_REQUEST_TIMEOUT_MS` | No | `5000` | Valkey request timeout in milliseconds. |

The sample binds Valkey to localhost and uses an unauthenticated connection
only for local development. Configure authentication and TLS before using a
non-local deployment.

## What It Demonstrates

- Haystack `Document` objects with embeddings and metadata
- `ValkeyDocumentStore.write_documents()` for indexing
- `ValkeyEmbeddingRetriever.run()` for vector search
- Haystack metadata filters passed to the Valkey integration
- Idempotent cleanup through `delete_all_documents()`
