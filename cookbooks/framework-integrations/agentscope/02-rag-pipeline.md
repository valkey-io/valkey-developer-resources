# Building a RAG Pipeline with AgentScope + Valkey

> Chunk documents, generate embeddings, store them in Valkey, and retrieve relevant context for an AgentScope LLM agent using ValkeyStore.

**Intermediate** · Python · ~20 min

This cookbook walks through building a complete Retrieval-Augmented Generation pipeline: splitting source documents into chunks, embedding them, storing vectors in Valkey, and wiring retrieval into an AgentScope agent that answers questions grounded in your data.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Documents  │────▶│  Chunking +  │────▶│   ValkeyStore   │
│  (text/PDF) │     │  Embedding   │     │  (HNSW index)   │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
┌─────────────┐     ┌──────────────┐              │
│   Answer    │◀────│  LLM Agent   │◀─────────────┘
│             │     │  + Context   │       vector search
└─────────────┘     └──────────────┘
```

## Prerequisites

- Valkey running with the Search module (see [Getting Started](01-getting-started.md))
- AWS credentials with access to Amazon Bedrock (Titan Embeddings)

```bash
pip install agentscope[valkey] boto3
```

## Step 1: Prepare Your Documents

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# Example: a simple knowledge base
source_text = """
Valkey is an open-source, high-performance key-value datastore.
It supports strings, hashes, lists, sets, sorted sets, streams, and more.
The Search module adds full-text search and vector similarity search
with HNSW and FLAT indexing algorithms. Vector search enables semantic
queries over embeddings stored directly in Valkey, making it ideal for
RAG pipelines, recommendation systems, and similarity matching.
Valkey is wire-compatible with Redis OSS and can serve as a drop-in replacement.
"""

chunks = chunk_text(source_text.strip(), chunk_size=200, overlap=30)
print(f"Created {len(chunks)} chunks")
```

## Step 2: Generate Embeddings

```python
import json
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Amazon Bedrock Titan."""
    embeddings = []
    for text in texts:
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": text}),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        embeddings.append(result["embedding"])
    return embeddings


embeddings = embed(chunks)
dimensions = len(embeddings[0])  # 1024 for Titan Embed Text v2
print(f"Embedding dimensions: {dimensions}")
```

## Step 3: Store in Valkey

```python
import asyncio
from agentscope.rag import ValkeyStore, Document, DocMetadata
from agentscope.message import TextBlock

store = ValkeyStore(
    host="localhost",
    port=6379,
    index_name="knowledge_base",
    prefix="kb:doc:",
    dimensions=dimensions,
    distance="COSINE",
)

documents = [
    Document(
        embedding=emb,
        metadata=DocMetadata(
            content=TextBlock(type="text", text=chunk),
            doc_id="valkey-overview",
            chunk_id=i,
            total_chunks=len(chunks),
        ),
    )
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
]

asyncio.run(store.add(documents))
print(f"Stored {len(documents)} document chunks in Valkey")
```

## Step 4: Retrieve Relevant Context

```python
async def retrieve(query: str, top_k: int = 3) -> list[str]:
    """Embed a query and retrieve the most relevant chunks."""
    query_embedding = embed([query])[0]
    results = await store.search(
        query_embedding=query_embedding,
        limit=top_k,
        score_threshold=0.7,
    )
    return [doc.metadata.content["text"] for doc in results]


query = "What indexing algorithms does Valkey support?"
context_chunks = asyncio.run(retrieve(query))
for i, chunk in enumerate(context_chunks, 1):
    print(f"[{i}] {chunk[:80]}...")
```

## Step 5: Wire Into an AgentScope Agent

```python
import agentscope

agentscope.init(
    model_configs={
        "config_name": "bedrock_chat",
        "model_type": "litellm_chat",
        "model_name": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    },
)

from agentscope.agents import DialogAgent


async def rag_answer(question: str) -> str:
    """Answer a question using RAG with Valkey retrieval."""
    # Retrieve relevant context
    context_chunks = await retrieve(question)
    context = "\n\n".join(context_chunks)

    # Build the agent with context in the system prompt
    agent = DialogAgent(
        name="assistant",
        model_config_name="bedrock_chat",
        sys_prompt=(
            "Answer the user's question based on the following context. "
            "If the context doesn't contain the answer, say so.\n\n"
            f"Context:\n{context}"
        ),
    )

    response = agent(question)
    return response.content


answer = asyncio.run(rag_answer("What indexing algorithms does Valkey support?"))
print(answer)
```

## Step 6: Filter by Document ID

When your knowledge base contains multiple source documents, use `filter_expression` to scope searches:

```python
async def retrieve_from_doc(query: str, doc_id: str, top_k: int = 3) -> list[str]:
    """Retrieve chunks from a specific document only."""
    query_embedding = embed([query])[0]
    results = await store.search(
        query_embedding=query_embedding,
        limit=top_k,
        filter_expression=f"@doc_id:{{{doc_id}}}",
    )
    return [doc.metadata.content["text"] for doc in results]
```

This uses Valkey's tag-based filtering to restrict the KNN search to chunks belonging to a specific document.

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Configuration →](03-production.md)
