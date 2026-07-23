# Knowledge Base

> Build a vector-searchable knowledge base with Agno's `ValkeyDB` — store documents, embed them with Ollama, and find them by semantic similarity.

**Intermediate** · Python · ~15 min

**Who is this for:** Python developers who want to give Agno agents a searchable
knowledge base backed by Valkey's HNSW vector index, using a free local embedder.

## How Agno Knowledge Works

Agno's Knowledge system loads documents, chunks them, embeds the chunks, and stores
them in a vector database. `ValkeyDB` implements the `VectorDb` interface using
the valkey-search module (FT.* commands) for HNSW vector indexing.

```text
Document → chunk → OllamaEmbedder → 768-dim vector → ValkeyDB (HSET + FT.CREATE HNSW)
Query → embed → FT.SEARCH KNN → top-k results → Agent context
```

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Valkey running)
- [Ollama](https://ollama.com/) installed and running
- Embedding model pulled: `ollama pull nomic-embed-text`

## Step 1: Install Dependencies

```bash
pip install "agno[valkey,ollama]==2.8.0"
```

## Step 2: Configure the Embedder

```python
from agno.knowledge.embedder.ollama import OllamaEmbedder

embedder = OllamaEmbedder(
    id="nomic-embed-text",  # 768-dim embedding model
    dimensions=768,
)
```

`nomic-embed-text` produces 768-dimensional vectors. The `dimensions` parameter
tells Agno the expected output size — it validates every embedding matches this.

## Step 3: Create the Vector Store

```python
from agno.vectordb.valkey import ValkeyDB
from agno.vectordb.search import SearchType

vector_db = ValkeyDB(
    index_name="agno_knowledge",
    host="localhost",
    port=6379,
    embedder=embedder,
    search_type=SearchType.vector,
)
```

`ValkeyDB` reads `embedder.dimensions` (768) and uses it to configure the HNSW
index schema. No separate dimension parameter needed.

## Step 4: Load Documents and Search

```python
import asyncio
from agno.knowledge.document.base import Document

async def main():
    # Create the index
    await vector_db.async_create()

    # Insert documents
    docs = [
        Document(name="valkey-intro", content="Valkey is an open-source, high-performance key/value datastore."),
        Document(name="valkey-search", content="The valkey-search module adds full-text and vector search to Valkey."),
        Document(name="valkey-license", content="Valkey is BSD-3 licensed under the Linux Foundation."),
        Document(name="valkey-glide", content="GLIDE is the official Valkey client library, available for multiple languages."),
    ]

    for doc in docs:
        await vector_db.async_insert(
            content_hash=doc.name,
            documents=[doc],
        )

    # Search by semantic similarity
    results = await vector_db.async_search("What search capabilities does Valkey have?", limit=2)

    for doc in results:
        print(f"  [{doc.name}] {doc.content[:80]}")

    # Cleanup
    await vector_db.async_drop()

asyncio.run(main())
```

## Step 5: Wire into an Agent

```python
from agno.agent import Agent
from agno.knowledge.base import Knowledge
from agno.models.ollama import Ollama

knowledge = Knowledge(vector_db=vector_db)

agent = Agent(
    model=Ollama(id="llama3.2"),
    knowledge=knowledge,
    search_knowledge=True,
)

agent.knowledge.load()  # Embed and store documents
agent.print_response("What is Valkey's license?")
```

The agent automatically searches the knowledge base for relevant context before responding.

## How It Works

| Operation | Valkey Command | What It Does |
| --------- | -------------- | ------------ |
| Create index | `FT.CREATE ... ON HASH PREFIX agno_knowledge:` | HNSW vector index setup |
| Store document | `HSET agno_knowledge:{id} content ... embedding <bytes>` | Persist chunk |
| Vector search | `FT.SEARCH idx "(*)=>[KNN k @embedding $vec]"` | Semantic similarity |
| Keyword search | `FT.SEARCH idx "(@content:keyword)"` | Full-text search |
| Delete | `DEL agno_knowledge:{id}` | Remove by key |

## Configuration Reference

| Field | Required | Default | Description |
| ----- | -------- | ------- | ----------- |
| `index_name` | Yes | — | FT.CREATE index name (also key prefix) |
| `host` | No | `localhost` | Valkey hostname |
| `port` | No | `6379` | Valkey port |
| `embedder` | No | `OpenAIEmbedder()` | Embedder instance (always set explicitly) |
| `search_type` | No | `SearchType.vector` | `vector` or `keyword` |
| `distance` | No | `Distance.cosine` | Distance metric (cosine, l2, max_inner_product) |
| `vector_algorithm` | No | `HNSW` | Index algorithm (`HNSW` or `FLAT`) |

## Supported Search Types

| Type | How It Works | When to Use |
| ---- | ------------ | ----------- |
| `vector` | KNN over HNSW index | Semantic similarity (default) |
| `keyword` | Full-text search on TEXT fields | Exact term matching |
| `hybrid` | ❌ Not supported | Use vector or keyword separately |

## Cleanup

```bash
docker stop valkey && docker rm valkey
```

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Per-User Isolation →](03-per-user-isolation.md)
