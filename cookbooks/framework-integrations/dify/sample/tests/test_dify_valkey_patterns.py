"""Integration tests validating the Valkey patterns used by Dify's vector store.

These tests exercise the same Valkey commands and data structures that Dify's
ValkeyVector class uses internally, without importing Dify itself. This verifies
that a Valkey instance with the valkey-search module supports all required
operations for the Dify knowledge base feature.

Requires: Valkey with valkey-search module running on localhost:6379.
"""

from __future__ import annotations

import json
import struct
import uuid

import pytest
import pytest_asyncio
from glide import GlideClient


# ---------------------------------------------------------------------------
# Helpers (mirror Dify's internal functions)
# ---------------------------------------------------------------------------


def float_vector_to_bytes(vector: list[float]) -> bytes:
    """Pack a list of floats into little-endian FLOAT32 bytes."""
    return struct.pack(f"<{len(vector)}f", *vector)


def bytes_to_float_vector(data: bytes) -> list[float]:
    """Unpack little-endian FLOAT32 bytes back into a list of floats."""
    count = len(data) // 4
    return list(struct.unpack(f"<{count}f", data))


def escape_tag(value: str) -> str:
    """Escape special characters in a TAG value for FT.SEARCH queries."""
    special = r"\.+*?[{()|^$!<>~@&\"-]"
    return "".join(f"\\{ch}" if ch in special else ch for ch in value)


def to_str(value) -> str:
    """Convert bytes or other types to str."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VECTOR_DIM = 128


# ---------------------------------------------------------------------------
# Tests: Connectivity & Module
# ---------------------------------------------------------------------------


class TestConnectivity:
    """Verify Valkey is reachable and has the search module."""

    @pytest.mark.asyncio
    async def test_ping(self, valkey_client: GlideClient):
        result = await valkey_client.ping()
        assert to_str(result) == "PONG"

    @pytest.mark.asyncio
    async def test_search_module_loaded(self, valkey_client: GlideClient):
        """Verify the valkey-search module is available."""
        result = await valkey_client.custom_command(["MODULE", "LIST"])
        # Glide may return list of dicts or list of lists depending on version
        module_names = []
        for module_info in result:
            if isinstance(module_info, dict):
                # [{b'name': b'search', b'ver': N, ...}, ...]
                name_val = module_info.get(b"name") or module_info.get("name")
                if name_val:
                    module_names.append(to_str(name_val))
            elif isinstance(module_info, (list, tuple)):
                items = [to_str(x) for x in module_info]
                for i, item in enumerate(items):
                    if item == "name" and i + 1 < len(items):
                        module_names.append(items[i + 1])
        assert "search" in module_names, (
            f"valkey-search module not loaded. Found modules: {module_names}. "
            f"Raw result sample: {result[:2] if result else result}"
        )


# ---------------------------------------------------------------------------
# Tests: Index Creation (FT.CREATE)
# ---------------------------------------------------------------------------


class TestIndexCreation:
    """Test FT.CREATE with the schema Dify uses."""

    @pytest_asyncio.fixture(autouse=True)
    async def _setup_index(self, valkey_client: GlideClient):
        """Ensure index doesn't exist before test, clean up after."""
        self.collection = f"test_idx_{uuid.uuid4().hex[:8]}"
        self.prefix = f"doc:{self.collection}:"
        self.index_name = f"idx:{self.collection}"
        yield
        try:
            await valkey_client.custom_command(["FT.DROPINDEX", self.index_name])
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_create_hnsw_index(self, valkey_client: GlideClient):
        """Create an HNSW vector index matching Dify's schema."""
        result = await valkey_client.custom_command([
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])
        assert to_str(result) == "OK"

    @pytest.mark.asyncio
    async def test_index_info(self, valkey_client: GlideClient):
        """Verify FT.INFO returns expected index metadata after creation."""
        await valkey_client.custom_command([
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])

        info = await valkey_client.custom_command(["FT.INFO", self.index_name])
        # FT.INFO returns a flat array of key-value pairs
        info_strs = [to_str(item) for item in info if isinstance(item, (str, bytes))]
        assert self.index_name in info_strs or self.collection in str(info)


# ---------------------------------------------------------------------------
# Tests: Document Storage (HSET)
# ---------------------------------------------------------------------------


