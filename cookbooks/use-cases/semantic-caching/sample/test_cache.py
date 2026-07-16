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


def parse_ft_search_fields(fields: list) -> dict:
    """Parse FT.SEARCH result field array into a dict.

    FT.SEARCH returns fields as a flat list: [key, value, key, value, ...].
    Keys and values may be bytes that need decoding.
    """
    field_dict = {}
    for j in range(0, len(fields), 2):
        k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
        v = fields[j + 1]
        if isinstance(v, bytes):
            try:
                v = v.decode()
            except UnicodeDecodeError:
                pass  # binary field (e.g., embedding)
        field_dict[k] = v
    return field_dict


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
    client = valkey.Valkey(host=VALKEY_HOST, port=VALKEY_PORT, socket_timeout=5.0)
    assert client.ping(), "Valkey is not reachable"
    yield client
    # Cleanup: drop test index and delete test keys
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass
    for key in client.scan_iter(match="test_cache:*"):
        client.delete(key)


def wait_for_indexing(client, index_name: str, expected_docs: int, timeout: float = 5.0):
    """Poll FT.INFO until num_docs reaches expected count or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = client.execute_command("FT.INFO", index_name)
        # FT.INFO returns flat list; find num_docs value
        for i, item in enumerate(info):
            if isinstance(item, bytes):
                item = item.decode()
            if item == "num_docs" and i + 1 < len(info):
                num = int(info[i + 1])
                if num >= expected_docs:
                    return
        time.sleep(0.1)
    raise TimeoutError(f"Index {index_name} did not reach {expected_docs} docs in {timeout}s")


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
        "TEXT",
        "response",
        "TEXT",
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
    # Wait for index to be ready (no documents yet, just verify it exists)
    time.sleep(0.2)
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
        wait_for_indexing(valkey_client, cache_index, expected_docs=1)

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
        field_dict = parse_ft_search_fields(results[2])

        score = float(field_dict.get("score", "999"))
        assert score < SIMILARITY_THRESHOLD, (
            f"Expected score < {SIMILARITY_THRESHOLD} for similar vector, got {score}"
        )
        assert field_dict.get("response") == response_text

    def test_different_vector_exceeds_threshold(self, valkey_client, cache_index):
        """Query with a completely different vector — should exceed threshold."""
        # Insert a known document so the test is self-contained
        known_vec = make_vector(seed=77)
        cache_key = "test_cache:self_contained"
        valkey_client.hset(
            cache_key,
            mapping={
                "prompt": "self-contained test doc",
                "response": "test response",
                "embedding": known_vec.tobytes(),
            },
        )
        wait_for_indexing(valkey_client, cache_index, expected_docs=2)

        # Query with a completely unrelated vector
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

        # Must have at least one document to compare against
        assert results[0] > 0, (
            "Expected at least 1 document in index"
        )

        field_dict = parse_ft_search_fields(results[2])

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


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_knn_on_empty_index(self, valkey_client):
        """KNN search on an empty index should return 0 results gracefully."""
        # Create a fresh empty index
        empty_idx = "test_empty_idx"
        try:
            valkey_client.execute_command("FT.DROPINDEX", empty_idx)
        except valkey.ResponseError:
            pass

        valkey_client.execute_command(
            "FT.CREATE",
            empty_idx,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            "empty_test:",
            "SCHEMA",
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
        time.sleep(0.2)

        # Search with no documents in the index
        query_vec = make_vector(seed=555)
        results = valkey_client.execute_command(
            "FT.SEARCH",
            empty_idx,
            "*=>[KNN 1 @embedding $query_vec AS score]",
            "PARAMS",
            "2",
            "query_vec",
            query_vec.tobytes(),
        )

        # Should return 0 results, not error
        assert results[0] == 0, f"Expected 0 results on empty index, got {results[0]}"

        # Cleanup
        try:
            valkey_client.execute_command("FT.DROPINDEX", empty_idx)
        except valkey.ResponseError:
            pass
