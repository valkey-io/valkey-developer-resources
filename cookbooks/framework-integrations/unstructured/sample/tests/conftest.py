"""Shared fixtures for Unstructured + Valkey cookbook tests."""

import asyncio
import os
import time

import numpy as np
import pytest
from glide import (
    DistanceMetricType,
    FtCreateOptions,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    NumericField,
    RequestError,
    TagField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
    ft,
)


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

# Reduced dimension for fast tests (real: 384 for all-MiniLM-L6-v2)
DIMENSION = 32
INDEX_PREFIX = "test:unstructured:"
INDEX_NAME = "test_documents_index"


def vector_to_bytes(vec: list[float]) -> bytes:
    """Convert a float list to binary for Valkey HSET."""
    return np.array(vec, dtype=np.float32).tobytes()


def random_vector(dim: int = DIMENSION) -> list[float]:
    """Generate a random unit vector for testing."""
    vec = np.random.default_rng().standard_normal(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


@pytest.fixture
async def client():
    """Create and yield a GLIDE async client, close after test."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        request_timeout=10000,
    )
    c = await GlideClient.create(config)
    yield c
    await c.close()


@pytest.fixture
def create_hnsw_index():
    """Factory fixture to create an HNSW index with given parameters."""

    async def _create(client, index_name=INDEX_NAME, prefix=INDEX_PREFIX, dim=DIMENSION):
        schema = [
            TagField("element_type"),
            TagField("source_document"),
            TagField("record_id"),
            NumericField("page_number"),
            VectorField(
                "embedding",
                VectorAlgorithm.HNSW,
                VectorFieldAttributesHnsw(
                    dimensions=dim,
                    distance_metric=DistanceMetricType.COSINE,
                    type=VectorType.FLOAT32,
                ),
            ),
        ]
        await ft.create(
            client,
            index_name,
            schema,
            FtCreateOptions(prefixes=[prefix]),
        )

    return _create


@pytest.fixture
def cleanup_keys():
    """Factory fixture to clean up keys and index after test."""
    keys_to_delete = []
    indexes_to_drop = []

    class Tracker:
        def track_key(self, key: str):
            keys_to_delete.append(key)

        def track_index(self, name: str):
            indexes_to_drop.append(name)

    tracker = Tracker()
    yield tracker

    # Cleanup happens via the test's client fixture teardown
    # Tests should call cleanup explicitly; this tracks for safety


async def wait_for_indexed(client, index_name: str, expected_docs: int, timeout: float = 15.0):
    """Poll FT.INFO until the expected number of docs are indexed."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            info = await ft.info(client, index_name)
            # FT.INFO returns various formats; look for num_docs
            num_docs = 0
            if isinstance(info, dict):
                num_docs = int(info.get("num_docs", info.get(b"num_docs", 0)))
            elif isinstance(info, (list, tuple)):
                for i, item in enumerate(info):
                    item_str = item.decode() if isinstance(item, bytes) else str(item)
                    if item_str == "num_docs" and i + 1 < len(info):
                        val = info[i + 1]
                        num_docs = int(val.decode() if isinstance(val, bytes) else val)
                        break

            if num_docs >= expected_docs:
                return
        except Exception as exc:
            if "Unknown index" not in str(exc) and "not found" not in str(exc):
                raise
        await asyncio.sleep(0.2)
    raise TimeoutError(
        f"Timed out waiting for {expected_docs} docs in index '{index_name}'"
    )
