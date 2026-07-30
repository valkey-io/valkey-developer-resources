# Vector Knowledge Retrieval

> Build a semantic knowledge base with PraisonAI and Valkey: embed documents as float32 vectors, index them with HNSW, and retrieve the most relevant chunks at query time.

**Intermediate** · Python · ~25 min

**Who is this for:** Python developers who want their PraisonAI agents to answer questions grounded in a local knowledge base without a hosted vector database.

## What We're Building

A PraisonAI agent backed by a Valkey knowledge base. Documents are embedded as float32 vectors and indexed with HNSW.
At query time, the agent retrieves the most semantically relevant documents from Valkey using `FT.SEARCH`,
then uses them as grounding context for its answer.

## Prerequisites

- Valkey running on `localhost:6379` with the ValkeySearch module — the `valkey-bundle` image includes it (see [01 Getting Started](01-getting-started.md))
- `praisonai[valkey]` and `sentence-transformers` installed:

```bash
pip install "praisonai[valkey]==4.6.157" "sentence-transformers==3.3.1"
```

- `OPENAI_API_KEY` set, or Ollama running locally

## How ValkeySearch Stores Vectors

Each document is a Valkey Hash at key `praisonai:kb:<collection>:<doc_id>`:

```text
HSET praisonai:kb:agent_kb:doc1
  content      "Valkey is an open-source key-value store..."
  content_hash "a3f2..."
  created_at   "1715000000.0"
  embedding    <1536 bytes of float32>
```

An HNSW index over the `embedding` field enables approximate nearest-neighbour search:

```text
FT.CREATE praisonai:kb:agent_kb:idx ON HASH
  PREFIX 1 praisonai:kb:agent_kb:
  SCHEMA
    content TEXT
    embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE
```

## Configuration Reference

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | No | `localhost` | Valkey server hostname. Override with `VALKEY_HOST` env var. |
| `port` | No | `6379` | Valkey server port. Override with `VALKEY_PORT` env var. |
| `password` | No | `None` | Valkey password for authenticated instances. Override with `VALKEY_PASSWORD` env var. |
| `prefix` | No | `"praison:vec:"` | Key namespace prefix. Isolate collections per agent or topic. |
| `dimension` | Yes (per collection) | — | Embedding vector dimension. Must match the model output (e.g. 384 for `all-MiniLM-L6-v2`). |
| `distance` | No | `"cosine"` | Distance metric: `"cosine"` or `"l2"`. Must match the model's normalization. |

## Step 1: Set Up Embedding Model and Vector Store

```python
import os
from sentence_transformers import SentenceTransformer
from praisonai.persistence.knowledge.valkey_vector import ValkeyVectorKnowledgeStore
from praisonai.persistence.knowledge.base import KnowledgeDocument

COLLECTION = "agent_kb"  # alphanumerics and underscores only
DIM = 384               # all-MiniLM-L6-v2 output dimension

model = SentenceTransformer("all-MiniLM-L6-v2")

store = ValkeyVectorKnowledgeStore(
    host=os.environ.get("VALKEY_HOST", "localhost"),
    port=int(os.environ.get("VALKEY_PORT", "6379")),
    password=os.environ.get("VALKEY_PASSWORD") or None,
    prefix="praisonai:kb:",
)


def embed(text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()
```

## Step 2: Ingest Documents

```python
def ingest(docs: list[dict]) -> None:
    """Create the HNSW index (no-op if already exists) and insert documents."""
    store.create_collection(COLLECTION, dimension=DIM, distance="cosine")
    documents = [
        KnowledgeDocument(
            id=d["id"],
            content=d["content"],
            embedding=embed(d["content"]),
        )
        for d in docs
    ]
    ids = store.insert(COLLECTION, documents)
    assert len(ids) == len(documents), f"Expected {len(documents)} inserts, got {len(ids)}"
    print(f"Indexed {len(ids)} documents.")
```

## Step 3: Query with Context-Grounded Agent

**Option A — Ollama (free, local, no API key):**

