"""Verify Valkey connectivity and search module availability.

This script demonstrates the initial setup check from Cookbook 01 (Getting Started).
It connects to Valkey, verifies the search module is loaded, and confirms
that HASH operations work — the storage pattern DocsGPT uses for vector data.

Usage:
    python scripts/getting_started.py

Requirements:
    - Valkey running on localhost:6379 with valkey-search module
    - pip install valkey-glide-sync
"""
from __future__ import annotations

import os
import struct
import sys

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


def main() -> None:
    """Connect to Valkey and verify the search module is available."""
    print(f"Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")

    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)]
    )
    client = GlideClient.create(config)

    # 1. Basic connectivity
    pong = client.ping()
    print(f"✓ Connected to Valkey: {pong}")

    # 2. Verify search module via FT.CREATE + FT.DROPINDEX
    test_index = "__docsgpt_connectivity_test__"
    try:
        client.custom_command(
            [
                "FT.CREATE", test_index,
                "ON", "HASH",
                "PREFIX", "1", "__test__:",
                "SCHEMA",
                "vec", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32", "DIM", "3", "DISTANCE_METRIC", "COSINE",
            ]
        )
        print("✓ valkey-search module is available (FT.CREATE succeeded)")
    except Exception as e:
        print(f"✗ FT.CREATE failed: {e}")
        print("  Make sure Valkey is running with the search module.")
        print("  Use: docker run -d -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0")
        client.close()
        sys.exit(1)

    # Clean up test index
    client.custom_command(["FT.DROPINDEX", test_index])
    print("✓ Cleanup complete (FT.DROPINDEX succeeded)")

    # 3. Verify HASH operations (the storage pattern DocsGPT uses)
    test_key = "__docsgpt_test_hash__"
    embedding = [0.1, 0.2, 0.3]
    vector_bytes = struct.pack(f"<{len(embedding)}f", *embedding)

    client.hset(test_key, {"vector": vector_bytes, "content": "test"})
    result = client.hget(test_key, "content")
    assert result == b"test", f"Expected b'test', got {result}"
    client.delete([test_key])
    print("✓ HASH operations work (vector store pattern)")

    client.close()
    print("\n✅ All checks passed — Valkey is ready for DocsGPT!")


if __name__ == "__main__":
    main()
