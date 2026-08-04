# Knowledge Graph with Cognee + Valkey

> Understand how Cognee builds and queries knowledge graphs on top of Valkey-stored vector embeddings.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers who completed [01 - Getting Started](01-getting-started.md) and want to understand Cognee's search types,
multi-document reasoning, and how to call the Valkey adapter directly for advanced scenarios.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module
- Ollama running locally with `qwen2.5:7b` and `nomic-embed-text` pulled

## Step 1: How Cognee Differs from Traditional RAG

Traditional RAG retrieves text chunks by vector similarity alone. Cognee adds a **knowledge graph layer** — it extracts entities and
relationships from your documents, stores the embeddings in Valkey, and traverses the graph at query time for more accurate, contextual answers.

```text
Traditional RAG:  Document → Chunks → Embeddings → Vector Search → LLM
Cognee:           Document → Entities/Relations → Knowledge Graph + Embeddings → Graph Traversal + Vector Search → LLM
```

## Step 2: Search Types

Cognee supports multiple search strategies. The primary one for knowledge graph queries is `GRAPH_COMPLETION`:

```python
from cognee import SearchType, search

# Graph completion — combines vector search with knowledge graph traversal
results = await search(
    query_type=SearchType.GRAPH_COMPLETION,
    query_text="How does NLP relate to information retrieval?",
)
```

Other search types available in Cognee 0.5.5:

| Search Type | Use Case | Notes |
|---|---|---|
| `GRAPH_COMPLETION` | Q&A, chatbots | Vector search + graph traversal, LLM synthesizes answer |
| `GRAPH_SUMMARY_COMPLETION` | Summarization | Graph-based summary generation |
| `RAG_COMPLETION` | Traditional RAG | Retrieval-augmented generation |
| `CHUNKS` | Raw retrieval | Pure vector similarity on document chunks (requires chunk embeddings) |
| `SUMMARIES` | Summary search | Search over document summaries (requires summary pipeline) |

> **Note**: `GRAPH_COMPLETION` is the recommended search type — it works out of the box with `cognify()` and leverages Cognee's knowledge graph for richer answers.

## Step 3: Multi-Document Relationships

Cognee's power shows when documents reference shared concepts:

```python
from cognee import add, cognify

# Add related documents
await add("""
Machine learning is a subset of artificial intelligence that
enables systems to learn from data without explicit programming.
""")

await add("""
Deep learning uses neural networks with multiple layers.
It has revolutionized natural language processing and computer vision.
""")

await add("""
Transformers are a deep learning architecture introduced in 2017.
They form the basis of models like BERT and GPT.
""")

# Build unified knowledge graph across all documents
await cognify()
```

After `cognify()`, Cognee connects concepts across documents — for example, linking "transformers" to "deep learning" to "artificial
intelligence" even though no single document states the full chain. Querying "How do transformers relate to AI?" traverses these connections at search time.

## Step 4: How Valkey Stores the Graph Data

Cognee uses Valkey for the **vector layer** of its architecture:

```text
┌─────────────────────────────────────────────┐
│  Cognee Architecture                        │
├─────────────────────────────────────────────┤
│  Graph DB (Kuzu/Neo4j)  ← entities/relations│
│  Vector DB (Valkey)     ← embeddings        │
│  Relational DB (SQLite) ← metadata          │
└─────────────────────────────────────────────┘
```

In Valkey, each data point is stored as a JSON document:

```json
{
  "id": "abc123",
  "vector": [0.012, -0.034],
  "payload_data": "{\"text\": \"...\", \"metadata\": {}}"
}
```

The adapter creates HNSW indices for approximate nearest-neighbor search:

```text
FT.CREATE index:<collection>
  ON JSON PREFIX 1 vdb:<collection>:
  SCHEMA
    $.id AS id TAG
    $.vector AS vector VECTOR HNSW 6
      TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE
```

## Step 5: Using the Valkey Adapter Directly

For advanced scenarios (batch search, custom collection management), you can use `ValkeyAdapter` directly instead of going through Cognee's high-level `add`/`cognify`/`search` API:

```python
from cognee_community_vector_adapter_valkey import ValkeyAdapter
from cognee.infrastructure.databases.vector.embeddings import get_embedding_engine

adapter = ValkeyAdapter(
    url="valkey://localhost:6379",
    embedding_engine=get_embedding_engine(),
)

# Batch search with concurrency control
results = await adapter.batch_search(
    collection_name="my_collection",
    query_texts=["query 1", "query 2", "query 3"],
    limit=10,
    max_concurrency=5,
    score_threshold=0.1,
)
```

See `sample/knowledge_graph.py` for a complete runnable script that exercises multi-document search.

## Step 6: Incremental Knowledge Building

Cognee supports adding documents incrementally — each `cognify()` call extends the existing knowledge graph:

```python
# Batch 1: Add initial documents
await add("First batch of documents...")
await cognify()

# Batch 2: Add more documents — graph grows, connections form
await add("New documents that reference earlier concepts...")
await cognify()
```

The Valkey vector indices persist across runs. New embeddings are added to existing collections without rebuilding.

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Patterns →](03-production.md)
