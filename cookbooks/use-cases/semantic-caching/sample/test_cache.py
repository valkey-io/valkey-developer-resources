"""Tests for semantic caching sample.

Requires:
    - Valkey running on localhost:6379 with search module

Tests use deterministic vectors to verify the Valkey search flow
without requiring Ollama. This allows CI to validate the caching
logic (index creation, storage, KNN retrieval, threshold filtering)
independently of the embedding provider.
"""

import hashlib
import time

import numpy as np
import pytest
import valkey

VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
EMBEDDING_DIM = 768
INDEX_NAME = "test_cache_idx"
SIMILARITY_THRESHOLD = 0.15


def make_vector(seed: int) -> np.ndarray:
    """Create a deterministic unit vector from a seed."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    vec /= np.linalg.norm(vec)  # Normalize for cosine distance
    return vec


def similar_vector(base: np.ndarray, noise_scale: float = 0.01) -> np.ndarray:
    """Create a vector similar to base by adding small noise.

    Noise is deterministic (seed=99) for reproducibility.
    A noise_scale of 0.01 on a 768-dim normalized vector produces
    cosine distance roughly in the 0.01-0.10 range.
    """
    rng = np.random.default_rng(99)
    noise = rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * noise_scale
    vec = base + noise
    vec /= np.linalg.norm(vec)
    return vec


@pytest.fixture(scope="module")
def valkey_client():
    """Create a Valkey client and clean up test keys after tests."""
    client = valkey.Valkey(host=VALKEY_HOST, port=VALKEY_PORT)
    assert client.ping(), "Valkey is not reachable"
    yield client
    # Cleanup: drop test index and delete test keys
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass


@pytest.fixture(scope="module")
def cache_index(valkey_client):
    """Create a test cache index."""
    try:
        valkey_client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass

    valkey_client.execute_command(
        "FT.CREATE",
        INDEX_NAME,
        "ON",
        "HASH",
        "PREFIX",
        "1",
        "test_cache:",
        "SCHEMA",
        "prompt",
        "TAG",
        "response",
        "TAG",
        "embedding",
        "VECTOR",
        "HNSW",
        "6",
        "TYPE",
        "FLOAT32",
        "DIM",
        str(EMBEDDING_DIM),
        "DISTANCE_METRIC",
        "COSINE",
    )
    # Give index time to be ready
    time.sleep(0.5)
    return INDEX_NAME


class TestIndexCreation:
    """Test that FT.CREATE works correctly."""

    def test_index_exists(self, valkey_client, cache_index):
        """Verify the index was created and is queryable."""
        info = valkey_client.execute_command("FT.INFO", cache_index)
        # FT.INFO returns a flat list of key-value pairs
        assert info is not None


class TestCacheHit:
    """Test the cache miss → store → cache hit flow."""

    def test_store_and_retrieve_similar(self, valkey_client, cache_index):
        """Store a vector, then query with a similar vector — should get a hit."""
        base_vec = make_vector(seed=42)
        prompt = "What are the main features of Valkey?"
        response_text = "Valkey supports strings, hashes, lists, sets, and more."

        # Store in cache
        cache_key = f"test_cache:{hashlib.md5(prompt.encode()).hexdigest()}"
        valkey_client.hset(
            cache_key,
            mapping={
                "prompt": prompt,
                "response": response_text,
                "embedding": base_vec.tobytes(),
            },
        )

        # Wait for indexing
        time.sleep(0.5)

        # Query with a similar vector (small noise added)
        query_vec = similar_vector(base_vec)

        results = valkey_client.execute_command(
            "FT.SEARCH",
            cache_index,
            "*=>[KNN 1 @embedding $query_vec AS score]",
            "PARAMS",
            "2",
            "query_vec",
            query_vec.tobytes(),
        )

        # Should find a result
        assert results[0] > 0, "Expected at least 1 KNN result"

        # Parse fields
        fields = results[2]
        field_dict = {}
        for j in range(0, len(fields), 2):
            k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
            v = fields[j + 1]
            if isinstance(v, bytes):
                try:
                    v = v.decode()
                except UnicodeDecodeError:
                    pass
            field_dict[k] = v

        score = float(field_dict.get("score", "999"))
        assert score < SIMILARITY_THRESHOLD, (
            f"Expected score < {SIMILARITY_THRESHOLD} for similar vector, got {score}"
        )
        assert field_dict.get("response") == response_text

    def test_different_vector_exceeds_threshold(self, valkey_client, cache_index):
        """Query with a completely different vector — should exceed threshold."""
        # Use a very different seed to get an unrelated vector
        different_vec = make_vector(seed=9999)

        results = valkey_client.execute_command(
            "FT.SEARCH",
            cache_index,
            "*=>[KNN 1 @embedding $query_vec AS score]",
            "PARAMS",
            "2",
            "query_vec",
            different_vec.tobytes(),
        )

        # Must have at least one document (from test_store_and_retrieve_similar)
        assert results[0] > 0, (
            "Expected at least 1 document in index — "
            "test_store_and_retrieve_similar must run first"
        )

        fields = results[2]
        field_dict = {}
        for j in range(0, len(fields), 2):
            k = (
                fields[j].decode()
                if isinstance(fields[j], bytes)
                else fields[j]
            )
            v = fields[j + 1]
            if isinstance(v, bytes):
                try:
                    v = v.decode()
                except UnicodeDecodeError:
                    pass
            field_dict[k] = v

        score = float(field_dict.get("score", "999"))
        # Random unrelated vector should have high cosine distance
        assert score > SIMILARITY_THRESHOLD, (
            f"Expected score > {SIMILARITY_THRESHOLD} for unrelated vector, got {score}"
        )


class TestTTL:
    """Test cache expiration."""

    def test_expire_sets_ttl(self, valkey_client, cache_index):
        """Verify EXPIRE sets a TTL on the cache key."""
        vec = make_vector(seed=100)
        cache_key = "test_cache:ttl_test"
        valkey_client.hset(
            cache_key,
            mapping={
                "prompt": "ttl test",
                "response": "ttl response",
                "embedding": vec.tobytes(),
            },
        )
        valkey_client.expire(cache_key, 60)

        ttl = valkey_client.ttl(cache_key)
        assert 0 < ttl <= 60
