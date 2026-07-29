"""Integration tests validating Kong AI Gateway's Valkey usage patterns.

Kong's AI plugins use vectordb.strategy=redis with auto-detection of Valkey via
the server_name field in INFO. They use JSON document storage with FT.CREATE on
JSON paths and FT.SEARCH for KNN similarity queries.
"""

import json
import struct
import time

import numpy as np
import pytest
import valkey

DIMENSION = 128
INDEX_PREFIX = "kong:test:"


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32."""
    return struct.pack(f"<{len(vector)}f", *vector)


class TestConnectivity:
    """Validate connectivity and auto-detection prerequisites."""

    def test_ping(self, valkey_client):
        assert valkey_client.ping() is True

    def test_server_name_detection(self, valkey_client):
        """Kong checks INFO server for server_name to auto-detect Valkey."""
        info = valkey_client.info("server")
        server_name = info.get("server_name", "")
        # Should be 'valkey' for a Valkey server
        assert server_name == "valkey", f"Expected 'valkey', got '{server_name}'"

    def test_search_module_loaded(self, valkey_client):
        """FT commands require the search module."""
        modules = valkey_client.module_list()
        search_found = any(
            (mod.get(b"name") or mod.get("name", b"")).decode().lower() == "search"
            if isinstance(mod.get(b"name") or mod.get("name", b""), bytes)
            else (mod.get(b"name") or mod.get("name", "")).lower() == "search"
            for mod in modules
        )
        assert search_found, "valkey-search module not loaded"

    def test_json_module_loaded(self, valkey_client):
        """JSON.SET/GET require the JSON module."""
        modules = valkey_client.module_list()
        json_found = any(
            (mod.get(b"name") or mod.get("name", b"")).decode().lower() == "json"
            if isinstance(mod.get(b"name") or mod.get("name", b""), bytes)
            else (mod.get(b"name") or mod.get("name", "")).lower() == "json"
            for mod in modules
        )
        assert json_found, "json module not loaded"


class TestJsonVectorStorage:
    """Validate JSON document storage with vector embeddings."""

    def test_json_set_with_vector(self, valkey_client, clean_state, rng):
        """Store a JSON document with an embedded vector (Kong's storage pattern)."""
        key = INDEX_PREFIX + "doc:1"
        vector = rng.random(DIMENSION, dtype=np.float32).tolist()
        doc = {
            "content": "What is Valkey?",
            "embedding": vector,
            "metadata": {"source": "user", "timestamp": 1234567890},
        }

        valkey_client.execute_command("JSON.SET", key, "$", json.dumps(doc))
        result = valkey_client.execute_command("JSON.GET", key, "$")
        parsed = json.loads(result)
        assert parsed[0]["content"] == "What is Valkey?"
        assert len(parsed[0]["embedding"]) == DIMENSION

    def test_json_delete(self, valkey_client, clean_state, rng):
        """Delete a JSON document."""
        key = INDEX_PREFIX + "doc:del"
        doc = {"content": "temp", "embedding": rng.random(DIMENSION, dtype=np.float32).tolist()}
        valkey_client.execute_command("JSON.SET", key, "$", json.dumps(doc))
        assert valkey_client.exists(key) == 1

        valkey_client.delete(key)
        assert valkey_client.exists(key) == 0


class TestVectorIndexCreation:
    """Validate FT.CREATE with HNSW on JSON paths (Kong's index pattern)."""

    def test_create_hnsw_index_on_json(self, valkey_client, clean_state):
        """Create an HNSW vector index on JSON documents."""
        index_name = INDEX_PREFIX + "semantic-cache"
        prefix = INDEX_PREFIX + "cache:"

        valkey_client.execute_command(
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "$.content", "AS", "content", "TEXT",
        )

        indices = valkey_client.execute_command("FT._LIST")
        index_names = [idx.decode() if isinstance(idx, bytes) else idx for idx in indices]
        assert index_name in index_names

    def test_index_info(self, valkey_client, clean_state):
        """FT.INFO returns index details."""
        index_name = INDEX_PREFIX + "info-test"
        prefix = INDEX_PREFIX + "info:"

        valkey_client.execute_command(
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
        )

        info = valkey_client.execute_command("FT.INFO", index_name)
        assert info is not None


class TestKNNSearch:
    """Validate KNN search matching Kong's semantic similarity queries."""

    def _create_index_and_store(self, client, rng, index_name, prefix, num_docs=5):
        """Helper: create index and store documents."""
        client.execute_command(
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "$.content", "AS", "content", "TEXT",
        )

        vectors = []
        for i in range(num_docs):
            vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            vectors.append(vec)
            doc = {"content": f"Document {i}", "embedding": vec}
            client.execute_command("JSON.SET", f"{prefix}{i}", "$", json.dumps(doc))

        time.sleep(0.5)  # Allow indexing
        return vectors

    def test_knn_basic(self, valkey_client, clean_state, rng):
        """Basic KNN search returns results."""
        index_name = INDEX_PREFIX + "knn-basic"
        prefix = INDEX_PREFIX + "knn:"
        vectors = self._create_index_and_store(valkey_client, rng, index_name, prefix)

        query_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
        result = valkey_client.execute_command(
            "FT.SEARCH", index_name,
            "*=>[KNN 3 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        assert count == 3

    def test_knn_returns_distance_scores(self, valkey_client, clean_state, rng):
        """KNN results include cosine distance scores."""
        index_name = INDEX_PREFIX + "knn-scores"
        prefix = INDEX_PREFIX + "scores:"
        vectors = self._create_index_and_store(valkey_client, rng, index_name, prefix)

        result = valkey_client.execute_command(
            "FT.SEARCH", index_name,
            "*=>[KNN 3 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(vectors[0]),
            "DIALECT", "2",
        )

        # First result should be the vector itself (distance ~0)
        assert result[0] >= 1
        fields = result[2]
        field_pairs = dict(zip(fields[::2], fields[1::2]))
        score_key = b"vector_score"
        assert score_key in field_pairs
        distance = float(field_pairs[score_key])
        assert distance < 0.01  # Near-zero distance to itself

    def test_similarity_threshold(self, valkey_client, clean_state, rng):
        """Verify that cosine distance can be used for threshold filtering."""
        index_name = INDEX_PREFIX + "threshold"
        prefix = INDEX_PREFIX + "thresh:"

        valkey_client.execute_command(
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
        )

        # Store a known vector
        base_vec = np.ones(DIMENSION, dtype=np.float32)
        base_vec = (base_vec / np.linalg.norm(base_vec)).tolist()
        doc = {"embedding": base_vec}
        valkey_client.execute_command("JSON.SET", f"{prefix}base", "$", json.dumps(doc))

        # Store a very different vector
        diff_vec = -np.ones(DIMENSION, dtype=np.float32)
        diff_vec = (diff_vec / np.linalg.norm(diff_vec)).tolist()
        doc2 = {"embedding": diff_vec}
        valkey_client.execute_command("JSON.SET", f"{prefix}diff", "$", json.dumps(doc2))

        time.sleep(0.5)

        # Search with base vector — should find base (distance ~0) and diff (distance ~2)
        result = valkey_client.execute_command(
            "FT.SEARCH", index_name,
            "*=>[KNN 2 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(base_vec),
            "DIALECT", "2",
        )
        assert result[0] == 2

        # First result (closest) should have very low distance
        fields_1 = dict(zip(result[2][::2], result[2][1::2]))
        dist_1 = float(fields_1[b"vector_score"])
        assert dist_1 < 0.1  # Very similar

        # Second result should have high distance
        fields_2 = dict(zip(result[4][::2], result[4][1::2]))
        dist_2 = float(fields_2[b"vector_score"])
        assert dist_2 > 1.5  # Very different (max cosine distance is 2.0)


class TestMultipleIndices:
    """Validate that Kong can create separate indices per plugin."""

    def test_separate_indices_per_plugin(self, valkey_client, clean_state, rng):
        """Each Kong plugin creates its own index (cache, rag, guard, etc.)."""
        plugins = ["semantic-cache", "rag-injector", "prompt-guard", "response-guard"]
        prefixes = {p: f"{INDEX_PREFIX}{p}:" for p in plugins}
        index_names = {p: f"{INDEX_PREFIX}{p}" for p in plugins}

        # Create an index for each plugin
        for plugin in plugins:
            valkey_client.execute_command(
                "FT.CREATE", index_names[plugin],
                "ON", "JSON",
                "PREFIX", "1", prefixes[plugin],
                "SCHEMA",
                "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(DIMENSION),
                "DISTANCE_METRIC", "COSINE",
            )

        # Store a doc in each
        for plugin in plugins:
            vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            doc = {"embedding": vec, "content": f"Doc for {plugin}"}
            valkey_client.execute_command(
                "JSON.SET", f"{prefixes[plugin]}doc1", "$", json.dumps(doc)
            )

        time.sleep(0.5)

        # Verify each index only sees its own documents
        for plugin in plugins:
            query_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            result = valkey_client.execute_command(
                "FT.SEARCH", index_names[plugin],
                "*=>[KNN 5 @embedding $BLOB AS vector_score]",
                "PARAMS", "2", "BLOB", vector_to_bytes(query_vec),
                "DIALECT", "2",
            )
            assert result[0] == 1, f"Expected 1 doc in {plugin} index, got {result[0]}"

    def test_drop_one_index_preserves_others(self, valkey_client, clean_state, rng):
        """Dropping one plugin's index doesn't affect others."""
        idx_a = INDEX_PREFIX + "plugin-a"
        idx_b = INDEX_PREFIX + "plugin-b"
        prefix_a = INDEX_PREFIX + "a:"
        prefix_b = INDEX_PREFIX + "b:"

        for idx, prefix in [(idx_a, prefix_a), (idx_b, prefix_b)]:
            valkey_client.execute_command(
                "FT.CREATE", idx,
                "ON", "JSON",
                "PREFIX", "1", prefix,
                "SCHEMA",
                "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(DIMENSION),
                "DISTANCE_METRIC", "COSINE",
            )
            vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            valkey_client.execute_command(
                "JSON.SET", f"{prefix}doc1", "$", json.dumps({"embedding": vec})
            )

        # Drop index A
        valkey_client.execute_command("FT.DROPINDEX", idx_a)

        # Index B still works
        time.sleep(0.3)
        query_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
        result = valkey_client.execute_command(
            "FT.SEARCH", idx_b,
            "*=>[KNN 5 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        assert result[0] == 1
