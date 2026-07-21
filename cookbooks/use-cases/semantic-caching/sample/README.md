# Semantic Caching Sample

> Runnable Python sample demonstrating semantic caching with Valkey vector search and Ollama embeddings.

## Prerequisites

- Docker or Podman
- Valkey Bundle 9.0+ (requires the Search module; plain `valkey/valkey` won't work)
- Python 3.9+
- [Ollama](https://ollama.com/) installed and running

## Quick Start

```bash
# 1. Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0

# 2. Pull the embedding model
ollama pull nomic-embed-text

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the sample
python main.py
```

## Expected Output

```text
=== Semantic Cache Demo ===

Creating cache index...
Cache index created

--- Query 1: "What is Valkey?" ---
Source: llm, Latency: ~1200ms
Response: Valkey is an open-source in-memory data store...

--- Query 2: "Can you explain what Valkey is?" (semantically similar) ---
Source: cache, Latency: ~15ms, Similarity: 0.08
Response: Valkey is an open-source in-memory data store...

--- Query 3: "How do I cook pasta?" (different topic) ---
Source: llm, Latency: ~980ms
Response: To cook pasta, bring a large pot of salted water...

Cache Stats: 2 misses, 1 hit (33% hit rate)
```

## Running Tests

```bash
python -m pytest test_cache.py -v
```

Tests run against a local Valkey instance and verify:

- Cache index creation
- Embedding generation
- Cache miss → store → cache hit flow
- Similarity threshold behavior

## Teardown

```bash
docker stop valkey && docker rm valkey
```
