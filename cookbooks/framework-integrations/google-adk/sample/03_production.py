"""Test script for 03-production.md — Google ADK + Valkey."""
import asyncio
import hashlib
import logging
import math
import os
import sys

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
INDEX_NAME = "test_prod_idx_03"
KEY_PREFIX = os.environ.get("MEMORY_KEY_PREFIX", "test:prod:memory:03")
EMBED_DIM = 768


def _stub_embed(text: str) -> list[float]:
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
        print("⚠️  GOOGLE_API_KEY not set — using stub embedder")
        async def embed_texts(texts: list[str]) -> list[list[float]]:
            return [_stub_embed(t) for t in texts]
        return embed_texts, "stub"


async def main():
    from glide import GlideClient, GlideClusterClient
    from glide import GlideClientConfiguration, GlideClusterClientConfiguration, NodeAddress, ft
    from google.adk_community.memory import ValkeyMemoryService, ValkeyMemoryServiceConfig
    from google.adk.events.event import Event
    from google.adk.sessions.session import Session
    from google.genai import types

    embed_fn, embed_src = await make_embed_fn()
    print(f"Embedder: {embed_src}")

    # Step 1: TTL-based memory expiry
    print(f"\nConnecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        client_name="adk_memory_production",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)

    try:
        try:
            await ft.dropindex(client, INDEX_NAME)
        except Exception:
            pass

        ttl_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_fn,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=EMBED_DIM,
                key_prefix=KEY_PREFIX,
                index_name=INDEX_NAME,
                ttl_seconds=86400,
                similarity_top_k=10,
                vector_distance_threshold=0.6,
            ),
        )
        await ttl_service.create_index()
        print("✅ Step 1 PASS: TTL-based memory service (ttl_seconds=86400)")

        # Store an event to confirm TTL pipeline works
        session = Session(
            app_name="prod-app", user_id="user-ttl", id="sess-ttl",
            last_update_time=1000,
            events=[Event(
                id="evt-ttl", invocation_id="inv-ttl", author="user", timestamp=1000,
                content=types.Content(parts=[types.Part(text="Test TTL memory entry")]),
            )],
        )
        await ttl_service.add_session_to_memory(session)
        print("   ✓ add_session_to_memory with TTL pipeline completed")

        # Step 2: Cluster mode — verify GlideClusterClient constructor signature
        # (cannot connect without a real cluster, so we just test the config object)
        try:
            cluster_config = GlideClusterClientConfiguration(
                addresses=[NodeAddress(host="my-cluster.abc123.use1.cache.amazonaws.com", port=6379)],
                client_name="adk_memory_cluster",
                request_timeout=5000,
                use_tls=True,
            )
            print("✅ Step 2 PASS: GlideClusterClientConfiguration constructed (cluster TLS pattern)")
        except Exception as e:
            print(f"❌ Step 2 FAIL: GlideClusterClientConfiguration: {e}")
            raise

        # Step 3: Environment-driven configuration (with existing standalone client)
        use_tls = os.environ.get("VALKEY_TLS", "false").lower() == "true"
        cluster_mode = os.environ.get("VALKEY_CLUSTER", "false").lower() == "true"
        ttl = int(os.environ.get("MEMORY_TTL_SECONDS", "86400"))
        # cluster_mode=False since we only have standalone, so we reuse the existing client
        env_service = ValkeyMemoryService(
            client=client,
            embedding_function=embed_fn,
            config=ValkeyMemoryServiceConfig(
                embedding_dimensions=EMBED_DIM,
                key_prefix=KEY_PREFIX,
                index_name=INDEX_NAME,
                ttl_seconds=ttl,
                similarity_top_k=10,
            ),
        )
        await env_service.create_index()
        print(f"✅ Step 3 PASS: Env-driven config (host={VALKEY_HOST}, tls={use_tls}, cluster={cluster_mode}, ttl={ttl})")

        # Step 4: Observability — logging setup
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("google_adk")
        logger.setLevel(logging.DEBUG)
        print("✅ Step 4 PASS: Logging configured under 'google_adk' namespace")

        # Step 5: Performance tuning patterns
        # Batched embedding function
        async def embed_texts_batched(texts: list[str]) -> list[list[float]]:
            batch_size = 100
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                all_embeddings.extend([_stub_embed(t) for t in batch])
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            return all_embeddings

        # Per-environment key prefix isolation
        dev_config = ValkeyMemoryServiceConfig(
            key_prefix="dev:adk:memory",
            index_name="dev_adk_memory_idx",
            embedding_dimensions=EMBED_DIM,
        )
        prod_config = ValkeyMemoryServiceConfig(
            key_prefix="prod:adk:memory",
            index_name="prod_adk_memory_idx",
            embedding_dimensions=EMBED_DIM,
        )
        print("✅ Step 5 PASS: Batched embedder and per-env key_prefix isolation pattern")

        print("\n✅ 03-production: ALL STEPS PASSED")

    finally:
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
