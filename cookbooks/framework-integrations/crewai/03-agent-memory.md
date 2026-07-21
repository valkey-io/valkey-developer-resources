# Agent Memory in Action

> Wire `ValkeyStorageBackend` into CrewAI's unified `Memory` system — agents remember facts across executions and recall them by semantic similarity.

**Intermediate** · Python · ~15 min

**Who is this for:** Python developers who built the storage backend in cookbook 02 and want to see it work with CrewAI's Memory system and real agents.

## Prerequisites

- Completed [02 - Memory Storage Backend](02-memory-storage.md)
- Valkey running with the search module
- [Ollama](https://ollama.com/) installed with `nomic-embed-text` and `llama3.2:1b` models pulled
- `pip install crewai==1.15.5 ollama==0.6.2`

```bash
ollama pull nomic-embed-text
ollama pull llama3.2:1b
```

## Step 1: Configure Memory with Valkey Backend

```python
from crewai import Memory
from valkey_storage import ValkeyStorageBackend

backend = ValkeyStorageBackend(
    host="localhost",
    port=6379,
    embedding_dim=768,  # nomic-embed-text output dimension
)

memory = Memory(
    storage=backend,
    llm="ollama/llama3.2:1b",
    embedder={
        "provider": "ollama",
        "config": {"model_name": "nomic-embed-text"},
    },
)
```

That's it. CrewAI's `Memory` now stores all records in Valkey via your backend.
The LLM handles scope inference and fact extraction; the embedder converts text to vectors;
your backend stores and searches them.

## Step 2: Store Memories

```python
memory.remember("Valkey uses HNSW algorithm for fast vector similarity search.")
memory.remember("Always close GLIDE clients explicitly to prevent connection leaks.")
memory.remember("Use TAG fields for exact-match filtering in FT.SEARCH queries.")

print(f"Stored {backend.count()} memories in Valkey")
```

When you call `remember()`, CrewAI:

1. Sends the content to the LLM to infer scope, categories, and importance
2. Embeds the content using your configured embedder
3. Calls `backend.save([record])` with the fully-populated `MemoryRecord`

## Step 3: Recall by Semantic Similarity

```python
matches = memory.recall("How does vector search work?")
for m in matches:
    print(f"[{m.score:.2f}] {m.record.content}")
```

Recall embeds your query, then calls `backend.search(query_embedding)` which runs `FT.SEARCH` with KNN against Valkey. Results are ranked by CrewAI's composite score (semantic similarity + recency + importance).

## Step 4: Persistent Across Executions

Because memories live in Valkey (not in-process LanceDB), they persist across script runs:

```python
# script_a.py
memory.remember("The API rate limit is 1000 requests per minute.")
backend.close()

# script_b.py (hours later, different process)
matches = memory.recall("What are the API limits?")
# Returns the rate limit fact stored in script_a.py
```

This is the key advantage over CrewAI's default LanceDB backend — memories are shared, persistent, and searchable from any process connected to the same Valkey instance.

## Step 5: Use with Crews

```python
from crewai import Agent, Crew, Task, Process

researcher = Agent(
    role="Senior Researcher",
    goal="Research and remember key findings",
    backstory="Expert researcher with excellent memory.",
    memory=True,
    verbose=True,
)

task = Task(
    description="What do you know about vector search algorithms?",
    expected_output="Summary of knowledge about vector search",
    agent=researcher,
)

crew = Crew(
    agents=[researcher],
    tasks=[task],
    memory=memory,  # Your Valkey-backed Memory
    process=Process.sequential,
    verbose=True,
)

result = crew.kickoff()
# Agent recalls your stored memories about HNSW and TAG fields!
```

<details>
<summary>Alternative: Using OpenAI instead of Ollama</summary>

```python
import os

memory = Memory(
    storage=backend,
    llm="gpt-4o-mini",  # or any OpenAI model
    embedder={
        "provider": "openai",
        "config": {"model_name": "text-embedding-3-small"},
    },
)
# Requires OPENAI_API_KEY environment variable
```

When using OpenAI embeddings (1536 dimensions), set `embedding_dim=1536` in `ValkeyStorageBackend`.

</details>

## How It Works

| Component | Role |
|-----------|------|
| `Memory(storage=backend)` | CrewAI's unified memory — handles LLM analysis and embedding |
| `ValkeyStorageBackend` | Your implementation — stores/searches records in Valkey |
| Ollama `nomic-embed-text` | Converts text → 768-dim vectors (configured via `embedder`) |
| Ollama `llama3.2` | Infers scope, categories, importance on `remember()` |
| Valkey `FT.SEARCH` | KNN similarity search over stored embeddings |

## What's Next

An official Valkey storage backend for CrewAI is [in development](https://github.com/crewAIInc/crewAI/pull/5700).
Once merged and released, `pip install crewai[valkey]` will provide a built-in backend.
Until then, `ValkeyStorageBackend` gives you Valkey-backed memory today.

For production deployments, set `VALKEY_HOST` and `VALKEY_PORT` environment variables to point at your Valkey cluster (e.g., ElastiCache for Valkey) and add TLS/auth as needed.

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `storage` | ✓ | — | Your `ValkeyStorageBackend` instance |
| `llm` | No | `gpt-5.4-mini` | Model for scope/category inference (override to `ollama/llama3.2:1b` for local) |
| `embedder` | No | OpenAI `text-embedding-3-large` | Embedding config (override for vendor neutrality) |
| `embedding_dim` | ✓ | `384` | Must match the embedder's output dimension |

## Teardown

```bash
docker rm -f valkey
```

---

[← 02 - Memory Storage Backend](02-memory-storage.md)