```python
from praisonaiagents import Agent

agent = Agent(
    instructions="You are a helpful assistant. Answer using only the provided context. Be concise.",
    llm="ollama/llama3.2",  # free, local — run: ollama pull llama3.2
)
```

**Option B — OpenAI (requires `OPENAI_API_KEY`):**

```python
from praisonaiagents import Agent

agent = Agent(
    instructions="You are a helpful assistant. Answer using only the provided context. Be concise.",
)
```

For either option, the `ask()` function is the same:

```python
def ask(question: str, top_k: int = 3) -> str:
    """Retrieve relevant documents from Valkey and pass them to the agent."""
    results = store.search(COLLECTION, query_embedding=embed(question), limit=top_k)
    context = "\n".join(f"- {doc.content}" for doc in results)
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    return str(agent.start(prompt))
```

## Step 4: Run It

```python
KNOWLEDGE = [
    {"id": "doc1", "content": "Valkey is an open-source, high-performance in-memory key-value store forked from Redis 7.2."},
    {"id": "doc2", "content": "ValkeySearch adds FT.CREATE and FT.SEARCH commands for full-text and vector similarity search."},
    {"id": "doc3", "content": "HNSW (Hierarchical Navigable Small World) is a graph-based approximate nearest-neighbour index."},
    {"id": "doc4", "content": "Valkey GLIDE is the official client with a Rust core supporting standalone and cluster modes."},
    {"id": "doc5", "content": "PraisonAI is a multi-agent framework supporting OpenAI-compatible LLMs with pluggable memory backends."},
    {"id": "doc6", "content": "ElastiCache for Valkey is a managed Valkey service on AWS with automatic failover and Multi-AZ support."},
]

if __name__ == "__main__":
    try:
        ingest(KNOWLEDGE)

        questions = [
            "What client library should I use for Valkey?",
            "How does vector search work in Valkey?",
            "Tell me about managed Valkey on AWS",
        ]
        for q in questions:
            print(f"\nQ: {q}")
            answer = ask(q)
            print(f"A: {answer}")
    finally:
        store.close()
```

## Key Design Decisions

**Idempotent ingestion** — `create_collection` silently ignores the "already exists" error, so re-running the script overwrites existing documents (HSET is idempotent) and skips index creation.

**Collection names** — must contain only alphanumerics and underscores (e.g. `agent_kb`, not `agent-kb`).

**Prefix isolation** — `prefix="praisonai:kb:"` namespaces all keys for this knowledge store.
Multiple knowledge bases (per-agent, per-topic) can coexist on the same Valkey instance
using different collection names or prefixes.

**Embedding model** — `all-MiniLM-L6-v2` produces 384-dimensional vectors and runs on CPU in ~10 ms per
document. You can swap in any model that outputs fixed-dimension float32 vectors, including OpenAI
`text-embedding-3-small` (1536 dims — update `DIM` accordingly).

## Connection Lifecycle

Always call `store.close()` in a `finally` block. The underlying `valkey-glide-sync`
client holds an open connection pool that prevents the process from exiting cleanly
if not explicitly closed.

```python
store = ValkeyVectorKnowledgeStore(...)
try:
    # ... ingest and query
finally:
    store.close()
```

## Combining State + Knowledge

Use both stores together for a fully stateful, knowledge-augmented agent:

```python
from praisonai.persistence.state.valkey import ValkeyStateStore
from praisonai.persistence.knowledge.valkey_vector import ValkeyVectorKnowledgeStore

state = ValkeyStateStore(host="localhost", prefix="praisonai:agent:")
knowledge = ValkeyVectorKnowledgeStore(host="localhost", prefix="praisonai:kb:")

try:
    # Track run metadata
    state.incr("runs")
    state.hset("meta", "last_query", question)

    # Retrieve relevant context and pass to agent
    context_docs = knowledge.search("agent_kb", query_embedding=embed(question), limit=5)
    context = "\n".join(doc.content for doc in context_docs)
    answer = agent.start(f"Context:\n{context}\n\nQuestion: {question}")
finally:
    state.close()
    knowledge.close()
```

---

[← 02 Agent State Persistence](02-agent-state.md)
