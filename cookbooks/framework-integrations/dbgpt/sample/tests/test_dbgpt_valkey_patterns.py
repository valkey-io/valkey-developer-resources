"""Integration tests for DB-GPT + Valkey patterns.

Tests the underlying Valkey operations used by DB-GPT's ValkeyStore and
ValkeyCacheStorage, using mock embeddings (no paid API required).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import struct

import pytest
from glide import GlideClient


# --- Helpers ---

VECTOR_DIM = 64


def mock_embedding(seed: int, dim: int = VECTOR_DIM) -> list[float]:
    """Generate a deterministic mock embedding."""
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def to_bytes(embedding: list[float]) -> bytes:
    """Convert float list to FLOAT32 bytes."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


async def create_hnsw_index(
    client: GlideClient,
    index_name: str,
    key_prefix: str,
    dim: int = VECTOR_DIM,
    extra_schema: list[str] | None = None,
) -> None:
    """Create an HNSW index for testing.

    Args:
        client: Valkey client.
        index_name: Name for the FT index.
        key_prefix: Key prefix to index.
        dim: Vector dimension.
        extra_schema: Additional schema fields (e.g., ["category", "TAG", "year", "NUMERIC"]).
    """
    schema = [
        "vector", "VECTOR", "HNSW", "10",
        "TYPE", "FLOAT32",
        "DIM", str(dim),
        "DISTANCE_METRIC", "COSINE",
        "M", "16",
        "EF_CONSTRUCTION", "200",
    ]
    if extra_schema:
        schema.extend(extra_schema)

    await client.custom_command(
        ["FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", key_prefix, "SCHEMA"]
        + schema
    )


async def wait_for_indexing(client: GlideClient, index_name: str) -> None:
    """Poll FT.INFO until indexing completes."""
    for _ in range(100):  # max 5 seconds at 50ms intervals
        info = await client.custom_command(["FT.INFO", index_name])
        # valkey-glide 2.3+ returns FT.INFO as a dict with bytes keys
        backfill = info.get(b"backfill_in_progress", b"0")
        if backfill in (b"0", "0", 0):
            return
        await asyncio.sleep(0.05)  # 50ms poll — demo only; production: poll FT.INFO "backfill_in_progress" field
    pytest.fail("Indexing did not complete within timeout")


# --- Vector Store Tests ---