class TestDocumentStorage:
    """Test storing and retrieving documents as HASH keys."""

    @pytest_asyncio.fixture(autouse=True)
    async def _setup(self, valkey_client: GlideClient):
        """Set up unique prefix and clean up test keys."""
        self.collection = f"test_doc_{uuid.uuid4().hex[:8]}"
        self.prefix = f"doc:{self.collection}:"
        self.group_id = "dataset_test_001"
        self._keys: list[str] = []
        yield
        if self._keys:
            try:
                await valkey_client.delete(self._keys)
            except Exception:
                pass

    def _key(self, doc_id: str) -> str:
        key = f"{self.prefix}{doc_id}"
        self._keys.append(key)
        return key

    @pytest.mark.asyncio
    async def test_store_document_hash(self, valkey_client: GlideClient):
        """Store a document with vector, content, and metadata."""
        key = self._key("doc_001")
        embedding = [0.1] * VECTOR_DIM
        vector_bytes = float_vector_to_bytes(embedding)

        metadata = {"source": "test.pdf", "page": 1}
        result = await valkey_client.hset(key, {
            "vector": vector_bytes,
            "page_content": "Valkey is a high-performance data store.",
            "metadata": json.dumps(metadata),
            "group_id": self.group_id,
            "doc_id": "doc_001",
            "document_id": "file_001",
        })
        assert result >= 0  # number of fields added

    @pytest.mark.asyncio
    async def test_retrieve_document(self, valkey_client: GlideClient):
        """Retrieve a stored document and verify all fields."""
        key = self._key("doc_002")
        embedding = [0.5, -0.3] + [0.0] * (VECTOR_DIM - 2)
        vector_bytes = float_vector_to_bytes(embedding)

        await valkey_client.hset(key, {
            "vector": vector_bytes,
            "page_content": "Test document for retrieval.",
            "metadata": json.dumps({"key": "value"}),
            "group_id": self.group_id,
            "doc_id": "doc_002",
            "document_id": "file_002",
        })

        # Retrieve specific fields
        content = await valkey_client.hget(key, "page_content")
        assert content is not None
        assert to_str(content) == "Test document for retrieval."

        # Retrieve and decode vector
        raw_vector = await valkey_client.hget(key, "vector")
        assert raw_vector is not None
        decoded = bytes_to_float_vector(raw_vector)
        assert len(decoded) == VECTOR_DIM
        assert abs(decoded[0] - 0.5) < 1e-6
        assert abs(decoded[1] - (-0.3)) < 1e-6

    @pytest.mark.asyncio
    async def test_document_exists(self, valkey_client: GlideClient):
        """Test EXISTS check for documents (used by Dify's text_exists)."""
        key = self._key("doc_exists_test")

        # Should not exist yet
        count = await valkey_client.exists([key])
        assert count == 0

        # Create it
        await valkey_client.hset(key, {
            "vector": float_vector_to_bytes([0.0] * VECTOR_DIM),
            "page_content": "exists test",
            "metadata": "{}",
            "group_id": self.group_id,
            "doc_id": "doc_exists_test",
            "document_id": "file_ex",
        })

        # Should exist now
        count = await valkey_client.exists([key])
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_documents(self, valkey_client: GlideClient):
        """Test bulk deletion of document keys."""
        keys = []
        for i in range(5):
            key = f"{self.prefix}del_{i}"
            self._keys.append(key)
            await valkey_client.hset(key, {
                "vector": float_vector_to_bytes([float(i)] * VECTOR_DIM),
                "page_content": f"doc {i}",
                "metadata": "{}",
                "group_id": self.group_id,
                "doc_id": f"del_{i}",
                "document_id": "file_del",
            })
            keys.append(key)

        # Delete all at once
        deleted = await valkey_client.delete(keys)
        assert deleted == 5

        # Verify they're gone
        count = await valkey_client.exists(keys)
        assert count == 0


# ---------------------------------------------------------------------------
# Tests: Vector Search (FT.SEARCH with KNN)
# ---------------------------------------------------------------------------


