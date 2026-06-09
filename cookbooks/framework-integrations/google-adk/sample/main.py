"""Google ADK + Valkey Memory Service — Full Lifecycle Demo.

Demonstrates:
1. Connecting to Valkey with valkey-glide
2. Creating a ValkeyMemoryService with vector search
3. Storing agent conversation events as embeddings
4. Searching memories by semantic similarity
5. Incremental event ingestion
6. User isolation via TAG pre-filtering

Requirements:
    pip install 'google-adk-community[valkey]' google-genai

Environment variables:
    VALKEY_HOST       - Valkey server hostname (default: localhost)
    VALKEY_PORT       - Valkey server port (default: 6379)
    GOOGLE_API_KEY    - Google GenAI API key for embeddings
    MEMORY_TTL_SECONDS - TTL for memory entries (default: 3600)
"""

from __future__ import annotations

import asyncio
import os
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress
from google import genai
from google.adk.events.event import Event
from google.adk.sessions.session import Session
from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
from google.genai import types


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
MEMORY_TTL = int(os.environ.get("MEMORY_TTL_SECONDS", "3600"))


_genai_client = None


def _get_genai_client() -> genai.Client:
    """Lazy-init genai client so auth errors surface inside main()'s try/except."""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    return _genai_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Google Gemini text-embedding-004."""
    client = _get_genai_client()
    response = await client.models.embed_content_async(
        model="text-embedding-004",
        contents=texts,
    )
    return [e.values for e in response.embeddings]


async def main() -> None:
    """Run the full memory service lifecycle demo."""
    print("=" * 60)
    print("Google ADK + Valkey Memory Service Demo")
    print("=" * 60)

    # ⚠️ These examples connect without authentication for local development.
    # Always enable authentication and TLS for production deployments.

    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        client_name="adk_memory_cookbook_demo",
        request_timeout=5000,  # 5s — tune for network latency
    )

    print(f"\n→ Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")
    client = await GlideClient.create(config)

    try:
        # --- Step 1: Create memory service ---
        memory_config = ValkeyMemoryServiceConfig(
            similarity_top_k=5,
            vector_distance_threshold=0.8,
            embedding_dimensions=768,  # text-embedding-004 output dim
            key_prefix="adk:cookbook:memory",
            index_name="adk_cookbook_demo_idx",
            distance_metric="COSINE",
            ttl_seconds=MEMORY_TTL,
        )
        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_texts,
            config=memory_config,
        )

        # Defensive cleanup: drop stale index from prior runs
        from glide import ft

        try:
            await ft.dropindex(client, "adk_cookbook_demo_idx")
        except Exception:
            pass  # Index doesn't exist — fine

        await memory_service.create_index()
        print("✅ Memory service created with HNSW vector index")

        # --- Step 2: Store a session ---
        print("\n→ Storing conversation session for user 'alice'...")
        session = Session(
            app_name="cookbook-demo",
            user_id="alice",
            id="session-demo-001",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-1",
                    invocation_id="inv-1",
                    author="user",
                    timestamp=1000,
                    content=types.Content(
                        parts=[types.Part(text="I'm working on a machine learning project with PyTorch")]
                    ),
                ),
                Event(
                    id="evt-2",
                    invocation_id="inv-2",
                    author="model",
                    timestamp=1001,
                    content=types.Content(
                        parts=[types.Part(text="PyTorch is great for research and production ML. Would you like help with training loops or model architecture?")]
                    ),
                ),
                Event(
                    id="evt-3",
                    invocation_id="inv-3",
                    author="user",
                    timestamp=1002,
                    content=types.Content(
                        parts=[types.Part(text="I need help optimizing my transformer model for inference speed")]
                    ),
                ),
            ],
        )
        await memory_service.add_session_to_memory(session)
        print("✅ Stored 3 memories with vector embeddings")

        # --- Step 3: Incremental ingestion ---
        print("\n→ Adding incremental events...")
        new_events = [
            Event(
                id="evt-4",
                invocation_id="inv-4",
                author="user",
                timestamp=2000,
                content=types.Content(
                    parts=[types.Part(text="I deployed the model on AWS SageMaker")]
                ),
            ),
        ]
        await memory_service.add_events_to_memory(
            app_name="cookbook-demo",
            user_id="alice",
            events=new_events,
            session_id="session-demo-001",
        )
        print("✅ Added 1 event incrementally")

        # --- Step 4: Store memories for another user (isolation demo) ---
        print("\n→ Storing session for user 'bob'...")
        bob_session = Session(
            app_name="cookbook-demo",
            user_id="bob",
            id="session-demo-002",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-b1",
                    invocation_id="inv-b1",
                    author="user",
                    timestamp=1000,
                    content=types.Content(
                        parts=[types.Part(text="I'm building a web scraper with Scrapy")]
                    ),
                ),
            ],
        )
        await memory_service.add_session_to_memory(bob_session)
        print("✅ Stored 1 memory for bob")

        # NOTE: Demo simplification. Valkey search indexes are near-real-time
        # but not instant. Production code should use retry logic for
        # immediate-after-write reads.
        await asyncio.sleep(0.5)

        # --- Step 5: Search memories ---
        print("\n→ Searching alice's memories for 'deep learning model'...")
        result = await memory_service.search_memory(
            app_name="cookbook-demo",
            user_id="alice",
            query="deep learning model optimization",
        )
        print(f"✅ Found {len(result.memories)} relevant memories:")
        for i, mem in enumerate(result.memories, 1):
            print(f"   {i}. [{mem.author}] {mem.content.parts[0].text[:80]}...")

        # --- Step 6: Demonstrate user isolation ---
        print("\n→ Searching alice's memories for 'web scraping'...")
        result = await memory_service.search_memory(
            app_name="cookbook-demo",
            user_id="alice",
            query="web scraping",
        )
        print(f"✅ Found {len(result.memories)} results (bob's memories are isolated)")
        # Alice should NOT see Bob's Scrapy memory due to TAG filtering

        # --- Cleanup ---
        print("\n→ Cleaning up demo index...")
        try:
            await ft.dropindex(client, "adk_cookbook_demo_idx")
        except Exception:
            pass
        # Delete demo keys using SCAN (production-safe, non-blocking)
        try:
            cursor = b"0"
            while True:
                result = await client.scan(cursor, match="adk:cookbook:memory:*", count=100)
                cursor = result[0]
                keys = result[1]
                if keys:
                    await client.delete(keys)
                if cursor == b"0":
                    break
        except Exception as e:
            print(f"⚠️ Cleanup incomplete: {e}", file=sys.stderr)

        print("\n" + "=" * 60)
        print("Demo complete!")
        print("=" * 60)

    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print("\nHints:", file=sys.stderr)
        print("  • Ensure Valkey is running: docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest", file=sys.stderr)
        print("  • Ensure GOOGLE_API_KEY is set for embedding generation", file=sys.stderr)
        print("  • Ensure dependencies are installed: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
