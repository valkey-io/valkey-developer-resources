# Haystack + Valkey Sample

> Runnable Python sample demonstrating Haystack's ValkeyDocumentStore and ValkeyEmbeddingRetriever with local semantic embeddings.

## Prerequisites

- Docker
- Python 3.10+
- Internet access for the first model download (no API key required)

The sample uses the local `sentence-transformers/all-MiniLM-L6-v2` model for both
document and query embeddings. The public 384-dimensional model downloads on its
first run and then uses the local cache. It does not require an API key or a paid
embedding service.

## Quick Start

```bash
# 1. Start Valkey Bundle (includes Valkey-Search and Valkey JSON modules)
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.2

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
Top result: valkey-search
Filtered result: valkey-search

=== Demo Complete ===
```

## Running Tests

```bash
python -m pytest test_haystack.py -v
```

Tests verify:

- Documents and queries are embedded with the same local model before retrieval
- ValkeyEmbeddingRetriever ranks the semantically relevant document first
- Metadata filters narrow semantic results to matching documents only
- Environment variable overrides work for host/port/timeout
- Store cleanup closes the connection even on failure

The tests download the same public local model on a cold cache. They do not use
an external embedding API or fabricated vectors.

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
