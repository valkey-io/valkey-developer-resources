"""Verify Valkey connectivity for DB-GPT extensions.

Connects to Valkey, verifies the search module is loaded, and confirms
basic HASH operations work (the pattern used by ValkeyStore).
"""
from __future__ import annotations

import asyncio
import struct
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def main() -> int:
    """Connect to Valkey and verify the search module is available."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dbgpt_connectivity_check",
        request_timeout=5000,
    )

    try:
        client = await GlideClient.create(config)
    except Exception as exc:
        print(f"✗ Failed to connect to Valkey: {exc}")
        print("  Make sure Valkey is running: docker compose up -d")
        return 1

    try:
        # Basic connectivity
        pong = await client.ping()
        print(f"✓ Connected to Valkey: {pong}")

        # Verify search module via FT.CREATE + FT.DROP
        test_index = "__dbgpt_connectivity_test__"
        await client.custom_command(
            [
                "FT.CREATE", test_index, "ON", "HASH",
                "PREFIX", "1", "__test__:",
                "SCHEMA", "vec", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32", "DIM", "3", "DISTANCE_METRIC", "COSINE",
            ]
        )
        print("✓ valkey-search module is available (FT.CREATE succeeded)")

        # Clean up test index
        await client.custom_command(["FT.DROPINDEX", test_index])
        print("✓ Cleanup complete (FT.DROPINDEX succeeded)")

        # Verify basic HASH operations (used by both vector store and cache)
        test_key = "__dbgpt_test_hash__"
        embedding = [0.1, 0.2, 0.3]
        vector_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
        await client.hset(test_key, {"vector": vector_bytes, "content": "test"})
        result = await client.hget(test_key, "content")
        assert result == b"test", f"Expected b'test', got {result}"
        await client.delete([test_key])
        print("✓ HASH operations work (vector store pattern)")

        print("\n✅ All checks passed — Valkey is ready for DB-GPT!")
        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
