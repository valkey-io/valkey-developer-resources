# Vector Memory Search

**Intermediate** · Python · ~20 min

## What You'll Build

A semantic memory retrieval pipeline for ADK agents that stores conversation events as vector embeddings and retrieves them via KNN search with TAG-based pre-filtering. You'll configure distance thresholds, batch ingestion, and multi-user isolation.

## Prerequisites

- Completed [01 — Getting Started](01-getting-started.md)
- Valkey running with Search module (`valkey-bundle`)
- `google-adk-community[valkey]` and `google-genai` installed

## Step 1: Configure the Memory Service

`ValkeyMemoryServiceConfig` controls search behavior, vector dimensions, and storage options:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_search_demo",
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

        # Full configuration with all options
        memory_config = ValkeyMemoryServiceConfig(
            similarity_top_k=10,           # Max KNN results per search
            vector_distance_threshold=0.6, # Filter results above this distance
            embedding_dimensions=768,      # Must match your embedding model
            key_prefix="adk:memory",       # Valkey key prefix for all entries
            index_name="adk_memory_idx",   # Search index name
            distance_metric="COSINE",      # COSINE, L2, or IP
            ttl_seconds=None,              # Optional TTL (None = no expiry)
        )

        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=memory_config,
        )
        await memory_service.create_index()
        print("✅ Memory service configured")

    finally:
        await client.close()

asyncio.run(main())
```

**Configuration options:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `similarity_top_k` | 10 | Maximum number of KNN results returned |
| `vector_distance_threshold` | None | Filter results with distance > threshold |
| `embedding_dimensions` | 768 | Must match your embedding model output |
| `key_prefix` | `adk:memory` | Valkey key prefix for isolation |
| `index_name` | `adk_memory_idx` | Name of the FT.CREATE index |
| `distance_metric` | `COSINE` | One of COSINE, L2, or IP |
| `ttl_seconds` | None | Auto-expire entries after N seconds |

## Step 2: Understand TAG Pre-Filtering

Every memory is tagged with `app_name` and `user_id`. Search queries are scoped by these tags before KNN runs, so users never see each other's memories:

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
        client_name="adk_memory_isolation_demo",
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
            config=ValkeyMemoryServiceConfig(embedding_dimensions=768),
        )

        # User A stores memories
        session_a = Session(
            app_name="support-bot",
            user_id="alice",
            id="session-a",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-a1",
                    invocation_id="inv-a1",
                    author="user",
                    timestamp=1000,
                    content=types.Content(
                        parts=[types.Part(text="My order #12345 hasn't arrived yet")]
                    ),
                ),
            ],
        )
        await memory_service.add_session_to_memory(session_a)

        # User B stores memories
        session_b = Session(
            app_name="support-bot",
            user_id="bob",
            id="session-b",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-b1",
                    invocation_id="inv-b1",
                    author="user",
                    timestamp=1000,
                    content=types.Content(
                        parts=[types.Part(text="How do I reset my password?")]
                    ),
                ),
            ],
        )
        await memory_service.add_session_to_memory(session_b)

        # Alice's search only returns her own memories
        result = await memory_service.search_memory(
            app_name="support-bot",
            user_id="alice",
            query="order status",
        )
        print(f"Alice's memories: {len(result.memories)}")
        for mem in result.memories:
            print(f"  {mem.content.parts[0].text}")
            # Will NOT contain Bob's password reset question

    finally:
        await client.close()

asyncio.run(main())
```

The generated query looks like:

```
(@app_name:{support\-bot} @user_id:{alice})=>[KNN 10 @embedding $query_vec]
```

Special characters in `app_name` and `user_id` are escaped automatically.

## Step 3: Incremental Memory Ingestion