class TestVectorStorePatterns:
    """Tests for patterns used by DB-GPT's ValkeyStore."""

    @pytest.fixture
    def index_name(self) -> str:
        return "__test_hnsw_idx__"

    @pytest.fixture
    def key_prefix(self) -> str:
        return "__test__:"

    async def test_create_hnsw_index(self, clean_valkey: GlideClient, index_name: str, key_prefix: str) -> None:
        """ValkeyStore creates an HNSW index on first use."""
        await create_hnsw_index(clean_valkey, index_name, key_prefix)

        # Verify index exists via FT.INFO
        info = await clean_valkey.custom_command(["FT.INFO", index_name])
        assert info is not None
        # FT.INFO returns a dict; verify the index name is present in its string representation
        info_str = str(info)
        assert index_name in info_str

    async def test_create_flat_index(self, clean_valkey: GlideClient) -> None:
        """ValkeyStore supports FLAT index type for small datasets."""
        flat_index = "__test_flat_idx__"
        await clean_valkey.custom_command(
            [
                "FT.CREATE", flat_index,
                "ON", "HASH",
                "PREFIX", "1", "__test__:",
                "SCHEMA",
                "vector", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32",
                "DIM", str(VECTOR_DIM),
                "DISTANCE_METRIC", "L2",
            ]
        )

        info = await clean_valkey.custom_command(["FT.INFO", flat_index])
        assert info is not None

    async def test_load_documents(self, clean_valkey: GlideClient, index_name: str, key_prefix: str) -> None:
        """ValkeyStore.load_document stores chunks as HASH keys."""
        # Drop index if left over from a previous test
        try:
            await clean_valkey.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

        # Create index first
        await create_hnsw_index(clean_valkey, index_name, key_prefix)

        # Store documents
        for i in range(5):
            key = f"{key_prefix}{i:04d}"
            embedding = mock_embedding(seed=i)
            await clean_valkey.hset(
                key,
                {
                    "vector": to_bytes(embedding),
                    "content": f"Test document {i}",
                    "metadata": json.dumps({"index": i}),
                },
            )

        # Verify documents are stored
        content = await clean_valkey.hget(f"{key_prefix}0000", "content")
        assert content == b"Test document 0"

        vec_bytes = await clean_valkey.hget(f"{key_prefix}0000", "vector")
        assert vec_bytes is not None
        assert len(vec_bytes) == VECTOR_DIM * 4  # FLOAT32 = 4 bytes per dim

    async def test_knn_search(self, clean_valkey: GlideClient, index_name: str, key_prefix: str) -> None:
        """ValkeyStore.similar_search performs KNN via FT.SEARCH."""
        # Drop index if left over from a previous test
        try:
            await clean_valkey.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

        # Create index and load documents
        await create_hnsw_index(clean_valkey, index_name, key_prefix)

        for i in range(5):
            key = f"{key_prefix}{i:04d}"
            embedding = mock_embedding(seed=i)
            await clean_valkey.hset(
                key,
                {
                    "vector": to_bytes(embedding),
                    "content": f"Document about topic {i}",
                },
            )

        await wait_for_indexing(clean_valkey, index_name)

        # KNN search with the same embedding as doc 0 — should return doc 0 first
        query_vec = to_bytes(mock_embedding(seed=0))
        result = await clean_valkey.custom_command(
            [
                "FT.SEARCH", index_name,
                "*=>[KNN 3 @vector $query_vec]",
                "PARAMS", "2", "query_vec", query_vec,
                "RETURN", "2", "content", "__vector_score",
                "DIALECT", "2",
            ]
        )

        # Result format: [total_count, {key: {field: value, ...}, ...}]
        total = result[0]
        assert total >= 1

        # First result should be the exact match (score ~ 0.0 for cosine)
        results_dict = result[1]
        keys_list = list(results_dict.keys())
        first_key = keys_list[0] if isinstance(keys_list[0], str) else keys_list[0].decode()
        assert first_key == f"{key_prefix}0000"

    async def test_metadata_filtering_tag(self, clean_valkey: GlideClient) -> None:
        """ValkeyStore supports TAG metadata filtering."""
        index_name = "__test_meta_idx__"
        key_prefix = "__test__:"

        # Drop index if left over from a previous test
        try:
            await clean_valkey.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

        await create_hnsw_index(
            clean_valkey, index_name, key_prefix,
            extra_schema=["category", "TAG", "year", "NUMERIC"],
        )

        # Load documents with metadata
        docs = [
            {"content": "Valkey database info", "category": "database", "year": "2024"},
            {"content": "Algorithm details", "category": "algorithms", "year": "2023"},
            {"content": "Another database doc", "category": "database", "year": "2023"},
        ]

        for i, doc in enumerate(docs):
            key = f"{key_prefix}{i:04d}"
            embedding = mock_embedding(seed=i + 100)
            await clean_valkey.hset(
                key,
                {
                    "vector": to_bytes(embedding),
                    "content": doc["content"],
                    "category": doc["category"],
                    "year": doc["year"],
                },
            )

        await wait_for_indexing(clean_valkey, index_name)

        # Search with TAG filter
        query_vec = to_bytes(mock_embedding(seed=100))
        result = await clean_valkey.custom_command(
            [
                "FT.SEARCH", index_name,
                "(@category:{database})=>[KNN 3 @vector $query_vec]",
                "PARAMS", "2", "query_vec", query_vec,
                "RETURN", "2", "content", "category",
                "DIALECT", "2",
            ]
        )

        # Result format: [total_count, {key: {field: value, ...}, ...}]
        total = result[0]
        assert total == 2  # Only "database" category docs

    async def test_metadata_filtering_numeric(self, clean_valkey: GlideClient) -> None:
        """ValkeyStore supports NUMERIC range metadata filtering."""
        index_name = "__test_meta_idx__"
        key_prefix = "__test__:"

        # Drop index if left over from a previous test
        try:
            await clean_valkey.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

        await create_hnsw_index(
            clean_valkey, index_name, key_prefix,
            extra_schema=["year", "NUMERIC"],
        )

        for i, year in enumerate([2022, 2023, 2024, 2024]):
            key = f"{key_prefix}{i:04d}"
            embedding = mock_embedding(seed=i + 200)
            await clean_valkey.hset(
                key,
                {
                    "vector": to_bytes(embedding),
                    "content": f"Doc from {year}",
                    "year": str(year),
                },
            )

        await wait_for_indexing(clean_valkey, index_name)

        # Search with NUMERIC filter: year == 2024
        query_vec = to_bytes(mock_embedding(seed=200))
        result = await clean_valkey.custom_command(
            [
                "FT.SEARCH", index_name,
                "(@year:[2024 2024])=>[KNN 3 @vector $query_vec]",
                "PARAMS", "2", "query_vec", query_vec,
                "RETURN", "2", "content", "year",
                "DIALECT", "2",
            ]
        )

        # Result format: [total_count, {key: {field: value, ...}, ...}]
        total = result[0]
        assert total == 2  # Only year=2024 docs

    async def test_delete_by_key(self, clean_valkey: GlideClient, key_prefix: str) -> None:
        """ValkeyStore.delete_by_ids removes specific documents."""
        key = f"{key_prefix}delete_test"
        await clean_valkey.hset(key, {"content": "to be deleted"})

        # Verify exists
        content = await clean_valkey.hget(key, "content")
        assert content == b"to be deleted"

        # Delete
        deleted = await clean_valkey.delete([key])
        assert deleted == 1

        # Verify gone
        content = await clean_valkey.hget(key, "content")
        assert content is None

    async def test_drop_index(self, clean_valkey: GlideClient, index_name: str, key_prefix: str) -> None:
        """ValkeyStore.delete_vector_name drops the index."""
        # Drop index if left over from a previous test
        try:
            await clean_valkey.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

        # Create index
        await clean_valkey.custom_command(
            [
                "FT.CREATE", index_name,
                "ON", "HASH",
                "PREFIX", "1", key_prefix,
                "SCHEMA",
                "vector", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32",
                "DIM", str(VECTOR_DIM),
                "DISTANCE_METRIC", "COSINE",
            ]
        )

        # Drop with DD (delete documents too)
        await clean_valkey.custom_command(["FT.DROPINDEX", index_name])

        # Verify index is gone
        with pytest.raises(Exception):
            await clean_valkey.custom_command(["FT.INFO", index_name])


