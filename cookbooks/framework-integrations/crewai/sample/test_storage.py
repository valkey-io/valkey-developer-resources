"""CI tests for ValkeyStorageBackend.

Uses deterministic fixed vectors — no LLM, no Ollama, no embedder required.
Requires only Valkey running on localhost:6379 with the search module.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np
import pytest

from crewai.memory.types import MemoryRecord, ScopeInfo
from valkey_storage import ValkeyStorageBackend


EMBEDDING_DIM = 4
TEST_INDEX = "test_crewai_storage_idx"
TEST_PREFIX = "test_crewai:mem:"


def make_vector(seed: int) -> list[float]:
    """Create a deterministic normalized vector."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def similar_vector(base: list[float], noise_scale: float = 0.01) -> list[float]:
    """Create a vector similar to base with small deterministic noise."""
    rng = np.random.default_rng(99)
    arr = np.array(base, dtype=np.float32)
    noise = rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * noise_scale
    result = arr + noise
    result /= np.linalg.norm(result)
    return result.tolist()


def make_record(
    record_id: str,
    content: str,
    scope: str = "/",
    categories: list[str] | None = None,
    importance: float = 0.5,
    embedding: list[float] | None = None,
) -> MemoryRecord:
    """Create a MemoryRecord with defaults."""
    return MemoryRecord(
        id=record_id,
        content=content,
        scope=scope,
        categories=categories or [],
        metadata={},
        importance=importance,
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        embedding=embedding,
    )


@pytest.fixture(scope="module")
def backend():
    """Create a ValkeyStorageBackend for tests and clean up after."""
    store = ValkeyStorageBackend(
        host="localhost",
        port=6379,
        embedding_dim=EMBEDDING_DIM,
        index_name=TEST_INDEX,
        key_prefix=TEST_PREFIX,
    )
    yield store
    # Cleanup
    store.reset()
    store.close()


