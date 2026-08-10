"""Integration tests for DocsGPT + Valkey vector store patterns.

These tests verify the Valkey commands and data patterns that DocsGPT's
ValkeyStore implementation relies on — without importing DocsGPT itself.

Tests run against a real Valkey instance with the valkey-search module loaded.
Start Valkey with: docker compose up -d

Each test exercises a specific pattern from the cookbook:
- Index creation with HNSW vector fields
- Document storage as HASH keys
- KNN vector similarity search
- Source isolation via TAG field filtering
- Chunk management (add, list, delete)
- TAG value escaping for special characters

Note on GLIDE RESP3 format:
  FT.SEARCH returns [total_count, {key: {field: value}, ...}]
  FT.CREATE returns 'OK' (str)
  FT.DROPINDEX returns 'OK' (str)
"""
from __future__ import annotations

import json
import struct
import uuid

import pytest

from glide_sync import GlideClient

from conftest import (
    EMBEDDING_DIM,
    TEST_INDEX_NAME,
    TEST_PREFIX,
    make_embedding,
    skip_if_no_filtered_knn,
)

VECTOR_DIM = EMBEDDING_DIM





def _create_hnsw_index(
    client: GlideClient,
    index_name: str,
    prefix: str,
    dim: int = VECTOR_DIM,
    algorithm: str = "HNSW",
) -> None:
    """Create a vector search index for testing."""
    algo_args = (
        ["HNSW", "10", "TYPE", "FLOAT32", "DIM", str(dim),
         "DISTANCE_METRIC", "COSINE", "M", "16", "EF_CONSTRUCTION", "200"]
        if algorithm == "HNSW"
        else ["FLAT", "6", "TYPE", "FLOAT32", "DIM", str(dim), "DISTANCE_METRIC", "COSINE"]
    )
    client.custom_command(
        ["FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", prefix,
         "SCHEMA", "source_id", "TAG", "embedding", "VECTOR", *algo_args]
    )


class TestConnectivity:
    """Verify basic Valkey connectivity and module availability."""

    def test_ping(self, valkey_client: GlideClient) -> None:
        """GLIDE client can connect and ping."""
        assert valkey_client.ping() == b"PONG"

    def test_search_module_loaded(self, valkey_client: GlideClient) -> None:
        """The valkey-search module is loaded (FT.CREATE succeeds)."""
        result = valkey_client.custom_command(
            [
                "FT.CREATE", TEST_INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", TEST_PREFIX,
                "SCHEMA",
                "source_id", "TAG",
                "embedding", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32", "DIM", "3", "DISTANCE_METRIC", "COSINE",
            ]
        )
        assert result == "OK"


class TestIndexCreation:
    """Verify FT.CREATE with HNSW and FLAT algorithms."""

    def test_create_hnsw_index(self, valkey_client: GlideClient) -> None:
        """Create an HNSW index matching DocsGPT's default configuration."""
        _create_hnsw_index(valkey_client, TEST_INDEX_NAME, TEST_PREFIX)

        # Verify index exists via FT.INFO
        info = valkey_client.custom_command(["FT.INFO", TEST_INDEX_NAME])
        assert info is not None

    def test_create_flat_index(self, valkey_client: GlideClient) -> None:
        """Create a FLAT index (exact search, alternative to HNSW)."""
        _create_hnsw_index(
            valkey_client, TEST_INDEX_NAME, TEST_PREFIX, algorithm="FLAT"
        )

    def test_duplicate_index_raises(self, valkey_client: GlideClient) -> None:
        """Creating an index that already exists raises an error."""
        valkey_client.custom_command(
            [
                "FT.CREATE", TEST_INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", TEST_PREFIX,
                "SCHEMA", "source_id", "TAG",
                "embedding", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32", "DIM", str(VECTOR_DIM),
                "DISTANCE_METRIC", "COSINE",
            ]
        )

        with pytest.raises(Exception, match="already exists|Index already"):
            valkey_client.custom_command(
                [
                    "FT.CREATE", TEST_INDEX_NAME,
                    "ON", "HASH",
                    "PREFIX", "1", TEST_PREFIX,
                    "SCHEMA", "source_id", "TAG",
                    "embedding", "VECTOR", "FLAT", "6",
                    "TYPE", "FLOAT32", "DIM", str(VECTOR_DIM),
                    "DISTANCE_METRIC", "COSINE",
                ]
            )


