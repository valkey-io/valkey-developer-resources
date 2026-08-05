"""Fixtures for Open WebUI ValkeyClient pattern integration tests."""

import sys
from pathlib import Path

import numpy as np
import pytest
import valkey

# Add sample root to path so helpers is importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import (  # noqa: E402
    DIMENSION,
    TEST_COLLECTION_NAME,
    TEST_COLLECTION_PREFIX,
    TEST_INDEX_NAME,
    TEST_KEY_PREFIX,
    vector_to_bytes,
    wait_for_indexing,
)

# Re-export for tests that import from conftest
COLLECTION_PREFIX = TEST_COLLECTION_PREFIX
COLLECTION_NAME = TEST_COLLECTION_NAME
INDEX_NAME = TEST_INDEX_NAME
KEY_PREFIX = TEST_KEY_PREFIX


@pytest.fixture
def valkey_client():
    """Provide a valkey client connection."""
    client = valkey.Valkey(host="localhost", port=6379)
    yield client
    client.close()


@pytest.fixture
def clean_collection(valkey_client):
    """Drop test index and keys before/after each test."""
    _cleanup(valkey_client)
    yield
    _cleanup(valkey_client)


@pytest.fixture
def test_vectors():
    """Generate reproducible test vectors."""
    rng = np.random.default_rng(seed=42)
    return rng.random((10, DIMENSION), dtype=np.float32)


@pytest.fixture
def indexed_collection(valkey_client, clean_collection, test_vectors):
    """Create index and store 5 test documents."""
    # Create index
    valkey_client.execute_command(
        "FT.CREATE", INDEX_NAME,
        "ON", "HASH",
        "PREFIX", "1", KEY_PREFIX,
        "SCHEMA",
        "vector", "VECTOR", "HNSW", "10",
        "TYPE", "FLOAT32",
        "DIM", str(DIMENSION),
        "DISTANCE_METRIC", "COSINE",
        "M", "16",
        "EF_CONSTRUCTION", "200",
        "text", "TEXT",
        "id", "TAG",
        "metadata_json", "TEXT",
        "hash", "TAG",
        "file_id", "TAG",
        "source", "TAG",
        "knowledge_base_id", "TAG",
    )

    # Store documents
    sources = ["docs.md", "readme.md", "docs.md", "tutorial.md", "docs.md"]
    file_ids = ["file-001", "file-002", "file-001", "file-003", "file-001"]
    for i in range(5):
        key = KEY_PREFIX + f"doc-{i}"
        mapping = {
            "id": f"doc-{i}",
            "vector": vector_to_bytes(test_vectors[i].tolist()),
            "text": f"Test document {i} about topic {i % 3}",
            "metadata_json": f'{{"source": "{sources[i]}", "file_id": "{file_ids[i]}"}}',
            "hash": f"hash-{i}",
            "file_id": file_ids[i],
            "source": sources[i],
            "knowledge_base_id": "kb-test",
        }
        valkey_client.hset(key, mapping=mapping)

    # Wait for indexing
    wait_for_indexing(valkey_client, INDEX_NAME, expected=5)
    return test_vectors


def _cleanup(client: valkey.Valkey) -> None:
    """Drop index and delete keys."""
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=KEY_PREFIX + "*", count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
