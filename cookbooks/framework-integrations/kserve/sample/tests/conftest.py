"""Fixtures for KServe Valkey pattern integration tests."""

import numpy as np
import pytest
import valkey


@pytest.fixture
def valkey_client():
    """Provide a valkey client connection."""
    client = valkey.Valkey(host="localhost", port=6379)
    yield client
    client.close()


@pytest.fixture
def clean_keys(valkey_client):
    """Clean up test keys before and after each test."""
    _cleanup(valkey_client)
    yield
    _cleanup(valkey_client)


@pytest.fixture
def rng():
    """Reproducible random number generator."""
    return np.random.default_rng(seed=42)


def _cleanup(client: valkey.Valkey) -> None:
    """Remove all test-specific keys."""
    patterns = ["test:*", "lmcache:*", "idx:*", "feast:*", "model@*"]
    for pattern in patterns:
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=pattern, count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