def wait_for_indexing(backend: ValkeyStorageBackend, expected: int, timeout: float = 5.0):
    """Poll until the index has at least `expected` documents."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        count = backend.count()
        if count >= expected:
            return
        time.sleep(0.1)
    raise TimeoutError(f"Index did not reach {expected} docs in {timeout}s (got {backend.count()})")


class TestSaveAndRetrieve:
    """Test save, get_record, and count."""

    def test_save_single_record(self, backend: ValkeyStorageBackend):
        backend.reset()
        vec = make_vector(42)
        record = make_record("rec-1", "Test memory content", embedding=vec)
        backend.save([record])
        wait_for_indexing(backend, 1)
        assert backend.count() >= 1

    def test_save_rejects_wrong_embedding_dimension(self, backend: ValkeyStorageBackend):
        """Embedding dimension mismatch must raise ValueError, not silently corrupt."""
        wrong_dim_vec = [0.1] * (EMBEDDING_DIM + 2)  # Wrong dimension
        record = make_record("bad-dim", "Should fail", embedding=wrong_dim_vec)
        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            backend.save([record])

    def test_get_record_by_id(self, backend: ValkeyStorageBackend):
        retrieved = backend.get_record("rec-1")
        assert retrieved is not None
        assert retrieved.id == "rec-1"
        assert retrieved.content == "Test memory content"

    def test_get_nonexistent_record(self, backend: ValkeyStorageBackend):
        result = backend.get_record("nonexistent-id")
        assert result is None

    def test_save_multiple_records(self, backend: ValkeyStorageBackend):
        backend.reset()
        records = [
            make_record(f"batch-{i}", f"Content {i}", embedding=make_vector(i))
            for i in range(3)
        ]
        backend.save(records)
        wait_for_indexing(backend, 3)
        assert backend.count() == 3


class TestSearch:
    """Test vector similarity search."""

    def test_search_finds_similar_vector(self, backend: ValkeyStorageBackend):
        backend.reset()
        base_vec = make_vector(100)
        record = make_record("search-1", "Find me by vector", embedding=base_vec)
        backend.save([record])
        wait_for_indexing(backend, 1)

        query_vec = similar_vector(base_vec)
        results = backend.search(query_vec, limit=1)
        assert len(results) >= 1
        found_record, score = results[0]
        assert found_record.content == "Find me by vector"
        assert score > 0.9  # Very similar

    def test_search_with_scope_filter(self, backend: ValkeyStorageBackend):
        backend.reset()
        vec1 = make_vector(200)
        vec2 = make_vector(201)
        backend.save([
            make_record("scope-a", "In scope A", scope="/project/alpha", embedding=vec1),
            make_record("scope-b", "In scope B", scope="/project/beta", embedding=vec2),
        ])
        wait_for_indexing(backend, 2)

        results = backend.search(
            similar_vector(vec1),
            scope_prefix="/project/alpha",
            limit=5,
        )
        assert len(results) >= 1
        assert all(r.scope == "/project/alpha" for r, _ in results)

    def test_search_with_category_filter(self, backend: ValkeyStorageBackend):
        backend.reset()
        vec1 = make_vector(300)
        vec2 = make_vector(301)
        backend.save([
            make_record("cat-a", "Architecture decision", categories=["architecture"], embedding=vec1),
            make_record("cat-b", "Bug report", categories=["bugs"], embedding=vec2),
        ])
        wait_for_indexing(backend, 2)

        results = backend.search(
            similar_vector(vec1),
            categories=["architecture"],
            limit=5,
        )
        assert len(results) >= 1
        assert all("architecture" in r.categories for r, _ in results)


class TestDelete:
    """Test deletion operations."""

    def test_delete_by_record_id(self, backend: ValkeyStorageBackend):
        backend.reset()
        vec = make_vector(400)
        backend.save([make_record("del-1", "To be deleted", embedding=vec)])
        wait_for_indexing(backend, 1)

        deleted = backend.delete(record_ids=["del-1"])
        assert deleted == 1
        assert backend.get_record("del-1") is None

    def test_delete_by_scope(self, backend: ValkeyStorageBackend):
        backend.reset()
        backend.save([
            make_record("del-s1", "Scope A", scope="/temp", embedding=make_vector(410)),
            make_record("del-s2", "Scope B", scope="/keep", embedding=make_vector(411)),
        ])
        wait_for_indexing(backend, 2)

        deleted = backend.delete(scope_prefix="/temp")
        assert deleted >= 1
        # /keep record should still exist
        time.sleep(0.2)
        assert backend.get_record("del-s2") is not None


class TestScopeOperations:
    """Test scope-related operations."""

    def test_count_with_scope(self, backend: ValkeyStorageBackend):
        backend.reset()
        backend.save([
            make_record("cnt-1", "A", scope="/team/alpha", embedding=make_vector(500)),
            make_record("cnt-2", "B", scope="/team/alpha", embedding=make_vector(501)),
            make_record("cnt-3", "C", scope="/team/beta", embedding=make_vector(502)),
        ])
        wait_for_indexing(backend, 3)

        assert backend.count() == 3
        assert backend.count(scope_prefix="/team/alpha") == 2
        assert backend.count(scope_prefix="/team/beta") == 1

    def test_get_scope_info(self, backend: ValkeyStorageBackend):
        info = backend.get_scope_info("/team/alpha")
        assert isinstance(info, ScopeInfo)
        assert info.path == "/team/alpha"
        assert info.record_count == 2

    def test_list_records(self, backend: ValkeyStorageBackend):
        records = backend.list_records(scope_prefix="/team/alpha")
        assert len(records) == 2
        assert all(r.scope == "/team/alpha" for r in records)


class TestReset:
    """Test reset operation."""

    def test_reset_clears_all(self, backend: ValkeyStorageBackend):
        backend.reset()
        backend.save([
            make_record("reset-1", "Will be gone", embedding=make_vector(600)),
        ])
        wait_for_indexing(backend, 1)
        assert backend.count() >= 1

        backend.reset()
        time.sleep(0.3)
        assert backend.count() == 0
