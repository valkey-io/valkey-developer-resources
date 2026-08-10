"""Shared fixtures for DocsGPT + Valkey integration tests.

These fixtures provide a connected GLIDE client, automatic cleanup of test
keys/indexes between tests, and helper constants matching the patterns
used by DocsGPT's ValkeyStore implementation.
"""
from __future__ import annotations

import os
import struct
from typing import Generator

import pytest

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

# Connection settings (overridable via environment variables)
VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

# Test namespace to avoid colliding with real data
TEST_INDEX_NAME = "__docsgpt_test_index__"
TEST_PREFIX = "__docsgpt_test__:"

# Embedding dimensions matching DocsGPT defaults (768 for MiniLM-style models)
EMBEDDING_DIM = 768


@pytest.fixture(scope="session")
def valkey_client() -> Generator[GlideClient, None, None]:
    """Create a GLIDE client connected to the local Valkey instance.

    Scope: session — one connection reused across all tests.
    """
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)]
    )
    client = GlideClient.create(config)

    # Verify connectivity
    assert client.ping() == b"PONG", (
        f"Cannot connect to Valkey at {VALKEY_HOST}:{VALKEY_PORT}. "
        "Start Valkey with: docker compose up -d"
    )

    yield client

    client.close()


@pytest.fixture(autouse=True)
def cleanup_test_data(valkey_client: GlideClient) -> Generator[None, None, None]:
    """Clean up test keys and indexes before and after each test.

    Drops the test index (if exists) and deletes all keys with the test prefix.
    """
    _cleanup(valkey_client)
    yield
    _cleanup(valkey_client)


def _cleanup(client: GlideClient) -> None:
    """Remove test index and all test-prefixed keys."""
    # Drop the test index (ignore error if it doesn't exist)
    try:
        client.custom_command(["FT.DROPINDEX", TEST_INDEX_NAME])
    except Exception:
        pass

    # Delete all keys with test prefix using SCAN
    cursor = "0"
    while True:
        result = client.custom_command(
            ["SCAN", cursor, "MATCH", f"{TEST_PREFIX}*", "COUNT", "100"]
        )
        # SCAN returns [cursor, [keys...]]
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys = result[1] if isinstance(result[1], list) else []
        if keys:
            # Convert bytes keys to strings for DELETE
            key_list = [k if isinstance(k, str) else k.decode() for k in keys]
            client.delete(key_list)
        if cursor == "0":
            break


def make_embedding(seed: float = 0.1) -> bytes:
    """Create a deterministic test embedding as packed float32 bytes.

    Args:
        seed: Base value for the embedding vector. Each dimension gets
              seed + (i * 0.001) to create a unique but reproducible vector.

    Returns:
        Packed little-endian float32 bytes (768 * 4 = 3072 bytes).
    """
    floats = [seed + (i * 0.001) for i in range(EMBEDDING_DIM)]
    return struct.pack(f"<{EMBEDDING_DIM}f", *floats)
