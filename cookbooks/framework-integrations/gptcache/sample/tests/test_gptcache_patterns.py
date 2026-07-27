"""Integration tests validating GPTCache's RedisVectorStore patterns against Valkey."""

import numpy as np
import pytest
import valkey

INDEX_NAME = "test_gptcache_idx"
PREFIX = "test_gptcache:"
DIMENSION = 128

pytestmark = pytest.mark.timeout(10)


def _create_vector_index(client, index_name=INDEX_NAME, prefix=PREFIX):
    """Helper to create a FLAT FLOAT32 COSINE vector index."""
    client.execute_command(
        "FT.CREATE",
        index_name,
        "ON",
        "HASH",
        "PREFIX",
        "1",
        prefix,
        "SCHEMA",
        "id",
        "TAG",
        "vector",
        "VECTOR",
        "FLAT",
        "6",
        "TYPE",
        "FLOAT32",
        "DIM",
        str(DIMENSION),
        "DISTANCE_METRIC",
        "COSINE",
    )


class TestConnectivity:
    """Test basic connectivity and backend detection."""

    def test_connectivity(self, valkey_client):
        """PING succeeds and INFO SERVER identifies the backend."""
        assert valkey_client.ping() is True

        info = valkey_client.info("server")
        server_name = info.get("server_name", "")
        assert server_name == "valkey"

    def test_search_module_available(self, valkey_client):
        """FT._LIST confirms the search module is loaded."""
        result = valkey_client.execute_command("FT._LIST")
        # Should return a list (possibly empty) without error
        assert isinstance(result, list)


class TestVectorIndex:
    """Test vector index creation and inspection."""

    def test_create_vector_index(self, valkey_client, clean_index):
        """FT.CREATE with VECTOR FLAT field succeeds and FT.INFO reflects it."""
        _create_vector_index(valkey_client)

        info = valkey_client.execute_command("FT.INFO", INDEX_NAME)
        # FT.INFO returns a flat list of key-value pairs
        # Convert to dict for easier inspection
        info_dict = dict(zip(info[0::2], info[1::2]))
        assert info_dict[b"index_name"] == INDEX_NAME.encode()


class TestDocumentStorage:
    """Test HSET document storage and retrieval."""

    def test_store_and_retrieve_vectors(self, valkey_client, clean_index, test_vectors):
        """HSET stores vector bytes and HGETALL retrieves them intact."""
        _create_vector_index(valkey_client)

        key = f"{PREFIX}0"
        original_vector = test_vectors[0]
        valkey_client.hset(
            key, mapping={"id": "0", "vector": original_vector.tobytes()}
        )

        result = valkey_client.hgetall(key)
        assert result[b"id"] == b"0"

        retrieved_vector = np.frombuffer(result[b"vector"], dtype=np.float32)
        np.testing.assert_array_equal(retrieved_vector, original_vector)