# --- Cache Tests ---


class TestCachePatterns:
    """Tests for patterns used by DB-GPT's ValkeyCacheStorage."""

    @pytest.fixture
    def cache_prefix(self) -> str:
        return "__test_cache__:"

    async def test_set_and_get(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """ValkeyCacheStorage.set/get stores and retrieves values."""
        key = f"{cache_prefix}basic"
        value = json.dumps({"response": "cached LLM output", "tokens": 42})

        await clean_valkey.set(key, value)
        result = await clean_valkey.get(key)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["response"] == "cached LLM output"
        assert parsed["tokens"] == 42

    async def test_exists(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """ValkeyCacheStorage.exists checks key presence."""
        key = f"{cache_prefix}exists_test"

        # Should not exist yet
        exists = await clean_valkey.exists([key])
        assert exists == 0

        # Set and verify
        await clean_valkey.set(key, "value")
        exists = await clean_valkey.exists([key])
        assert exists == 1

    async def test_ttl_expiration(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """Cache entries expire after TTL."""
        key = f"{cache_prefix}ttl_test"
        await clean_valkey.set(key, "expires soon")
        await clean_valkey.expire(key, 1)  # 1 second TTL

        # Should exist immediately
        result = await clean_valkey.get(key)
        assert result is not None

        # Wait for expiry
        await asyncio.sleep(1.5)

        # Should be gone
        result = await clean_valkey.get(key)
        assert result is None

    async def test_cache_key_determinism(self) -> None:
        """Cache keys are deterministic for the same input."""
        key1 = self._make_key("prompt", "model", {"temp": 0.7})
        key2 = self._make_key("prompt", "model", {"temp": 0.7})
        key3 = self._make_key("prompt", "model", {"temp": 0.8})

        assert key1 == key2
        assert key1 != key3

    async def test_cache_miss_returns_none(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """Cache miss returns None (not an error)."""
        result = await clean_valkey.get(f"{cache_prefix}nonexistent_key_12345")
        assert result is None

    async def test_overwrite_cached_value(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """Updating a cached value overwrites the previous one."""
        key = f"{cache_prefix}overwrite"
        await clean_valkey.set(key, "first")
        await clean_valkey.set(key, "second")

        result = await clean_valkey.get(key)
        assert result == b"second"

    async def test_scan_cache_keys(self, clean_valkey: GlideClient, cache_prefix: str) -> None:
        """Cache keys can be enumerated via SCAN (never KEYS)."""
        # Create several cache keys
        for i in range(5):
            await clean_valkey.set(f"{cache_prefix}scan_{i}", f"value_{i}")

        # Scan for them
        found_keys: list[str] = []
        cursor = "0"
        while True:
            result = await clean_valkey.custom_command(
                ["SCAN", cursor, "MATCH", f"{cache_prefix}scan_*", "COUNT", "100"]
            )
            cursor = result[0] if isinstance(result[0], str) else result[0].decode()
            for k in result[1]:
                found_keys.append(k if isinstance(k, str) else k.decode())
            if cursor == "0":
                break

        assert len(found_keys) == 5

    @staticmethod
    def _make_key(prompt: str, model: str, params: dict) -> str:
        """Helper to generate cache key (mirrors ValkeyCacheStorage)."""
        key_data = json.dumps(
            {"prompt": prompt, "model": model, "params": params},
            sort_keys=True,
        )
        return f"llm_cache:{hashlib.sha256(key_data.encode()).hexdigest()}"