class TestDocumentStorage:
    """Verify HASH-based document storage matching DocsGPT's pattern."""

    def test_store_document_hash(self, valkey_client: GlideClient) -> None:
        """Store a document as a HASH with content, source_id, metadata, embedding."""
        doc_id = str(uuid.uuid4())
        key = f"{TEST_PREFIX}{doc_id}"
        embedding = make_embedding(0.1)
        metadata = json.dumps({"source": "test.pdf", "page": 1})

        valkey_client.hset(
            key,
            {
                "content": "Valkey is a high-performance data store.",
                "source_id": "test-source",
                "metadata": metadata,
                "embedding": embedding,
            },
        )

        # Verify all fields stored correctly
        content = valkey_client.hget(key, "content")
        assert content == b"Valkey is a high-performance data store."

        source = valkey_client.hget(key, "source_id")
        assert source == b"test-source"

        meta_raw = valkey_client.hget(key, "metadata")
        assert json.loads(meta_raw) == {"source": "test.pdf", "page": 1}

        emb_raw = valkey_client.hget(key, "embedding")
        assert len(emb_raw) == EMBEDDING_DIM * 4  # float32 = 4 bytes each

    def test_store_multiple_documents(self, valkey_client: GlideClient) -> None:
        """Store multiple documents and verify count."""
        for i in range(5):
            key = f"{TEST_PREFIX}{uuid.uuid4()}"
            valkey_client.hset(
                key,
                {
                    "content": f"Document {i}",
                    "source_id": "bulk-source",
                    "metadata": "{}",
                    "embedding": make_embedding(0.1 * i),
                },
            )

        # Count keys with test prefix via SCAN
        count = 0
        cursor = "0"
        while True:
            result = valkey_client.custom_command(
                ["SCAN", cursor, "MATCH", f"{TEST_PREFIX}*", "COUNT", "100"]
            )
            cursor = result[0] if isinstance(result[0], str) else result[0].decode()
            keys = result[1] if isinstance(result[1], list) else []
            count += len(keys)
            if cursor == "0":
                break

        assert count == 5


class TestKNNSearch:
    """Verify KNN vector similarity search via FT.SEARCH."""

    @pytest.fixture(autouse=True)
    def _setup_index_and_docs(self, valkey_client: GlideClient) -> None:
        """Create index and insert test documents before each test."""
        import time

        # Create HNSW index
        _create_hnsw_index(valkey_client, TEST_INDEX_NAME, TEST_PREFIX)

        # Insert 3 documents with distinct embeddings
        docs = [
            ("doc1", "Valkey vector search", "source-a", 0.1),
            ("doc2", "HNSW algorithm details", "source-a", 0.5),
            ("doc3", "Unrelated content", "source-b", 0.9),
        ]
        for doc_id, content, source, seed in docs:
            key = f"{TEST_PREFIX}{doc_id}"
            valkey_client.hset(
                key,
                {
                    "content": content,
                    "source_id": source,
                    "metadata": "{}",
                    "embedding": make_embedding(seed),
                },
            )

        # Brief wait for indexing
        time.sleep(0.2)

    def test_knn_search_returns_results(self, valkey_client: GlideClient) -> None:
        """KNN search returns documents sorted by vector similarity."""
        query_embedding = make_embedding(0.1)  # Closest to doc1

        # GLIDE RESP3 format: [total, {key: {field: val}, ...}]
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "*=>[KNN 3 @embedding $BLOB AS score]",
                "PARAMS", "2", "BLOB", query_embedding,
                "RETURN", "2", "content", "score",
                "LIMIT", "0", "3",
            ]
        )

        # result = [total_count, {key: {fields}, ...}]
        total = result[0]
        assert total >= 1

        # The dict contains key→fields mappings
        docs_map = result[1]
        assert isinstance(docs_map, dict)

        # First result should be doc1 (closest embedding to query)
        # KNN results are sorted by score ascending (closest first)
        keys = list(docs_map.keys())
        first_key = keys[0] if isinstance(keys[0], str) else keys[0].decode()
        assert "doc1" in first_key

    def test_knn_search_with_source_filter(self, valkey_client: GlideClient, search_version: int) -> None:
        """KNN search filtered by source_id returns only matching source."""
        skip_if_no_filtered_knn(search_version)
        query_embedding = make_embedding(0.9)  # Closest to doc3

        # Search only source-a (should NOT return doc3 even though it's closest)
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "@source_id:{source\\-a}=>[KNN 3 @embedding $BLOB AS score]",
                "PARAMS", "2", "BLOB", query_embedding,
                "RETURN", "2", "content", "source_id",
                "LIMIT", "0", "3",
            ]
        )

        total = result[0]
        assert total >= 1

        # Verify all returned results have source_id = source-a
        docs_map = result[1]
        for key, fields in docs_map.items():
            source_val = fields.get(b"source_id", fields.get("source_id"))
            if isinstance(source_val, bytes):
                source_val = source_val.decode()
            assert source_val == "source-a"