Use `add_events_to_memory` to persist only the latest turn without re-ingesting the full session:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
from google.adk.events.event import Event
from google.genai import types

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_incremental_demo",
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
            config=ValkeyMemoryServiceConfig(embedding_dimensions=768),
        )

        # After each turn, persist only the new events
        new_events = [
            Event(
                id="evt-turn3-user",
                invocation_id="inv-3",
                author="user",
                timestamp=3000,
                content=types.Content(
                    parts=[types.Part(text="Can you recommend a good book on Rust?")]
                ),
            ),
            Event(
                id="evt-turn3-model",
                invocation_id="inv-3",
                author="model",
                timestamp=3001,
                content=types.Content(
                    parts=[types.Part(text="I recommend 'The Rust Programming Language' by Klabnik and Nichols.")]
                ),
            ),
        ]

        await memory_service.add_events_to_memory(
            app_name="book-advisor",
            user_id="user-42",
            events=new_events,
            session_id="session-current",
        )
        print("✅ Stored 2 new events incrementally")

    finally:
        await client.close()

asyncio.run(main())
```

Events without text content (function calls, empty events) are automatically filtered out during ingestion.

## Step 4: Distance Threshold Filtering

Set `vector_distance_threshold` to discard low-quality matches. With COSINE distance, lower values mean higher similarity:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_memory_threshold_demo",
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

        # Strict threshold — only highly relevant results
        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=768,
                vector_distance_threshold=0.4,  # Only very similar results
                similarity_top_k=5,
            ),
        )

        result = await memory_service.search_memory(
            app_name="my-agent",
            user_id="user-123",
            query="Python data science libraries",
        )

        # Only results with cosine distance <= 0.4 are returned
        print(f"High-quality matches: {len(result.memories)}")

    finally:
        await client.close()

asyncio.run(main())
```

**Distance metric guidance:**

| Metric | Range | Lower = | Use case |
|--------|-------|---------|----------|
| COSINE | 0–2 | More similar | General text similarity |
| L2 | 0–∞ | More similar | Normalized embeddings |
| IP | -∞–∞ | Less similar | Already-normalized vectors |

## Step 5: Use with ADK Runner

The primary use case is plugging `ValkeyMemoryService` into ADK's `Runner` for automatic memory persistence:

```python
import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
from google.adk.runners import Runner

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        client_name="adk_runner_demo",
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
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=768,
                similarity_top_k=10,
                vector_distance_threshold=0.6,
            ),
        )

        # Plug into ADK Runner — memories are persisted automatically
        # NOTE: Replace my_agent and my_session_service with your own ADK components.
        # For example:
        #   from google.adk.agents import LlmAgent
        #   my_agent = LlmAgent(model="gemini-2.0-flash", name="demo-agent")
        #   my_session_service = InMemorySessionService()
        runner = Runner(
            agent=my_agent,  # Your LlmAgent instance
            memory_service=memory_service,
            app_name="my-app",
            session_service=my_session_service,  # Your SessionService instance
        )
        # The Runner calls add_session_to_memory after each interaction
        # and search_memory to provide context for future queries

    finally:
        await client.close()

asyncio.run(main())
```

## How It Works Under the Hood

| Operation | Valkey Command | Purpose |
|-----------|---------------|---------|
| Index creation | `FT.CREATE adk_memory_idx ON HASH PREFIX adk:memory: SCHEMA embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE ...` | HNSW index with TAG fields |
| Batch ingestion | `HSET adk:memory:{uuid} content "..." embedding <blob> app_name "..." user_id "..." author "..." timestamp "..."` (via Batch pipeline) | Pipeline multiple HSET+EXPIRE |
| KNN search | `FT.SEARCH adk_memory_idx "(@app_name:{app} @user_id:{user})=>[KNN 10 @embedding $query_vec]" PARAMS 2 query_vec <blob>` | Filtered vector similarity |
| Distance filter | Post-filter on `__embedding_score` | Discard results above threshold |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 0 results returned | Check `app_name` and `user_id` match between ingestion and search |
| All results filtered | Increase `vector_distance_threshold` or set to `None` |
| Embedding dimension mismatch | Ensure `embedding_dimensions` matches your model output (768 for text-embedding-004) |
| Slow batch ingestion | Embeddings are generated in batch — ensure your embedding provider supports batch requests |

[← Previous: 01 — Getting Started](01-getting-started.md) · [Next: 03 — Production Patterns →](03-production.md)
