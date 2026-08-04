"""CI tests for the Cognee Valkey vector adapter integration.

Uses a deterministic stub embedding engine — no LLM, no Ollama, no embedder
required. Exercises the actual integration point the cookbook samples depend
on: ValkeyAdapter.create_collection / create_data_points / search / prune
against a real Valkey instance.
"""

from __future__ import annotations

import os

import pytest

from cognee.infrastructure.engine import DataPoint
from cognee_community_vector_adapter_valkey import ValkeyAdapter

EMBEDDING_DIM = 8
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "valkey://localhost:6379")


class StubEmbeddingEngine:
    """Deterministic fixed-vector embedder — same text always maps to the same vector."""

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    async def embed_text(self, text: list[str]) -> list[list[float]]:
        vectors = []
        for t in text:
            seed = abs(hash(t)) % 1000
            vectors.append([((seed + i) % 97) / 97.0 for i in range(self.dim)])
        return vectors

    def get_vector_size(self) -> int:
        return self.dim

    def get_batch_size(self) -> int:
        return 32


class TextChunk(DataPoint):
    text: str
    metadata: dict = {"index_fields": ["text"]}


@pytest.fixture
async def adapter():
    """Create a ValkeyAdapter for tests and clean up after."""
    a = ValkeyAdapter(url=VECTOR_DB_URL, embedding_engine=StubEmbeddingEngine())
    yield a
    await a.prune()
    await a.close()


class TestCollectionLifecycle:
    async def test_create_collection_is_idempotent(self, adapter: ValkeyAdapter):
        collection = "test_lifecycle"
        assert await adapter.has_collection(collection) is False

        await adapter.create_collection(collection)
        assert await adapter.has_collection(collection) is True

        # Calling create_collection again on an existing collection must not raise
        await adapter.create_collection(collection)
        assert await adapter.has_collection(collection) is True

    async def test_prune_removes_all_collections(self, adapter: ValkeyAdapter):
        await adapter.create_collection("prune_target_a")
        await adapter.create_collection("prune_target_b")
        assert await adapter.has_collection("prune_target_a") is True

        await adapter.prune()

        assert await adapter.has_collection("prune_target_a") is False
        assert await adapter.has_collection("prune_target_b") is False


class TestDataPoints:
    async def test_create_and_search_data_points(self, adapter: ValkeyAdapter):
        collection = "test_search"
        await adapter.create_collection(collection)

        points = [
            TextChunk(text="Valkey supports HNSW vector indexing."),
            TextChunk(text="Cognee builds knowledge graphs from documents."),
        ]
        await adapter.create_data_points(collection, points)

        results = await adapter.search(
            collection_name=collection,
            query_text="Valkey supports HNSW vector indexing.",
            limit=5,
        )
        assert len(results) >= 1
        # The exact match should score as the closest result (lowest cosine distance)
        result_ids = {str(r.id) for r in results}
        assert str(points[0].id) in result_ids

    async def test_search_on_missing_collection_returns_empty(self, adapter: ValkeyAdapter):
        results = await adapter.search(
            collection_name="does_not_exist",
            query_text="anything",
            limit=5,
        )
        assert results == []

    async def test_delete_data_points(self, adapter: ValkeyAdapter):
        collection = "test_delete"
        await adapter.create_collection(collection)

        point = TextChunk(text="This will be deleted.")
        await adapter.create_data_points(collection, [point])

        results = await adapter.search(collection_name=collection, query_text="deleted", limit=5)
        assert len(results) == 1

        deleted = await adapter.delete_data_points(collection, [str(point.id)])
        assert deleted["deleted"] == 1

    async def test_batch_search(self, adapter: ValkeyAdapter):
        collection = "test_batch_search"
        await adapter.create_collection(collection)

        points = [
            TextChunk(text="Machine learning is a subset of AI."),
            TextChunk(text="Valkey is an open-source key-value store."),
        ]
        await adapter.create_data_points(collection, points)

        results = await adapter.batch_search(
            collection_name=collection,
            query_texts=["Machine learning is a subset of AI.", "Valkey is an open-source key-value store."],
            limit=5,
            max_concurrency=2,
        )
        assert len(results) == 2
        assert all(len(r) >= 1 for r in results)