class TestSourceIsolation:
    """Verify source isolation via TAG field filtering."""

    @pytest.fixture(autouse=True)
    def _setup_multi_source(self, valkey_client: GlideClient, search_version: int) -> None:
        """Create index with documents across multiple sources."""
        skip_if_no_filtered_knn(search_version)
        import time

        _create_hnsw_index(valkey_client, TEST_INDEX_NAME, TEST_PREFIX)

        # Insert docs across 3 sources
        sources = {
            "projectalpha": ["Doc A1", "Doc A2", "Doc A3"],
            "projectbeta": ["Doc B1", "Doc B2"],
            "projectgamma": ["Doc G1"],
        }
        seed = 0.1
        for source_id, texts in sources.items():
            for text in texts:
                key = f"{TEST_PREFIX}{uuid.uuid4()}"
                valkey_client.hset(
                    key,
                    {
                        "content": text,
                        "source_id": source_id,
                        "metadata": "{}",
                        "embedding": make_embedding(seed),
                    },
                )
                seed += 0.05

        time.sleep(0.2)

    def test_filter_single_source(self, valkey_client: GlideClient) -> None:
        """TAG filter returns only documents from one source."""
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "@source_id:{projectalpha}",
                "RETURN", "1", "content",
                "LIMIT", "0", "100",
            ]
        )

        total = result[0]
        assert total == 3

    def test_filter_excludes_other_sources(self, valkey_client: GlideClient) -> None:
        """TAG filter for one source does not return documents from others."""
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "@source_id:{projectbeta}",
                "RETURN", "1", "content",
                "LIMIT", "0", "100",
            ]
        )

        total = result[0]
        assert total == 2


class TestChunkManagement:
    """Verify chunk add/delete/list operations."""

    @pytest.fixture(autouse=True)
    def _setup_index(self, valkey_client: GlideClient) -> None:
        """Create a search index for chunk management tests."""
        _create_hnsw_index(valkey_client, TEST_INDEX_NAME, TEST_PREFIX)

    def test_delete_single_chunk(self, valkey_client: GlideClient) -> None:
        """Delete a specific document by key."""
        key = f"{TEST_PREFIX}delete-me"
        valkey_client.hset(
            key,
            {
                "content": "This will be deleted",
                "source_id": "test-source",
                "metadata": "{}",
                "embedding": make_embedding(0.1),
            },
        )

        # Verify it exists
        assert valkey_client.hget(key, "content") is not None

        # Delete it
        deleted = valkey_client.delete([key])
        assert deleted == 1

        # Verify it's gone
        assert valkey_client.hget(key, "content") is None

    def test_delete_all_chunks_for_source(self, valkey_client: GlideClient, search_version: int) -> None:
        """Delete all documents for a specific source via FT.SEARCH + DELETE."""
        skip_if_no_filtered_knn(search_version)
        import time

        source_id = "deletesource"

        # Insert 5 documents
        for i in range(5):
            key = f"{TEST_PREFIX}{uuid.uuid4()}"
            valkey_client.hset(
                key,
                {
                    "content": f"Document {i}",
                    "source_id": source_id,
                    "metadata": "{}",
                    "embedding": make_embedding(0.1 * i),
                },
            )

        time.sleep(0.2)

        # Use FT.SEARCH to find all docs for this source
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                f"@source_id:{{{source_id}}}",
                "RETURN", "1", "content",
                "LIMIT", "0", "100",
            ]
        )

        total = result[0]
        assert total == 5

        # Extract keys from the result dict
        docs_map = result[1]
        found_keys = []
        for k in docs_map.keys():
            found_keys.append(k if isinstance(k, str) else k.decode())

        # Delete all found keys
        if found_keys:
            valkey_client.delete(found_keys)

        time.sleep(0.1)

        # Verify deletion
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                f"@source_id:{{{source_id}}}",
                "RETURN", "1", "content",
                "LIMIT", "0", "100",
            ]
        )
        total = result[0]
        assert total == 0

    def test_get_chunks_pagination(self, valkey_client: GlideClient, search_version: int) -> None:
        """Retrieve chunks via paginated FT.SEARCH."""
        skip_if_no_filtered_knn(search_version)
        import time

        source_id = "paginatesource"

        # Insert 10 documents
        for i in range(10):
            key = f"{TEST_PREFIX}{uuid.uuid4()}"
            valkey_client.hset(
                key,
                {
                    "content": f"Paginated doc {i}",
                    "source_id": source_id,
                    "metadata": json.dumps({"index": i}),
                    "embedding": make_embedding(0.01 * i),
                },
            )

        time.sleep(0.2)

        # Page 1: first 5
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                f"@source_id:{{{source_id}}}",
                "RETURN", "2", "content", "metadata",
                "LIMIT", "0", "5",
            ]
        )
        total = result[0]
        assert total == 10  # Total count is always full, LIMIT only limits returned

        docs_map = result[1]
        assert len(docs_map) == 5  # Only 5 returned due to LIMIT

        # Page 2: next 5
        result2 = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                f"@source_id:{{{source_id}}}",
                "RETURN", "2", "content", "metadata",
                "LIMIT", "5", "5",
            ]
        )
        total2 = result2[0]
        assert total2 == 10

        docs_map2 = result2[1]
        assert len(docs_map2) == 5


