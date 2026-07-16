# Mem0 + Valkey Sample

> Run Mem0's memory API against a local Valkey Search index without external model credentials.

## Prerequisites

- Docker or Podman
- Python 3.9 or newer

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

`numpy==2.2.6` is pinned because it provides wheels for both the Python 3.11
CI runtime and the local Python 3.13 runtime.

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

```bash
.venv/bin/python -m pytest test_mem0.py -v
```

These commands reproduce the relevant steps from the shared Python cookbook
workflow in PR #45:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install ruff==0.11.13
.venv/bin/ruff check --output-format=github .
.venv/bin/python -m pytest test_mem0.py -v
```

The shared workflow should add `framework-integrations/mem0` to its cookbook
matrix and run `test_mem0.py` for this directory. This sample does not add a
second Python workflow.

## Optional LLM and Embeddings

For an application that extracts facts with an LLM, remove `infer=False` and
configure a supported Mem0 LLM provider. For production embeddings, configure
a supported embedder such as OpenAI, Ollama, or a self-hosted provider. These
paths require their own service or credentials and are not part of the default
test path.

## Teardown

The sample removes its `mem0:<collection>:` keys and index when it exits. Stop the Valkey container with:

```bash
docker compose down
```
