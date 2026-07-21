# Haystack + Valkey Sample

> Runnable Python sample demonstrating Haystack RAG pipelines with ValkeyDocumentStore and Ollama.

## Prerequisites

- Docker or Podman
- Python 3.10+
- [Ollama](https://ollama.com/) installed and running

## Quick Start

```bash
# 1. Start Valkey Bundle (includes search + json modules)
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0

# 2. Pull Ollama models
ollama pull nomic-embed-text
ollama pull llama3.2:1b

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the demo
python main.py
```

## Expected Output

```text
=== Haystack + Valkey RAG Demo ===

Connecting to ValkeyDocumentStore...
Connected. Current documents: 0

Indexing documents with Ollama embeddings...
Indexed 5 documents.

--- Similarity Search: "What is Valkey?" ---
  Score: 0.912 | Valkey is an open-source, high-performance in-memory data store.
  Score: 0.745 | Valkey supports vector search natively via its search module.

--- RAG Query: "How does Valkey integrate with Haystack?" ---
  Answer: The ValkeyDocumentStore integrates with Haystack pipelines...

=== Demo Complete ===
```

## Running Tests

Tests use Haystack's built-in `MockDocumentEmbedder` — no Ollama needed:

```bash
python -m pytest test_haystack.py -v
```

Tests verify:

- ValkeyDocumentStore connection and document count
- Write documents with embeddings via pipeline
- ValkeyEmbeddingRetriever returns ranked results
- top_k parameter is respected

## Teardown

```bash
docker stop valkey && docker rm valkey
```
