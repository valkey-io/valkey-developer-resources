# Getting Started with Google ADK + Valkey

**Beginner** · Python · ~15 min

## What is Google ADK + Valkey?

Google ADK (Agent Development Kit) is an open-source framework for building AI agents with tool use, multi-turn conversations, and persistent memory. `ValkeyMemoryService` from the `google-adk-community` package provides vector-based semantic memory backed by Valkey, allowing agents to remember and recall relevant past interactions via embedding similarity search.

## Prerequisites

- Python 3.10+
- Docker or Podman
- A Valkey server with the Search module (provided by `valkey-bundle`)
- An embedding model (Google Gemini, OpenAI, or sentence-transformers)

## Step 1: Start Valkey

```bash
# Using Docker
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest

# Using Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes the Search module with HNSW vector indexing. Verify it's running:

```bash
docker exec valkey-search valkey-cli PING
# PONG
```

## Step 2: Install Dependencies

```bash
pip install 'google-adk-community[valkey]' google-genai
```

This installs:
- `valkey-glide` — the official Valkey client library
- `google-adk` — the ADK framework (transitive dependency)
- `google-genai` — for embedding generation (or use your preferred provider)

## Step 3: Connect to Valkey and Create the Memory Service

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    # 1. Create a valkey-glide client
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_demo",
        request_timeout=5000,  # 5s — tune for network latency
    )
    client = await GlideClient.create(config)

    # ⚠️ These examples connect without authentication for local development.
    # Always enable authentication and TLS for production deployments.

    try:
        # 2. Define your embedding function (bring your own model)
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        # 3. Create the memory service with default config
        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
        )

        # 4. The index is created automatically on first use, or explicitly:
        await memory_service.create_index()
        print("✅ Connected to Valkey and created search index")

    finally:
        await client.close()

asyncio.run(main())
```

## Step 4: Store Agent Memories

The memory service integrates with ADK's `Runner` to persist conversation events automatically. Here's how to add a session's events to memory:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
from google.adk.events.event import Event
from google.adk.sessions.session import Session
from google.genai import types

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_demo",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)

    try:
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
        )

        # Create a session with events
        session = Session(
            app_name="my-agent",
            user_id="user-123",
            id="session-001",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-1",
                    invocation_id="inv-1",
                    author="user",
                    timestamp=1000,
                    content=types.Content(
                        parts=[types.Part(text="I prefer Python for data science")]
                    ),
                ),
                Event(
                    id="evt-2",
                    invocation_id="inv-2",
                    author="model",
                    timestamp=1001,
                    content=types.Content(
                        parts=[types.Part(text="Python has excellent libraries like pandas and scikit-learn for data science.")]
                    ),
                ),
            ],
        )

        # Store the session — embeddings are generated in batch
        await memory_service.add_session_to_memory(session)
        print("✅ Stored 2 memories with vector embeddings")

    finally:
        await client.close()

asyncio.run(main())
```

## Step 5: Search Memories

Retrieve relevant memories using semantic similarity:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_demo",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)

    try:
        from google import genai
        genai_client = genai.Client()

        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004",
                contents=texts,
            )
            return [e.values for e in response.embeddings]

        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
        )

        # Search for relevant memories
        result = await memory_service.search_memory(
            app_name="my-agent",
            user_id="user-123",
            query="What programming language does the user like?",
        )

        print(f"Found {len(result.memories)} relevant memories:")
        for mem in result.memories:
            print(f"  [{mem.author}] {mem.content.parts[0].text}")

    finally:
        await client.close()

asyncio.run(main())
```

## How It Works Under the Hood

| Operation | Valkey Command | Purpose |
|-----------|---------------|---------|
| Create index | `FT.CREATE adk_memory_idx ON HASH PREFIX adk:memory: SCHEMA embedding VECTOR HNSW ...` | Build HNSW search index |
| Store memory | `HSET adk:memory:{uuid} content "..." embedding <binary> app_name "..." user_id "..."` | Persist event + embedding |
| Search | `FT.SEARCH adk_memory_idx "(@app_name:{app} @user_id:{user})=>[KNN 10 @embedding $vec]"` | KNN similarity search |
| Set TTL | `EXPIRE adk:memory:{uuid} 3600` | Auto-expire old memories |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'glide'` | Run `pip install 'google-adk-community[valkey]'` |
| `ConnectionError` | Ensure Valkey is running: `docker ps \| grep valkey` |
| `Request timed out` | Increase `request_timeout` in `GlideClientConfiguration` |
| `Index already exists` | Safe to ignore — `create_index()` is idempotent |

[Next: 02 — Vector Memory Search →](02-vector-memory-search.md)
