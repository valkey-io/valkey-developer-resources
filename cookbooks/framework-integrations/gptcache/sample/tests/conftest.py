"""Fixtures for GPTCache pattern integration tests."""

import numpy as np
import pytest
import valkey

INDEX_NAME = "test_gptcache_idx"
PREFIX = "test_gptcache:"
DIMENSION = 128


@pytest.fixture
def valkey_client():
    """Provide a valkey client connection."""
    client = valkey.Valkey(host="localhost", port=6379)
    yield client
    client.close()


@pytest.fixture
def clean_index(valkey_client):
    """Drop the test index before and after the test."""
    _drop_index(valkey_client)
    yield INDEX_NAME
    _drop_index(valkey_client)


@pytest.fixture
def test_vectors():
    """Generate reproducible test vectors."""
    rng = np.random.default_rng(seed=42)
    return rng.random((5, DIMENSION), dtype=np.float32)


def _drop_index(client):
    """Drop the test index and clean up keys, ignoring errors."""
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass
    # Clean up any leftover keys with the test prefix
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=f"{PREFIX}*", count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
