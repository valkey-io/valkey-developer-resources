"""Fixtures for Kong AI Gateway Valkey pattern integration tests."""

import json
import os
import struct
import time

import numpy as np
import pytest
import valkey

DIMENSION = 128  # Reduced for tests (real: 768 for nomic-embed-text, 3072 for text-embedding-3-large)
INDEX_PREFIX = "kong:test:"


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32."""
    return struct.pack(f"<{len(vector)}f", *vector)


def create_hnsw_index(
    client: valkey.Valkey,
    index_name: str,
    prefix: str,
    *,
    extra_schema: tuple[str, ...] = (),
) -> None:
    """Create an HNSW COSINE vector index on JSON documents.

    This is the pattern Kong uses for all its semantic plugins. Each plugin
    creates a separate index with its own prefix.

    Args:
        client: Valkey client connection.
        index_name: The FT index name.
        prefix: Key prefix for documents in this index.
        extra_schema: Additional SCHEMA arguments (e.g., TEXT fields) appended
            after the vector field definition.
    """
    schema_args = [
        "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
        "TYPE", "FLOAT32",
        "DIM", str(DIMENSION),
        "DISTANCE_METRIC", "COSINE",
        *extra_schema,
    ]
    client.execute_command(
        "FT.CREATE", index_name,
        "ON", "JSON",
        "PREFIX", "1", prefix,
        "SCHEMA",
        *schema_args,
    )


def wait_for_indexed(client: valkey.Valkey, index_name: str, *, timeout: float = 2.0) -> None:
    """Wait until the index has finished background indexing.

    Polls FT.INFO for indexing == 0 (complete) rather than using a fixed sleep.
    Falls back to a brief sleep if FT.INFO is unavailable.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            info = client.execute_command("FT.INFO", index_name)
            # info is a flat list of key-value pairs
            info_dict = dict(zip(info[::2], info[1::2]))
            indexing = info_dict.get(b"indexing", info_dict.get("indexing", b"0"))
            if indexing in (b"0", "0", 0):
                return
        except (valkey.ResponseError, IndexError):
            pass
        time.sleep(0.05)
    # Final fallback
    time.sleep(0.1)


@pytest.fixture
def valkey_client():
    """Provide a valkey client connection."""
    host = os.environ.get("VALKEY_HOST", "localhost")
    port = int(os.environ.get("VALKEY_PORT", "6379"))
    client = valkey.Valkey(host=host, port=port)
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
    except valkey.ResponseError:
        indices = []

    for idx in indices:
        idx_name = idx.decode() if isinstance(idx, bytes) else idx
        if idx_name.startswith(INDEX_PREFIX):
            try:
                client.execute_command("FT.DROPINDEX", idx_name)
            except valkey.ResponseError:
                pass

    # Delete test keys
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=f"{INDEX_PREFIX}*", count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
