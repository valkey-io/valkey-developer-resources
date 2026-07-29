"""Fixtures for Kong AI Gateway Valkey pattern integration tests."""

import json
import struct
import time

import numpy as np
import pytest
import valkey

DIMENSION = 128  # Reduced for tests (real: 1024 or 3072)
INDEX_PREFIX = "kong:test:"


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32."""
    return struct.pack(f"<{len(vector)}f", *vector)


@pytest.fixture
def valkey_client():
    """Provide a valkey client connection."""
    client = valkey.Valkey(host="localhost", port=6379)
    yield client
    client.close()


@pytest.fixture
def clean_state(valkey_client):
    """Drop test indices and keys before/after each test."""
    _cleanup(valkey_client)
    yield
    _cleanup(valkey_client)


@pytest.fixture
def rng():
    """Reproducible random number generator."""
    return np.random.default_rng(seed=42)


def _cleanup(client: valkey.Valkey) -> None:
    """Remove test indices and keys."""
    # Drop all test indices
    try:
        indices = client.execute_command("FT._LIST")
        for idx in indices:
            idx_name = idx.decode() if isinstance(idx, bytes) else idx
            if idx_name.startswith("kong:test:"):
                client.execute_command("FT.DROPINDEX", idx_name)
    except valkey.ResponseError:
        pass

    # Delete test keys
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match="kong:test:*", count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
