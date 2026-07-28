"""Integration tests validating Open WebUI's ValkeyClient patterns."""

import json
import re
import struct
import time

import numpy as np
import pytest
import valkey

COLLECTION_PREFIX = "test_owui"
COLLECTION_NAME = "test_collection"
INDEX_NAME = f"idx:{COLLECTION_PREFIX}:{COLLECTION_NAME}"
KEY_PREFIX = f"{COLLECTION_PREFIX}:{COLLECTION_NAME}:"
DIMENSION = 128


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32."""
    return struct.pack(f"<{len(vector)}f", *vector)


class TestConnectivity:
    """Validate connectivity, version detection, and module checks."""

    def test_ping(self, valkey_client):
        assert valkey_client.ping() is True

    def test_server_version_detection(self, valkey_client):
        """Open WebUI checks INFO for valkey_version or redis_version."""
        info = valkey_client.info("server")
        version = info.get("valkey_version") or info.get("redis_version")
        assert version is not None
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        assert match is not None
        ver_tuple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        assert ver_tuple >= (9, 0, 1), f"Need >= 9.0.1, got {version}"

    def test_search_module_loaded(self, valkey_client):
        """Open WebUI checks MODULE LIST for 'search' >= 1.2.0."""
        modules = valkey_client.module_list()
        search_mod = None
        for mod in modules:
            name = mod.get(b"name") or mod.get("name", b"")
            if isinstance(name, bytes):
                name = name.decode()
            if name.lower() == "search":
                search_mod = mod
                break
        assert search_mod is not None, "valkey-search module not loaded"
        ver_int = int(search_mod.get(b"ver") or search_mod.get("ver", 0))
        version = (ver_int // 10000, (ver_int % 10000) // 100, ver_int % 100)
        assert version >= (1, 2, 0), f"Need >= 1.2.0, got {version}"

    def test_ft_list(self, valkey_client):
        """FT._LIST should work without error."""
        result = valkey_client.execute_command("FT._LIST")
        assert isinstance(result, list)


class TestIndexCreation:
    """Validate FT.CREATE with HNSW on HASH data."""

    def test_create_hnsw_index(self, valkey_client, clean_collection):
        """Create index matching Open WebUI's _create_index schema."""
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

        # Verify via FT._LIST
        indices = valkey_client.execute_command("FT._LIST")
        index_names = [idx.decode() if isinstance(idx, bytes) else idx for idx in indices]
        assert INDEX_NAME in index_names

    def test_index_info(self, valkey_client, clean_collection):
        """FT.INFO should return index details after creation."""
        valkey_client.execute_command(
            "FT.CREATE", INDEX_NAME,
            "ON", "HASH",
            "PREFIX", "1", KEY_PREFIX,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "text", "TEXT",
            "id", "TAG",
        )
        info = valkey_client.execute_command("FT.INFO", INDEX_NAME)
        assert info is not None

    def test_duplicate_index_raises_error(self, valkey_client, clean_collection):
        """Creating same index twice should raise ResponseError."""
        valkey_client.execute_command(
            "FT.CREATE", INDEX_NAME,
            "ON", "HASH",
            "PREFIX", "1", KEY_PREFIX,
            "SCHEMA",
            "vector", "VECTOR", "FLAT", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "id", "TAG",
        )
        with pytest.raises(valkey.ResponseError, match="already exists"):
            valkey_client.execute_command(
                "FT.CREATE", INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", KEY_PREFIX,
                "SCHEMA",
                "vector", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32",
                "DIM", str(DIMENSION),
                "DISTANCE_METRIC", "COSINE",
                "id", "TAG",
            )


class TestDocumentStorage:
    """Validate HASH document storage matching Open WebUI's insert()."""

    def test_store_and_retrieve(self, valkey_client, clean_collection):
        """HSET + HGETALL with vector bytes + metadata fields."""
        key = KEY_PREFIX + "test-doc-1"
        rng = np.random.default_rng(42)
        vector = rng.random(DIMENSION, dtype=np.float32).tolist()

        mapping = {
            "id": "test-doc-1",
            "vector": vector_to_bytes(vector),
            "text": "Test document content",
            "metadata_json": json.dumps({"source": "test.md", "file_id": "f1"}),
            "hash": "abc123",
            "file_id": "f1",
            "source": "test.md",
            "knowledge_base_id": "kb-1",
        }
        valkey_client.hset(key, mapping=mapping)

        result = valkey_client.hgetall(key)
        assert result[b"id"] == b"test-doc-1"
        assert result[b"text"] == b"Test document content"
        assert result[b"file_id"] == b"f1"
        assert len(result[b"vector"]) == DIMENSION * 4  # float32 = 4 bytes each

    def test_delete_by_key(self, valkey_client, clean_collection):
        """DELETE key removes document (matches Open WebUI's delete by id)."""
        key = KEY_PREFIX + "del-doc"
        valkey_client.hset(key, mapping={"id": "del-doc", "text": "to delete"})
        assert valkey_client.exists(key) == 1

        valkey_client.delete(key)
        assert valkey_client.exists(key) == 0