class TestVectorSearch:
    """Test KNN vector similarity search (Dify's search_by_vector)."""

    @pytest_asyncio.fixture(autouse=True)
    async def _setup_index(self, valkey_client: GlideClient):
        """Create a unique index for vector search tests."""
        self.collection = f"test_knn_{uuid.uuid4().hex[:8]}"
        self.prefix = f"doc:{self.collection}:"
        self.index_name = f"idx:{self.collection}"
        self.group_id = "dataset_knn_001"

        await valkey_client.custom_command([
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])
        yield
        try:
            await valkey_client.custom_command(["FT.DROPINDEX", self.index_name])
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_knn_search(self, valkey_client: GlideClient):
        """Add documents and perform KNN search."""
        docs = [
            ("knn_1", [1.0] + [0.0] * (VECTOR_DIM - 1), "First document"),
            ("knn_2", [0.0, 1.0] + [0.0] * (VECTOR_DIM - 2), "Second document"),
            ("knn_3", [0.9, 0.1] + [0.0] * (VECTOR_DIM - 2), "Third document"),
        ]

        for doc_id, embedding, content in docs:
            key = f"{self.prefix}{doc_id}"
            await valkey_client.hset(key, {
                "vector": float_vector_to_bytes(embedding),
                "page_content": content,
                "metadata": json.dumps({"doc_id": doc_id}),
                "group_id": self.group_id,
                "doc_id": doc_id,
                "document_id": "file_knn",
            })

        # Query vector similar to doc 1 and 3
        query_vector = float_vector_to_bytes([0.95, 0.05] + [0.0] * (VECTOR_DIM - 2))
        query = f"(@group_id:{{{escape_tag(self.group_id)}}})=>[KNN 3 @vector $query_vector]"

        result = await valkey_client.custom_command([
            "FT.SEARCH", self.index_name, query,
            "PARAMS", "2", "query_vector", query_vector,
            "LIMIT", "0", "3",
            "RETURN", "3", "page_content", "metadata", "__vector_score",
        ])

        # Result: [total_count, key1, [field, value, ...], key2, ...]
        assert result is not None
        total = int(result[0])
        assert total >= 1

    @pytest.mark.asyncio
    async def test_knn_search_with_document_filter(self, valkey_client: GlideClient):
        """KNN search filtered by document_id TAG (Dify's document_ids_filter)."""
        # Two docs, different document_id
        for i, doc_file in enumerate(["fileA", "fileB"]):
            key = f"{self.prefix}filter_{i}"
            await valkey_client.hset(key, {
                "vector": float_vector_to_bytes([float(i + 1)] * VECTOR_DIM),
                "page_content": f"Document from {doc_file}",
                "metadata": json.dumps({"doc_id": f"filter_{i}"}),
                "group_id": self.group_id,
                "doc_id": f"filter_{i}",
                "document_id": doc_file,
            })

        # Search only in fileA
        query_vector = float_vector_to_bytes([1.0] * VECTOR_DIM)
        query = (
            f"(@group_id:{{{escape_tag(self.group_id)}}} "
            f"@document_id:{{{escape_tag('fileA')}}})"
            f"=>[KNN 2 @vector $query_vector]"
        )

        result = await valkey_client.custom_command([
            "FT.SEARCH", self.index_name, query,
            "PARAMS", "2", "query_vector", query_vector,
            "LIMIT", "0", "2",
            "RETURN", "1", "document_id",
        ])

        # Should return at least one result (fileA doc)
        total = int(result[0])
        assert total >= 1

        # Verify fileA is in the results
        result_str = str(result)
        assert "fileA" in result_str


# ---------------------------------------------------------------------------
# Tests: Full-Text Search
# ---------------------------------------------------------------------------


class TestFullTextSearch:
    """Test full-text search on page_content (Dify's search_by_full_text)."""

    @pytest_asyncio.fixture(autouse=True)
    async def _setup_index(self, valkey_client: GlideClient):
        """Create a unique index for full-text search tests."""
        self.collection = f"test_ft_{uuid.uuid4().hex[:8]}"
        self.prefix = f"doc:{self.collection}:"
        self.index_name = f"idx:{self.collection}"
        self.group_id = "dataset_ft_001"

        await valkey_client.custom_command([
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])
        yield
        try:
            await valkey_client.custom_command(["FT.DROPINDEX", self.index_name])
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_text_search(self, valkey_client: GlideClient):
        """Search by keyword in page_content."""
        await valkey_client.hset(f"{self.prefix}txt_1", {
            "vector": float_vector_to_bytes([0.0] * VECTOR_DIM),
            "page_content": "Valkey provides extremely fast in-memory data access",
            "metadata": "{}",
            "group_id": self.group_id,
            "doc_id": "txt_1",
            "document_id": "file_txt",
        })
        await valkey_client.hset(f"{self.prefix}txt_2", {
            "vector": float_vector_to_bytes([0.0] * VECTOR_DIM),
            "page_content": "PostgreSQL is a relational database management system",
            "metadata": "{}",
            "group_id": self.group_id,
            "doc_id": "txt_2",
            "document_id": "file_txt",
        })

        # Search for "Valkey"
        query = f"@group_id:{{{escape_tag(self.group_id)}}} @page_content:Valkey"
        result = await valkey_client.custom_command([
            "FT.SEARCH", self.index_name, query,
            "LIMIT", "0", "10",
            "RETURN", "1", "page_content",
        ])

        total = int(result[0])
        assert total >= 1


