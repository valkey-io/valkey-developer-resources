# Getting Started with Cognee + Valkey

**Beginner** · Python · ~15 min

## What is Cognee?

[Cognee](https://github.com/topoteretes/cognee) is an open-source AI memory system that builds knowledge graphs from your data. Unlike traditional RAG that retrieves raw text chunks, Cognee extracts entities and relationships to provide more accurate, contextual answers.

The [cognee-community-vector-adapter-valkey](https://github.com/topoteretes/cognee-community) package provides a **first-class Valkey integration** using `valkey-glide` for high-performance vector storage and retrieval with Valkey Search.

## Step 1: Install

```bash
pip install cognee-community-vector-adapter-valkey boto3
```

This installs:
- `cognee` (core framework)
- `valkey-glide` (official Valkey client)
- `boto3` (for AWS Bedrock — or use OpenAI if preferred)

## Step 2: Start Valkey with Search Module

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

> **Note**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module required for vector indexing.

## Step 3: Configure Cognee with Valkey and Bedrock

```python
import os
import pathlib
from os import path

# Disable multi-user access control (Valkey adapter doesn't support it yet)
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"

# Configure AWS Bedrock as the LLM and embedding provider
os.environ["LLM_PROVIDER"] = "bedrock"
os.environ["LLM_MODEL"] = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
os.environ["EMBEDDING_PROVIDER"] = "bedrock"
os.environ["EMBEDDING_MODEL"] = "bedrock/amazon.titan-embed-text-v2:0"
os.environ["EMBEDDING_DIMENSIONS"] = "1024"
os.environ["AWS_REGION"] = "us-east-1"

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

> **Using OpenAI instead?** Set `LLM_API_KEY`, `LLM_PROVIDER=openai`, and `LLM_MODEL=gpt-4o`. The Valkey integration works the same regardless of LLM provider.

## Step 4: Register the Valkey Adapter

```python
from cognee_community_vector_adapter_valkey import register  # noqa: F401
```

Importing `register` hooks the Valkey adapter into Cognee's plugin system. No further configuration needed.

## Step 5: Add Documents and Build Knowledge Graph

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

## What's Happening in Valkey?

After running the example, Cognee creates:
- **Vector indices** (`FT.CREATE`) with HNSW algorithm and cosine distance
- **JSON documents** (`JSON.SET`) containing embeddings and metadata
- **Key prefix** pattern: `vdb:<collection_name>:<id>`

You can inspect with:

```bash
valkey-cli FT._LIST
valkey-cli FT.INFO "index:<collection_name>"
```

## Next Steps

- [02 - Knowledge Graph](02-knowledge-graph.md): Understand how Cognee builds and queries knowledge graphs on top of Valkey vectors.