class TestTagEscaping:
    """Verify special character escaping in TAG field queries.

    DocsGPT source_ids can contain characters that are special in FT.SEARCH
    query syntax (hyphens, slashes, dots). These must be escaped.
    """

    @pytest.fixture(autouse=True)
    def _setup_index(self, valkey_client: GlideClient, search_version: int) -> None:
        """Create index for tag escaping tests."""
        skip_if_no_filtered_knn(search_version)
        import time

        _create_hnsw_index(valkey_client, TEST_INDEX_NAME, TEST_PREFIX)

        # Pre-insert docs with special chars in source_id
        self._hyphen_key = f"{TEST_PREFIX}{uuid.uuid4()}"
        valkey_client.hset(
            self._hyphen_key,
            {
                "content": "Hyphenated source test",
                "source_id": "my-project-docs",
                "metadata": "{}",
                "embedding": make_embedding(0.1),
            },
        )

        self._path_key = f"{TEST_PREFIX}{uuid.uuid4()}"
        valkey_client.hset(
            self._path_key,
            {
                "content": "Path source test",
                "source_id": "application/indexes/my-docs",
                "metadata": "{}",
                "embedding": make_embedding(0.2),
            },
        )

        time.sleep(0.2)

    def test_hyphenated_source_id(self, valkey_client: GlideClient) -> None:
        """Source IDs with hyphens work when properly escaped."""
        # Escape hyphens in the query
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "@source_id:{my\\-project\\-docs}",
                "RETURN", "1", "content",
                "LIMIT", "0", "10",
            ]
        )
        total = result[0]
        assert total == 1

    def test_path_like_source_id(self, valkey_client: GlideClient) -> None:
        """Source IDs with slashes work when properly escaped."""
        # Escape slashes and hyphens
        result = valkey_client.custom_command(
            [
                "FT.SEARCH", TEST_INDEX_NAME,
                "@source_id:{application\\/indexes\\/my\\-docs}",
                "RETURN", "1", "content",
                "LIMIT", "0", "10",
            ]
        )
        total = result[0]
        assert total == 1


class TestVectorEncoding:
    """Verify vector byte encoding matches DocsGPT's struct.pack pattern."""

    def test_float32_encoding(self, valkey_client: GlideClient) -> None:
        """Vectors are stored as little-endian float32 bytes."""
        embedding = [0.1, 0.2, 0.3]
        packed = struct.pack(f"<{len(embedding)}f", *embedding)

        assert len(packed) == len(embedding) * 4  # 4 bytes per float32

        # Unpack and verify
        unpacked = struct.unpack(f"<{len(embedding)}f", packed)
        for orig, decoded in zip(embedding, unpacked):
            assert abs(orig - decoded) < 1e-6

    def test_768_dim_embedding_size(self) -> None:
        """768-dimension embeddings produce 3072 bytes (768 * 4)."""
        embedding = make_embedding(0.1)
        assert len(embedding) == EMBEDDING_DIM * 4
        assert len(embedding) == 3072