# ---------------------------------------------------------------------------
# Tests: Delete by Query (FT.SEARCH + DELETE pattern)
# ---------------------------------------------------------------------------


class TestDeleteByQuery:
    """Test the search-then-delete pattern Dify uses for group/doc deletion."""

    @pytest_asyncio.fixture(autouse=True)
    async def _setup_index(self, valkey_client: GlideClient):
        """Create a unique index for deletion tests."""
        self.collection = f"test_del_{uuid.uuid4().hex[:8]}"
        self.prefix = f"doc:{self.collection}:"
        self.index_name = f"idx:{self.collection}"
        self.group_id = "dataset_del_001"

        await valkey_client.custom_command([
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])
        yield
        try:
            await valkey_client.custom_command(["FT.DROPINDEX", self.index_name])
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_delete_by_group_id(self, valkey_client: GlideClient):
        """Delete all documents in a group (Dify's delete() method)."""
        from glide.async_commands.server_modules import ft
        from glide.async_commands.server_modules.ft_options.ft_search_options import (
            FtSearchLimit,
            FtSearchOptions,
        )

        # Add docs to our group and a different group
        for i in range(3):
            await valkey_client.hset(f"{self.prefix}grp_{i}", {
                "vector": float_vector_to_bytes([0.0] * VECTOR_DIM),
                "page_content": f"group doc {i}",
                "metadata": "{}",
                "group_id": self.group_id,
                "doc_id": f"grp_{i}",
                "document_id": "file_grp",
            })

        other_group = "other_group_999"
        await valkey_client.hset(f"{self.prefix}other_0", {
            "vector": float_vector_to_bytes([0.0] * VECTOR_DIM),
            "page_content": "other group doc",
            "metadata": "{}",
            "group_id": other_group,
            "doc_id": "other_0",
            "document_id": "file_other",
        })

        # Search for keys in our group
        query = f"@group_id:{{{escape_tag(self.group_id)}}}"
        opts = FtSearchOptions(
            return_fields=[],
            limit=FtSearchLimit(offset=0, count=100),
        )
        result = await ft.search(valkey_client, self.index_name, query, opts)

        # result = [total_count, {key: {fields...}, ...}]
        total = result[0]
        assert total == 3

        # Delete those keys
        keys_to_delete = [
            k.decode() if isinstance(k, bytes) else str(k)
            for k in result[1].keys()
        ]
        if keys_to_delete:
            await valkey_client.delete(keys_to_delete)

        # Verify our group is gone
        result = await ft.search(valkey_client, self.index_name, query, opts)
        assert result[0] == 0

        # Other group still exists
        other_query = f"@group_id:{{{escape_tag(other_group)}}}"
        result = await ft.search(valkey_client, self.index_name, other_query, opts)
        assert result[0] == 1


# ---------------------------------------------------------------------------
# Tests: Distance Metric Conversion (pure logic, no Valkey needed)
# ---------------------------------------------------------------------------


class TestDistanceConversion:
    """Test distance-to-similarity conversion (pure logic)."""

    def test_cosine_similarity(self):
        """COSINE: similarity = 1 - distance/2, range [0, 1]."""
        assert abs(_distance_to_similarity(0.0, "COSINE") - 1.0) < 1e-9
        assert abs(_distance_to_similarity(1.0, "COSINE") - 0.5) < 1e-9
        assert abs(_distance_to_similarity(2.0, "COSINE") - 0.0) < 1e-9

    def test_l2_similarity(self):
        """L2: similarity = 1 / (1 + distance)."""
        assert abs(_distance_to_similarity(0.0, "L2") - 1.0) < 1e-9
        assert abs(_distance_to_similarity(1.0, "L2") - 0.5) < 1e-9
        assert _distance_to_similarity(100.0, "L2") < 0.01

    def test_ip_similarity(self):
        """IP: similarity = 1 - distance."""
        assert abs(_distance_to_similarity(0.0, "IP") - 1.0) < 1e-9
        assert abs(_distance_to_similarity(0.5, "IP") - 0.5) < 1e-9
        assert abs(_distance_to_similarity(1.0, "IP") - 0.0) < 1e-9


def _distance_to_similarity(distance: float, metric: str) -> float:
    """Mirror of Dify's distance-to-similarity conversion."""
    metric_upper = metric.upper()
    if metric_upper == "COSINE":
        return 1.0 - distance / 2.0
    if metric_upper == "L2":
        return 1.0 / (1.0 + distance)
    if metric_upper == "IP":
        return 1.0 - distance
    return 1.0 - distance
