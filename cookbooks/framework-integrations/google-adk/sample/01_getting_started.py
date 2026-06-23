"""Test script for 01-getting-started.md — Google ADK + Valkey."""
import asyncio
import hashlib
import math
import os
import struct
import sys

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
INDEX_NAME = "test_gs_idx_01"
KEY_PREFIX = "test:gs:memory:01"
EMBED_DIM = 768


def _stub_embed(text: str) -> list[float]:
    """Deterministic unit-norm stub embedding (no API call)."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    vec = []
    for i in range(EMBED_DIM):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        vec.append(float((seed >> 33) & 0xFFF) / 0xFFF)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def make_embed_fn():
    if GOOGLE_API_KEY:
        from google import genai
        genai_client = genai.Client()
        async def embed_texts(texts: list[str]) -> list[list[float]]:
            response = await genai_client.models.embed_content_async(
                model="text-embedding-004", contents=texts)
            return [e.values for e in response.embeddings]
        return embed_texts, "google-genai"
    else:
        print("⚠️  GOOGLE_API_KEY not set — using stub embedder (no real embeddings)")
        async def embed_texts(texts: list[str]) -> list[list[float]]:
            return [_stub_embed(t) for t in texts]
        return embed_texts, "stub"


async def main():
    from glide import GlideClient, GlideClientConfiguration, NodeAddress, ft
    from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
    from google.adk.events.event import Event
    from google.adk.sessions.session import Session
    from google.genai import types

    print(f"Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        client_name="adk_memory_demo",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)

    embed_fn, embed_src = await make_embed_fn()
    print(f"Embedder: {embed_src}")

    try:
        # Step 3: Create memory service
        memory_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_fn,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=EMBED_DIM,
                key_prefix=KEY_PREFIX,
                index_name=INDEX_NAME,
            ),
        )
        # Drop stale index from prior runs
        try:
            await ft.dropindex(client, INDEX_NAME)
        except Exception:
            pass

        await memory_service.create_index()
        print("✅ Step 3 PASS: create_index()")

        # Step 4: Store memories via add_session_to_memory
        session = Session(
            app_name="my-agent",
            user_id="user-123",
            id="session-001",
            last_update_time=1000,
            events=[
                Event(
                    id="evt-1", invocation_id="inv-1", author="user", timestamp=1000,
                    content=types.Content(parts=[types.Part(text="I prefer Python for data science")]),
                ),
                Event(
                    id="evt-2", invocation_id="inv-2", author="model", timestamp=1001,
                    content=types.Content(parts=[types.Part(text="Python has excellent libraries like pandas and scikit-learn for data science.")]),
                ),
            ],
        )
        await memory_service.add_session_to_memory(session)
        print("✅ Step 4 PASS: add_session_to_memory() stored 2 events")

        # Step 5: Search memories
        await asyncio.sleep(0.3)  # brief wait for index propagation
        result = await memory_service.search_memory(
            app_name="my-agent",
            user_id="user-123",
            query="What programming language does the user like?",
        )
        print(f"✅ Step 5 PASS: search_memory() returned {len(result.memories)} result(s)")
        for mem in result.memories:
            print(f"   [{mem.author}] {mem.content.parts[0].text[:60]}")

        print("\n✅ 01-getting-started: ALL STEPS PASSED")

    finally:
        # Cleanup
        try:
            await ft.dropindex(client, INDEX_NAME)
        except Exception:
            pass
        try:
            cursor = b"0"
            while True:
                scan_result = await client.scan(cursor, match=f"{KEY_PREFIX}:*", count=100)
                cursor, keys = scan_result[0], scan_result[1]
                if keys:
                    await client.delete(keys)
                if cursor == b"0":
                    break
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}", file=sys.stderr)
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