class TestKNNSearch:
    """Validate KNN search matching Open WebUI's search() method."""

    def test_knn_basic(self, valkey_client, indexed_collection):
        """Basic KNN search returns results."""
        query_vec = indexed_collection[5].tolist()  # Use a vector not in the index
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "*=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        assert count == 3

    def test_knn_returns_document_fields(self, valkey_client, indexed_collection):
        """KNN results include text and metadata fields."""
        query_vec = indexed_collection[5].tolist()
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "*=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        # result = [count, key1, [field1, val1, ...], key2, [...], ...]
        assert result[0] >= 1
        # Check first result has fields
        fields = result[2]  # field-value pairs for first result
        field_names = [f.decode() if isinstance(f, bytes) else f for f in fields[::2]]
        assert "text" in field_names
        assert "__vector_score" in field_names

    def test_knn_results_sorted_by_distance(self, valkey_client, indexed_collection):
        """Results come back sorted by distance (ascending)."""
        query_vec = indexed_collection[5].tolist()
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "*=>[KNN 5 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        # Extract distances
        distances = []
        for i in range(1, len(result) - 1, 2):
            fields = result[i + 1]
            for j in range(0, len(fields), 2):
                fname = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
                if fname == "__vector_score":
                    distances.append(float(fields[j + 1]))
                    break

        # Should be non-decreasing (sorted by distance)
        assert distances == sorted(distances), f"Not sorted: {distances}"


class TestTagFiltering:
    """Validate TAG-filtered KNN matching Open WebUI's filter patterns."""

    def test_tag_filter_exact(self, valkey_client, indexed_collection):
        """Filter by file_id TAG field (exact match)."""
        query_vec = indexed_collection[5].tolist()
        # file-001 appears in docs 0, 2, 4
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "(@file_id:{file\\-001})=>[KNN 5 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        assert count == 3  # docs 0, 2, 4 have file_id=file-001

    def test_tag_filter_or(self, valkey_client, indexed_collection):
        """Filter with OR (matches Open WebUI's $in operator)."""
        query_vec = indexed_collection[5].tolist()
        # file-001 OR file-002
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "(@file_id:{file\\-001|file\\-002})=>[KNN 5 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        assert count == 4  # docs 0, 1, 2, 4

    def test_tag_filter_negation(self, valkey_client, indexed_collection):
        """Negated TAG filter (matches Open WebUI's $ne operator)."""
        query_vec = indexed_collection[5].tolist()
        # NOT file-001 → should get file-002 and file-003 (docs 1, 3)
        result = valkey_client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "(-@file_id:{file\\-001})=>[KNN 5 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        assert count == 2


class TestCollectionManagement:
    """Validate collection reset and namespace isolation."""

    def test_dropindex(self, valkey_client, indexed_collection):
        """FT.DROPINDEX removes the index."""
        valkey_client.execute_command("FT.DROPINDEX", INDEX_NAME)
        indices = valkey_client.execute_command("FT._LIST")
        index_names = [idx.decode() if isinstance(idx, bytes) else idx for idx in indices]
        assert INDEX_NAME not in index_names

    def test_prefix_isolation(self, valkey_client, clean_collection, test_vectors):
        """Different prefixes create isolated search spaces."""
        other_prefix = "other_prefix:"
        other_index = "idx:other_prefix:other_coll"

        try:
            # Create main index
            valkey_client.execute_command(
                "FT.CREATE", INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", KEY_PREFIX,
                "SCHEMA",
                "vector", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(DIMENSION),
                "DISTANCE_METRIC", "COSINE",
                "id", "TAG",
            )

            # Create other index
            valkey_client.execute_command(
                "FT.CREATE", other_index,
                "ON", "HASH",
                "PREFIX", "1", other_prefix,
                "SCHEMA",
                "vector", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(DIMENSION),
                "DISTANCE_METRIC", "COSINE",
                "id", "TAG",
            )

            # Store in main
            valkey_client.hset(KEY_PREFIX + "main-1", mapping={
                "id": "main-1",
                "vector": vector_to_bytes(test_vectors[0].tolist()),
            })

            # Store in other
            valkey_client.hset(other_prefix + "other-1", mapping={
                "id": "other-1",
                "vector": vector_to_bytes(test_vectors[1].tolist()),
            })

            time.sleep(0.5)

            # Search main → only finds main docs
            query_vec = test_vectors[2].tolist()
            result = valkey_client.execute_command(
                "FT.SEARCH", INDEX_NAME,
                "*=>[KNN 5 @vector $query_vec]",
                "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
                "DIALECT", "2",
            )
            assert result[0] == 1

            # Search other → only finds other docs
            result = valkey_client.execute_command(
                "FT.SEARCH", other_index,
                "*=>[KNN 5 @vector $query_vec]",
                "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
                "DIALECT", "2",
            )
            assert result[0] == 1

        finally:
            try:
                valkey_client.execute_command("FT.DROPINDEX", other_index)
            except valkey.ResponseError:
                pass
            cursor = 0
            while True:
                cursor, keys = valkey_client.scan(cursor, match=other_prefix + "*", count=100)
                if keys:
                    valkey_client.delete(*keys)
                if cursor == 0:
                    break