class TestKNNSearch:
    """Test KNN vector search patterns."""

    def test_knn_search(self, valkey_client, clean_index, test_vectors):
        """FT.SEARCH KNN returns nearest vectors ordered by distance."""
        _create_vector_index(valkey_client)

        # Store 5 vectors
        for i, vec in enumerate(test_vectors):
            key = f"{PREFIX}{i}"
            valkey_client.hset(key, mapping={"id": str(i), "vector": vec.tobytes()})

        # Search for nearest 3 to the first vector (should find itself at distance ~0)
        query = "*=>[KNN 3 @vector $vec AS score]"
        result = valkey_client.execute_command(
            "FT.SEARCH",
            INDEX_NAME,
            query,
            "PARAMS",
            "2",
            "vec",
            test_vectors[0].tobytes(),
            "DIALECT",
            "2",
        )

        # Result format: [count, key1, fields1, key2, fields2, ...]
        count = result[0]
        assert count == 3

        # Should have 3 results (6 elements after count: key, fields pairs)
        assert len(result) == 7  # count + 3*(key + fields)

    def test_knn_results_sorted_by_distance(self, valkey_client, clean_index, test_vectors):
        """KNN results come back sorted by distance even without SORTBY."""
        _create_vector_index(valkey_client)

        for i, vec in enumerate(test_vectors):
            key = f"{PREFIX}{i}"
            valkey_client.hset(key, mapping={"id": str(i), "vector": vec.tobytes()})

        query = "*=>[KNN 3 @vector $vec AS score]"
        result = valkey_client.execute_command(
            "FT.SEARCH",
            INDEX_NAME,
            query,
            "PARAMS",
            "2",
            "vec",
            test_vectors[0].tobytes(),
            "DIALECT",
            "2",
        )

        # Extract distances from results
        distances = []
        for i in range(1, len(result), 2):
            fields = result[i + 1]
            field_dict = dict(zip(fields[0::2], fields[1::2]))
            score = float(field_dict[b"score"])
            distances.append(score)

        # Verify results are sorted by ascending distance
        assert distances == sorted(distances)
        # First result should be the query vector itself (distance ≈ 0)
        assert distances[0] < 0.01

    def test_sortby_not_supported(self, valkey_client, clean_index, test_vectors):
        """FT.SEARCH with SORTBY raises ResponseError on Valkey."""
        _create_vector_index(valkey_client)

        # Store at least one vector
        key = f"{PREFIX}0"
        valkey_client.hset(
            key, mapping={"id": "0", "vector": test_vectors[0].tobytes()}
        )

        query = "*=>[KNN 3 @vector $vec AS score]"
        with pytest.raises(valkey.ResponseError):
            valkey_client.execute_command(
                "FT.SEARCH",
                INDEX_NAME,
                query,
                "SORTBY",
                "score",
                "ASC",
                "PARAMS",
                "2",
                "vec",
                test_vectors[0].tobytes(),
                "DIALECT",
                "2",
            )


class TestNamespaceIsolation:
    """Test that different prefixes create isolated namespaces."""

    def test_namespace_isolation(self, valkey_client):
        """Indexes with different prefixes don't see each other's documents."""
        idx_a = "test_ns_a_idx"
        idx_b = "test_ns_b_idx"
        prefix_a = "test_ns_a:"
        prefix_b = "test_ns_b:"

        try:
            # Create two indexes with different prefixes
            _create_vector_index(valkey_client, index_name=idx_a, prefix=prefix_a)
            _create_vector_index(valkey_client, index_name=idx_b, prefix=prefix_b)

            # Store a vector in namespace A only
            vec = np.random.default_rng(99).random(DIMENSION).astype(np.float32)
            valkey_client.hset(
                f"{prefix_a}0", mapping={"id": "0", "vector": vec.tobytes()}
            )

            # Search in namespace B should find nothing
            query = "*=>[KNN 3 @vector $vec AS score]"
            result = valkey_client.execute_command(
                "FT.SEARCH",
                idx_b,
                query,
                "PARAMS",
                "2",
                "vec",
                vec.tobytes(),
                "DIALECT",
                "2",
            )
            assert result[0] == 0

            # Search in namespace A should find the vector
            result = valkey_client.execute_command(
                "FT.SEARCH",
                idx_a,
                query,
                "PARAMS",
                "2",
                "vec",
                vec.tobytes(),
                "DIALECT",
                "2",
            )
            assert result[0] == 1

        finally:
            # Cleanup both indexes and keys
            for idx in (idx_a, idx_b):
                try:
                    valkey_client.execute_command("FT.DROPINDEX", idx)
                except valkey.ResponseError:
                    pass
            for prefix in (prefix_a, prefix_b):
                cursor = 0
                while True:
                    cursor, keys = valkey_client.scan(
                        cursor, match=f"{prefix}*", count=100
                    )
                    if keys:
                        valkey_client.delete(*keys)
                    if cursor == 0:
                        break
