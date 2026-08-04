# Getting Started with Cognee + Valkey

> Install Cognee, register the Valkey vector adapter, add documents, build a knowledge graph, and search it.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building RAG or agent-memory systems who want Cognee's knowledge-graph layer backed by a self-hosted, open-source vector store instead of a proprietary vector database.

## What is Cognee?

[Cognee](https://github.com/topoteretes/cognee) is an open-source AI memory system that builds knowledge graphs from your data.
Unlike traditional RAG that retrieves raw text chunks, Cognee extracts entities and relationships to provide more accurate, contextual answers.

The [cognee-community-vector-adapter-valkey](https://github.com/topoteretes/cognee-community) package provides a Valkey integration
using `valkey-glide` for vector storage and retrieval through the Valkey Search module.

## Prerequisites

- Python 3.11+
- Docker or Podman
- [Ollama](https://ollama.com/) installed locally, with the models pulled (Step 1)

## Step 1: Install

```bash
pip install cognee-community-vector-adapter-valkey==0.1.3
```

This installs `cognee` (core framework), `valkey-glide` (official Valkey client), and their dependencies.

This cookbook uses [Ollama](https://ollama.com/) for both knowledge extraction and embeddings, so the whole example runs locally with no API key or cloud account:

```bash
ollama pull qwen2.5:7b       # ~4.7 GB — smaller models often fail to follow
                              # the structured-output format cognify()/search() require
ollama pull nomic-embed-text
```

> **Using a hosted LLM instead?** See [Step 3](#step-3-configure-cognee-with-ollama) for OpenAI and Amazon Bedrock alternatives — the Valkey integration works identically regardless of LLM/embedding provider.

## Step 2: Start Valkey with the Search Module

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

<!-- -->

> **Note**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module required for vector indexing.

## Step 3: Configure Cognee with Ollama

Cognee reads its LLM and embedding configuration from environment variables. For the local Ollama path,
`LLM_ENDPOINT`/`EMBEDDING_ENDPOINT` and a placeholder `LLM_API_KEY`/`EMBEDDING_API_KEY` are required even though Ollama doesn't check them:

```python
import os
import pathlib
from os import path

# Disable multi-user access control (Valkey adapter doesn't support it yet)
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

# Ollama for knowledge extraction (LLM) and embeddings — free, local, no API key
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_MODEL", "qwen2.5:7b")
os.environ.setdefault("LLM_ENDPOINT", "http://localhost:11434/v1")
os.environ.setdefault("LLM_API_KEY", "ollama")  # placeholder — Ollama ignores this
os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text")
os.environ.setdefault("EMBEDDING_ENDPOINT", "http://localhost:11434/api/embeddings")
os.environ.setdefault("EMBEDDING_API_KEY", "ollama")  # placeholder — Ollama ignores this
os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
# Local tokenizer for counting tokens against the embedding model (nomic-embed-text)
os.environ.setdefault("HUGGINGFACE_TOKENIZER", "nomic-ai/nomic-embed-text-v1.5")

from cognee import config

# Set data directories
system_path = pathlib.Path(__file__).parent
config.system_root_directory(path.join(system_path, ".cognee-system"))
config.data_root_directory(path.join(system_path, ".cognee-data"))

# Point Cognee at Valkey
config.set_vector_db_config({
    "vector_db_provider": "valkey",
    "vector_db_url": "valkey://localhost:6379",
})
```

<details>
<summary>Alternative: Using OpenAI instead of Ollama</summary>

```python
os.environ["LLM_PROVIDER"] = "openai"
os.environ["LLM_MODEL"] = "gpt-4o-mini"
os.environ["LLM_API_KEY"] = "sk-..."  # requires OPENAI_API_KEY-style credentials
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
os.environ["EMBEDDING_DIMENSIONS"] = "1536"
```

</details>

<details>
<summary>Alternative: Using Amazon Bedrock instead of Ollama</summary>

Amazon Bedrock is a paid AWS service. This alternative is provided for AWS users who already have Bedrock model access enabled — it requires AWS credentials and is billed per token.

```bash
pip install boto3
```

```python
os.environ["LLM_PROVIDER"] = "bedrock"
os.environ["LLM_MODEL"] = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
os.environ["EMBEDDING_PROVIDER"] = "bedrock"
os.environ["EMBEDDING_MODEL"] = "bedrock/amazon.titan-embed-text-v2:0"
os.environ["EMBEDDING_DIMENSIONS"] = "1024"
os.environ["AWS_REGION"] = "us-east-1"
```

</details>

## Step 4: Register the Valkey Adapter

```python
from cognee_community_vector_adapter_valkey import register  # noqa: F401
```

Importing `register` hooks the Valkey adapter into Cognee's plugin system as the `"valkey"` vector database provider. No further configuration needed.

## Step 5: Add Documents and Build the Knowledge Graph

> **Note**: Steps 5 and 6 are shown as separate snippets for clarity. See `sample/quick_start.py` for a complete runnable script.

```python
import asyncio
from cognee import add, cognify, prune

async def main():
    # Clean slate
    await prune.prune_data()
    await prune.prune_system(metadata=True)

    # Add documents
    await add("""
    Natural language processing (NLP) is an interdisciplinary
    subfield of computer science and information retrieval.
    """)

    await add("""
    Valkey is an open-source, high-performance key-value datastore
    that supports vector similarity search through the Valkey Search module.
    """)

    # Build knowledge graph (extracts entities, relationships, embeddings)
    await cognify()

asyncio.run(main())
```

`cognify()` does the heavy lifting:

1. Chunks your documents
2. Extracts entities and relationships using the LLM
3. Generates embeddings
4. Stores vectors in Valkey using HNSW indexing

## Step 6: Search

```python
from cognee import SearchType, search

async def query():
    results = await search(
        query_type=SearchType.GRAPH_COMPLETION,
        query_text="Tell me about NLP",
    )

    for result in results:
        print(f"Result: {result}")

asyncio.run(query())
```

`GRAPH_COMPLETION` combines vector similarity with knowledge graph traversal for richer answers than pure vector search.

## How It Works

| Component | Role |
|-----------|------|
| `cognee` | Chunks documents, extracts entities/relationships via the LLM, orchestrates the knowledge graph pipeline |
| `cognee_community_vector_adapter_valkey` | Registers Valkey as a Cognee vector database provider using `valkey-glide` |
| Valkey (`valkey-search` module) | Stores embeddings as HNSW vector indices (`FT.CREATE`) for similarity search |
| Valkey (`valkey-json` module) | Stores each data point as a JSON document (`JSON.SET`) under a `vdb:<collection_name>:<id>` key prefix |
| Ollama | Serves the local LLM (knowledge extraction, search completion) and embedding model |

> **Module requirement**: Cognee stores documents as JSON and creates vector indices, so both the `valkey-search` and `valkey-json`
> modules are required. The `valkey/valkey-bundle` Docker image includes both modules out of the box.

You can inspect what Cognee created with:

```bash
docker exec -it valkey valkey-cli FT._LIST
docker exec -it valkey valkey-cli FT.INFO "index:<collection_name>"
```

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `vector_db_provider` | ✓ | — | Set to `"valkey"` after importing `register` |
| `vector_db_url` | ✓ | — | `valkey://host:port` (dev) or `valkeys://host:port` (TLS/production) |
| `LLM_PROVIDER` | ✓ | `openai` | `ollama`, `openai`, or `bedrock` |
| `LLM_MODEL` | ✓ | — | Model name/ID for the chosen provider |
| `EMBEDDING_PROVIDER` | ✓ | `openai` | `ollama`, `openai`, or `bedrock` |
| `EMBEDDING_MODEL` | ✓ | — | Embedding model name/ID for the chosen provider |
| `EMBEDDING_DIMENSIONS` | ✓ | — | Must match the embedding model's output dimension |
| `ENABLE_BACKEND_ACCESS_CONTROL` | — | `true` | Set `false` for this cookbook — the Valkey adapter doesn't yet support Cognee's multi-user access control |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[02 - Knowledge Graph →](02-knowledge-graph.md)
