# Mem0 + Valkey Sample

> Run Mem0's memory API against a local Valkey Search index without external model credentials.

## Prerequisites

- Docker
- Python 3.10 or newer

## Run

From this directory:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

The Compose file includes a health check. With an older Compose version, run
`docker compose up -d` and verify the service with
`docker compose exec -T valkey valkey-cli ping` before running the sample.

The sample uses Mem0's built-in `MockEmbeddings` and calls
`Memory.add(..., infer=False)`, so it does not contact an LLM or embedding
service. It demonstrates the same Mem0 API used in the cookbook: configure the
Valkey provider, add memories, search with a user filter, and list a user's
memories.

The dependency is the official `valkey` Python client because Mem0's released
Valkey connector constructs its `ValkeyDB` store with `valkey.from_url()`.
GLIDE is not a drop-in replacement for that framework-owned connector.

`numpy==2.0.2` is pinned for compatibility with the supported Python runtimes.

## Expected Output

The output contains one Alice memory from a filtered semantic search and one
Bob memory from `get_all`. The records also include Mem0-generated IDs and
timestamps. Representative output, with those variable fields omitted:

```text
=== Mem0 + Valkey Demo ===
Alice search:
[
  {
    "memory": "Alice prefers Python for data work."
  }
]
Bob memories:
[
  {
    "memory": "Bob prefers TypeScript for web apps."
  }
]
```

## Tests

Run the integration tests after starting the Compose service:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install ruff==0.11.13
.venv/bin/ruff check --output-format=github .
.venv/bin/python -m pytest test_mem0.py -v
```

## Optional LLM and Embeddings

For an application that extracts facts with an LLM, remove `infer=False` and
configure a supported Mem0 LLM provider such as Ollama, as shown in
[`../01-getting-started.md`](../01-getting-started.md).
For embeddings, use Ollama's `nomic-embed-text` (local) or another supported
embedder. These paths require their own service or credentials and are not part
of the default test path.

## Teardown

The sample removes its `mem0:<collection>:` keys and index when it exits. Stop the Valkey container with:

```bash
docker compose down
```
