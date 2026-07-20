# RAG Pipeline with Haystack + Valkey

> Build a full retrieval-augmented generation pipeline with Valkey as the vector store. Embed your documents once, then answer questions grounded in your data - not the LLM's training set.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who want to connect Haystack's embedding, retrieval, prompt, and generation components to Valkey Search.

## How RAG Works

```text
User question
  → embed question
  → find similar docs in Valkey (KNN)
  → inject docs into prompt
  → LLM generates grounded answer
```

Valkey handles the retrieval step with in-memory KNN over your document
embeddings.

## Prerequisites

- Python 3.10 or newer
- Docker or Podman
- A running `valkey/valkey-bundle:9.1.1` container with Valkey Search
- Dependencies installed from the [runnable sample](sample/README.md)
- An `OPENAI_API_KEY` only if you run the optional generator path

The default sample uses fixed embeddings and a local answer formatter, so it
does not require an API key, model download, or external service. The
model-backed walkthrough on this page is optional and requires the
`sentence-transformers` package plus its model download.

The local connection below is unauthenticated and binds to localhost. For any
non-local deployment, enable authentication and TLS. See the [Valkey security
documentation](https://valkey.io/topics/security/).

## Step 1: Indexing Pipeline

Run this once to embed and store your documents. The five documents use stable
IDs and an overwrite policy so rerunning the indexing block does not accumulate
duplicates:

```python
from haystack import Pipeline, Document
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs",
    embedding_dim=768,
    distance_metric="cosine",
    metadata_fields={"category": str},
    request_timeout=5000,
)

try:
    indexing_pipeline = Pipeline()
    document_embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-mpnet-base-v2"
    )
    document_embedder.warm_up()
    indexing_pipeline.add_component(
        "embedder", document_embedder
    )
    indexing_pipeline.add_component(
        "writer", DocumentWriter(document_store=document_store)
    )
    indexing_pipeline.connect("embedder.documents", "writer.documents")

    # Swap these fixtures for file loaders, web crawlers, or other sources.
    docs = [
        Document(
            id="valkey-search",
            content="Valkey supports vector search natively via its module system.",
        ),
        Document(
            id="haystack-store",
            content="The ValkeyDocumentStore integrates directly with Haystack pipelines.",
        ),
        Document(
            id="cosine-similarity",
            content="Cosine similarity measures the angle between two embedding vectors.",
        ),
        Document(
            id="rag-grounding",
            content="RAG grounds LLM responses in retrieved facts, reducing hallucinations.",
        ),
        Document(
            id="haystack-composable",
            content="Haystack pipelines are composable - swap any component without rewriting the rest.",
        ),
    ]

    indexing_pipeline.run(
        {
            "embedder": {"documents": docs},
            "writer": {"policy": DuplicatePolicy.OVERWRITE},
        }
    )
    print(f"Indexed {document_store.count_documents()} documents")
except Exception:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
    raise
```

Keep this Python session alive for Steps 2 and 3; they use the
`document_store` created above. If you run the blocks separately, recreate a
store with the same `index_name`.

## Step 2: Query Pipeline

Wire together embedding, retrieval, prompt building, and LLM generation:

```python
from haystack import Pipeline
from haystack.utils import Secret
from haystack.dataclasses import ChatMessage
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever

prompt_template = [
    ChatMessage.from_system(
        "Answer the question using only the provided context. "
        "If the context doesn't contain the answer, say 'I don't know'."
    ),
    ChatMessage.from_user(
        "Context:\n{% for doc in documents %}{{ doc.content }}\n{% endfor %}\n"
        "Question: {{query}}"
    ),
]

try:
    query_pipeline = Pipeline()
    text_embedder = SentenceTransformersTextEmbedder(
        model="sentence-transformers/all-mpnet-base-v2"
    )
    text_embedder.warm_up()
    query_pipeline.add_component(
        "text_embedder", text_embedder
    )
    query_pipeline.add_component(
        "retriever",
        ValkeyEmbeddingRetriever(document_store=document_store, top_k=3),
    )
    query_pipeline.add_component(
        "prompt_builder",
        ChatPromptBuilder(
            template=prompt_template,
            required_variables=["query", "documents"],
        ),
    )
    query_pipeline.add_component(
        "generator",
        OpenAIChatGenerator(
            api_key=Secret.from_env_var("OPENAI_API_KEY"),
            model="gpt-4o",
        ),
    )

    query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
    query_pipeline.connect("retriever.documents", "prompt_builder.documents")
    query_pipeline.connect("prompt_builder.prompt", "generator.messages")
except Exception:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
    raise
```

Both embedders use the same model, so their vector dimensions match the
document store's `embedding_dim`.

## Step 3: Ask a Question

```python
query = "How does Valkey integrate with Haystack?"

try:
    result = query_pipeline.run(
        {
            "text_embedder": {"text": query},
            "prompt_builder": {"query": query},
        }
    )

    print(result["generator"]["replies"][0].content)
finally:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
```

Output:

```text
The ValkeyDocumentStore integrates directly with Haystack pipelines,
allowing you to store document embeddings in Valkey and retrieve them
using the ValkeyEmbeddingRetriever component.
```

The output depends on the generator response. Treat the text above as an
illustrative example, not an exact-response assertion.

## Deterministic Local Validation

When model downloads or provider credentials are unavailable, run the
[deterministic sample](sample/README.md). It uses fixed four-dimensional
embeddings with the same `ValkeyDocumentStore` and
`ValkeyEmbeddingRetriever` APIs, then formats retrieved documents locally
instead of calling an LLM.

## Pipeline Architecture

The indexing and query pipelines are intentionally separate. You index once
(or on a schedule), then query many times. Valkey's in-memory KNN handles the
retrieval step before the LLM call.

| Stage | Component | What it does |
| --- | --- | --- |
| Index | `SentenceTransformersDocumentEmbedder` | Generates 768-dim embeddings for each doc |
| Index | `DocumentWriter` | Writes docs + embeddings to Valkey |
| Query | `SentenceTransformersTextEmbedder` | Embeds the user's question |
| Query | `ValkeyEmbeddingRetriever` | KNN search - returns top-k similar docs |
| Query | `ChatPromptBuilder` | Injects retrieved docs into the prompt |
| Query | `OpenAIChatGenerator` | Generates the final grounded answer |

## Swap the Embedding Model

Any Haystack-compatible embedder works. Keep `embedding_dim` consistent
between the document store and both embedders:

```python
# OpenAI embeddings (1536-dim)
from haystack.components.embedders import (
    OpenAIDocumentEmbedder,
    OpenAITextEmbedder,
)
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs_openai",
    embedding_dim=1536,  # text-embedding-3-small
    distance_metric="cosine",
    request_timeout=5000,
)
```

This optional example requires the provider's credentials and embedding
dependencies. Configure the corresponding text embedder with the same model
and dimension before querying.

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `nodes_list` | Yes | - | Host and port tuples for Valkey nodes. |
| `index_name` | Yes | - | Search index used for document storage and retrieval. |
| `embedding_dim` | Yes | - | Must match both document and query embedding dimensions. |
| `distance_metric` | Yes | - | Vector distance metric, such as `cosine`. |
| `metadata_fields` | No | None | Metadata fields indexed for filtering. |
| `request_timeout` | No | `5000 ms` in the examples | Maximum time allowed for a Valkey request. |
| `top_k` | No | `3` in the example | Number of nearest documents returned by the retriever. |
| `VALKEY_HOST` | No | `localhost` | Host override used by the runnable sample. |
| `VALKEY_PORT` | No | `6379` | Port override used by the runnable sample. |
| `VALKEY_REQUEST_TIMEOUT_MS` | No | `5000` | Request timeout override used by the runnable sample. |
| `OPENAI_API_KEY` | Only for generator path | - | Credential read by `Secret.from_env_var`. |
| `sentence-transformers/all-mpnet-base-v2` | Optional | - | Model used by the archived embedder path; produces 768-dimensional vectors. |

## Teardown

The question block removes the documents and closes the client in a
failure-safe `finally` block. Remove the local container after the examples
finish:

```bash
docker rm -f haystack-valkey
```

Valkey Search documents do not expire automatically through this integration.
Production applications should define a retention policy and schedule cleanup
for indexes that can grow without bound.

---

[<- 01 - Getting Started](01-getting-started.md)
