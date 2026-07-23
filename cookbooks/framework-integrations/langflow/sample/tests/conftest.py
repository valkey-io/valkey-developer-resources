"""Shared test fixtures for Langflow + Valkey integration tests."""

import os

import pytest
import valkey


@pytest.fixture
def valkey_host() -> str:
    return os.environ.get("VALKEY_HOST", "localhost")


@pytest.fixture
def valkey_port() -> int:
    return int(os.environ.get("VALKEY_PORT", "6379"))


@pytest.fixture
def valkey_client(valkey_host: str, valkey_port: int) -> valkey.Valkey:
    """Create a Valkey client connection."""
    client = valkey.Valkey(host=valkey_host, port=valkey_port, decode_responses=True)
    yield client
    client.close()


@pytest.fixture
def clean_prefix(valkey_client: valkey.Valkey) -> str:
    """Provide a unique key prefix and clean up after the test."""
    prefix = "test:langflow:"
    yield prefix
    # Clean up all keys with this prefix
    for key in valkey_client.scan_iter(f"{prefix}*"):
        valkey_client.delete(key)
