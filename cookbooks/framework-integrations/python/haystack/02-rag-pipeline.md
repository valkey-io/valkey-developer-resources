# RAG Pipeline with Haystack + Valkey

> Build a full retrieval-augmented generation pipeline with Valkey as the vector store. Embed your documents once, then answer questions grounded in your data — not the LLM's training set.

**Intermediate** · Python · ~20 min

**Who is this for:** AI application developers building question-answering systems who want sub-millisecond retrieval from Valkey combined with Haystack's composable pipeline architecture.

## How RAG Works

```text
User question
  → embed question (OllamaTextEmbedder)
  → find similar docs in Valkey (KNN via ValkeyEmbeddingRetriever)
  → inject docs into prompt (ChatPromptBuilder)
  → LLM generates grounded answer (OllamaChatGenerator)
```

Valkey handles the retrieval step — sub-millisecond KNN over your document embeddings.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey Bundle running with search module

Start Valkey with the sample's Compose configuration:

```bash
docker compose -f sample/docker-compose.yml up -d --wait
```

- Ollama running with models pulled:

  ```bash
  ollama pull nomic-embed-text
  ollama pull llama3.2:1b
  ```

## Step 1: Indexing Pipeline

Run this once to embed and store your documents:

```python
from haystack import Pipeline, Document
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs",
    embedding_dim=768,
    distance_metric="cosine",
)

indexing_pipeline = Pipeline()
indexing_pipeline.add_component(
    "embedder",
    OllamaDocumentEmbedder(model="nomic-embed-text"),
)
indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store))
indexing_pipeline.connect("embedder.documents", "writer.documents")

# Your documents — swap this for file loaders, web crawlers, etc.
docs = [
    Document(content="Valkey supports vector search natively via its search module."),
    Document(content="The ValkeyDocumentStore integrates directly with Haystack pipelines."),
    Document(content="Cosine similarity measures the angle between two embedding vectors."),
    Document(content="RAG grounds LLM responses in retrieved facts, reducing hallucinations."),
    Document(content="Haystack pipelines are composable — swap any component without rewriting."),
]

indexing_pipeline.run({"embedder": {"documents": docs}})
print(f"Indexed {document_store.count_documents()} documents")
```

## Step 2: Query Pipeline with Local LLM

Wire together embedding, retrieval, prompt building, and LLM generation — all running locally:

```python
from haystack import Pipeline
from haystack.dataclasses import ChatMessage
from haystack.components.builders import ChatPromptBuilder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaChatGenerator
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

query_pipeline = Pipeline()
query_pipeline.add_component(
    "text_embedder",
    OllamaTextEmbedder(model="nomic-embed-text"),
)
query_pipeline.add_component(
    "retriever",
    ValkeyEmbeddingRetriever(document_store=document_store, top_k=3),
)
query_pipeline.add_component(
    "prompt_builder",
    ChatPromptBuilder(template=prompt_template, required_variables=["query", "documents"]),
)
query_pipeline.add_component(
    "generator",
    OllamaChatGenerator(model="llama3.2:1b"),
)

query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
query_pipeline.connect("retriever.documents", "prompt_builder.documents")
query_pipeline.connect("prompt_builder.messages", "generator.messages")
```

## Step 3: Ask a Question

```python
query = "How does Valkey integrate with Haystack?"

result = query_pipeline.run({
    "text_embedder": {"text": query},
    "prompt_builder": {"query": query},
})

print(result["generator"]["replies"][0].text)
```

Expected output:

```text
The ValkeyDocumentStore integrates directly with Haystack pipelines,
allowing you to store document embeddings in Valkey and retrieve them
using vector search.
```

## Pipeline Architecture

The indexing and query pipelines are intentionally separate. You index once (or on a schedule), then query thousands of times.
Valkey's in-memory KNN means retrieval adds ~1ms to your total latency, negligible compared to the LLM call.

| Stage | Component | What it does |
|-------|-----------|-------------|
| Index | `OllamaDocumentEmbedder` | Generates 768-dim embeddings for each document |
| Index | `DocumentWriter` | Writes documents + embeddings to Valkey as JSON |
| Query | `OllamaTextEmbedder` | Embeds the user's question |
| Query | `ValkeyEmbeddingRetriever` | KNN search — returns top-k similar documents |
| Query | `ChatPromptBuilder` | Injects retrieved docs into the prompt template |
| Query | `OllamaChatGenerator` | Generates the final grounded answer locally |

<details>
<summary>Alternative: using a cloud LLM via OpenRouter</summary>

If you prefer a hosted model, swap the generator. `OpenAIChatGenerator` is
OpenAI-compatible, so pointing `api_base_url` at OpenRouter gives you access to
OpenAI, Anthropic, Google, and others through one endpoint — vendor-neutral,
no provider-specific SDK:

```bash
pip install openai
```

```python
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.utils import Secret

# Replace OllamaChatGenerator with:
query_pipeline.add_component(
    "generator",
    OpenAIChatGenerator(
        api_key=Secret.from_env_var("OPENROUTER_API_KEY"),
        api_base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    ),
)
```

Requires the `OPENROUTER_API_KEY` environment variable.

</details>

## Swap the Embedding Model

Any Haystack-compatible embedder works. Keep `embedding_dim` consistent between the document store and both embedders:

```python
# Example: using a different Ollama model with 384 dimensions
document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs_small",
    embedding_dim=384,  # all-minilm = 384
    distance_metric="cosine",
)

embedder = OllamaDocumentEmbedder(model="all-minilm")
```

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `model` (embedder) | ✓ | `"nomic-embed-text"` | Ollama model name for embeddings |
| `model` (generator) | ✓ | `"llama3.2:1b"` | Ollama model name for text generation |
| `top_k` (retriever) | — | `10` | Number of documents to retrieve |
| `url` (Ollama) | — | `"http://localhost:11434"` | Ollama server URL |
| `embedding_dim` | — | `768` | Must match embedding model output |

## Teardown

```bash
docker compose -f sample/docker-compose.yml down
```

---

[← 01 - Getting Started](01-getting-started.md)
