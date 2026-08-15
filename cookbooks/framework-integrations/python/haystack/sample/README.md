# Haystack + Valkey Sample

> Runnable Python sample demonstrating Haystack's ValkeyDocumentStore and ValkeyEmbeddingRetriever with deterministic vectors.

## Prerequisites

- Docker
- Python 3.10+
- No API key or model download needed for the default path

The sample uses fixed four-dimensional vectors so the default path is deterministic and runs in CI without any external embedding or LLM service.

## Quick Start

```bash
# 1. Start Valkey Bundle (includes search + json modules)
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the demo
python main.py

# 4. Run tests
python -m pytest test_haystack.py -v
```

## Expected Output

```text
=== Haystack + Valkey Demo ===

Indexed 3 documents
Top result: valkey-search (score: 1.000)
Filtered result: valkey-search

=== Demo Complete ===
```

## Running Tests

```bash
python -m pytest test_haystack.py -v
```

Tests verify:

- ValkeyEmbeddingRetriever returns the closest document by cosine similarity
- Metadata filters narrow results to matching documents only
- Environment variable overrides work for host/port/timeout
- Store cleanup closes the connection even on failure

No external APIs or paid services needed — tests use deterministic fixed vectors only.

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | No | `6379` | Valkey server port |
| `VALKEY_REQUEST_TIMEOUT_MS` | No | `5000` | Request timeout in milliseconds |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

The application also removes its documents via `delete_all_documents()` and closes the store connection after each run.
