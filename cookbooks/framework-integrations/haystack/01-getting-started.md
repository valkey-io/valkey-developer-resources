# Getting Started with Haystack + Valkey

> Connect Haystack to Valkey, store documents with embeddings, and run your first vector similarity search — all in under 15 minutes.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building search or RAG applications with Haystack who want to use Valkey as a high-performance, in-memory vector store instead of an external vector database.

Haystack is a framework for building RAG pipelines and search applications. Valkey replaces external vector databases with a single in-memory store that handles both document storage and similarity search.

## Prerequisites

- Docker or Podman installed
- Python 3.10+
- [Ollama](https://ollama.com/) installed and running (free, no API key needed)

## Step 1: Start Valkey

Vector search requires the `valkey-bundle` image, which includes the Search and JSON modules:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1.0
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# should include: name search
```

## Step 2: Pull the Embedding Model

```bash
ollama pull nomic-embed-text
```

This downloads a 274 MB embedding model that produces 768-dimensional vectors. It runs entirely locally.

## Step 3: Install Dependencies

```bash
pip install haystack-ai valkey-haystack ollama-haystack
```

The `valkey-haystack` package provides `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack components. It uses Valkey GLIDE under the hood for high-performance communication.

## Step 4: Connect to ValkeyDocumentStore

```python
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="my_documents",
    embedding_dim=768,         # must match your embedding model (nomic-embed-text = 768)
    distance_metric="cosine",  # cosine | l2 | ip
    metadata_fields={"category": str},  # indexed fields for filtered search
)

print(document_store.count_documents())  # 0
```

> **Note:** On first run you may see `Index not found` — this is expected. The document store creates the index automatically when you write your first documents.
>
> **Lifecycle:** Always call `document_store.close()` when done to release the GLIDE connection. Use try/finally in production code.

## Step 5: Embed and Store Documents

Use Ollama's `OllamaDocumentEmbedder` to generate embeddings and store them in Valkey:

```python
from haystack import Pipeline, Document
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder

docs = [
    Document(content="Valkey is a high-performance in-memory data store."),
    Document(content="Haystack is an open-source LLM framework by deepset."),
    Document(content="Vector search finds semantically similar documents."),
]

indexing_pipeline = Pipeline()
indexing_pipeline.add_component(
    "embedder",
    OllamaDocumentEmbedder(model="nomic-embed-text"),
)
indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store))
indexing_pipeline.connect("embedder.documents", "writer.documents")

indexing_pipeline.run({"embedder": {"documents": docs}})
print(f"Stored {document_store.count_documents()} documents")  # 3
```

## Step 6: Run a Similarity Search

```python
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever

text_embedder = OllamaTextEmbedder(model="nomic-embed-text")
retriever = ValkeyEmbeddingRetriever(document_store=document_store, top_k=2)

query_pipeline = Pipeline()
query_pipeline.add_component("text_embedder", text_embedder)
query_pipeline.add_component("retriever", retriever)
query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")

result = query_pipeline.run({"text_embedder": {"text": "What is Valkey used for?"}})

for doc in result["retriever"]["documents"]:
    print(f"Score: {doc.score:.3f} | {doc.content}")
```

Expected output:

```text
Score: 0.921 | Valkey is a high-performance in-memory data store.
Score: 0.743 | Vector search finds semantically similar documents.
```

## Step 7: Metadata Filtering

Pass filters to narrow results to documents matching specific metadata:

```python
result = query_pipeline.run({"text_embedder": {"text": "What about vector search?"}})

# Filter by category (requires metadata_fields={"category": str} in the store)
filtered = retriever.run(
    query_embedding=result["text_embedder"]["embedding"],
    filters={"field": "meta.category", "operator": "==", "value": "search"},
)

for doc in filtered["documents"]:
    print(f"Filtered: {doc.content}")
```

Metadata filters are applied server-side in Valkey Search — they don't download all documents and filter in Python.

## How It Works

| Component | Role |
|-----------|------|
| `ValkeyDocumentStore` | Stores documents as JSON + embeddings, manages the vector index via FT.CREATE |
| `OllamaDocumentEmbedder` | Generates 768-dim embeddings for documents at index time (runs locally) |
| `OllamaTextEmbedder` | Embeds the user's query at search time |
| `ValkeyEmbeddingRetriever` | Runs KNN search via FT.SEARCH and returns ranked documents |
| Valkey Search module | Provides vector indexing (HNSW) and KNN queries |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `nodes_list` | — | `[("localhost", 6379)]` | Valkey server addresses (list of host/port tuples) |
| `index_name` | — | `"default"` | Name of the vector index |
| `embedding_dim` | — | `768` | Must match your embedding model's output dimensions |
| `distance_metric` | — | `"cosine"` | Similarity metric: `cosine`, `l2`, or `ip` |
| `metadata_fields` | — | `None` | Dict mapping field names to types for filtered search |
| `request_timeout` | — | `5000` | Request timeout in milliseconds |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[02 - RAG Pipeline →](02-rag-pipeline.md)
