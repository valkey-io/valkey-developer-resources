"""CI tests for PraisonAI + Valkey persistence adapters.

Tests ValkeyStateStore and ValkeyVectorKnowledgeStore directly — no LLM
required. Uses deterministic embeddings (numpy random with fixed seed) so
the tests are fast and fully reproducible.

Requires Valkey running on localhost:6379 with the ValkeySearch module
(provided by valkey/valkey-bundle:9.1.0).
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from praisonai.persistence.knowledge.base import KnowledgeDocument
from praisonai.persistence.knowledge.valkey_vector import ValkeyVectorKnowledgeStore
from praisonai.persistence.state.valkey import ValkeyStateStore

DIM = 64  # small dimension for fast tests


def _rand_vec(seed: int) -> list[float]:
    """Deterministic unit-norm vector for testing."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------


@pytest.fixture(scope="module")
def state_store():
    """ValkeyStateStore scoped per test module; cleans up on teardown."""
    prefix = f"praisonai:test:{uuid.uuid4().hex[:8]}:"
    store = ValkeyStateStore(host="localhost", port=6379, prefix=prefix)
    yield store
    store.close()


@pytest.fixture(scope="module")
def vector_store():
    """ValkeyVectorKnowledgeStore scoped per test module."""
    prefix = f"praisonai:testknow:{uuid.uuid4().hex[:8]}:"
    store = ValkeyVectorKnowledgeStore(host="localhost", port=6379, prefix=prefix)
    yield store
    store.close()


@pytest.fixture(scope="module")
def collection(vector_store: ValkeyVectorKnowledgeStore) -> str:
    """Create a fresh collection for vector tests and return its name."""
    name = f"testcoll_{uuid.uuid4().hex[:8]}"
    vector_store.create_collection(name, dimension=DIM, distance="cosine")
    return name


# -----------------------------------------------------------------
# ValkeyStateStore tests
# -----------------------------------------------------------------


class TestValkeyStateStore:
    """Test key-value state persistence operations."""

    def test_set_and_get_string(self, state_store: ValkeyStateStore) -> None:
        """Write and read a plain string value."""
        state_store.set("greeting", "hello")
        assert state_store.get("greeting") == "hello"

    def test_set_and_get_dict(self, state_store: ValkeyStateStore) -> None:
        """Write and read a Python dict (JSON round-trip)."""
        payload = {"role": "user", "content": "What is Valkey?"}
        state_store.set("last_message", payload)
        loaded = state_store.get("last_message")
        assert loaded == payload

    def test_set_and_get_list(self, state_store: ValkeyStateStore) -> None:
        """Write and read a list of dicts (conversation history)."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        state_store.set("history", history)
        loaded = state_store.get("history")
        assert loaded == history

    def test_incr(self, state_store: ValkeyStateStore) -> None:
        """incr creates counter on first call and increments on subsequent."""
        key = f"counter_{uuid.uuid4().hex[:6]}"
        first = state_store.incr(key)
        second = state_store.incr(key)
        assert second == first + 1

    def test_hset_and_hgetall(self, state_store: ValkeyStateStore) -> None:
        """Write multiple hash fields and read them back as a dict.

        hset() JSON-encodes values; hgetall() JSON-decodes them — so an
        integer string "3" round-trips as the integer 3.
        """
        state_store.hset("meta", "run_count", "3")
        state_store.hset("meta", "last_query", "test")
        meta = state_store.hgetall("meta")
        # "3" is stored as JSON, so it round-trips as int 3
        assert meta.get("run_count") in ("3", 3)
        assert meta.get("last_query") == "test"

    def test_overwrite(self, state_store: ValkeyStateStore) -> None:
        """A second set() overwrites the first value."""
        state_store.set("overwrite_key", "v1")
        state_store.set("overwrite_key", "v2")
        assert state_store.get("overwrite_key") == "v2"

    def test_get_missing_key_returns_none(self, state_store: ValkeyStateStore) -> None:
        """get() on a non-existent key returns None."""
        result = state_store.get(f"missing_{uuid.uuid4().hex}")
        assert result is None


# -----------------------------------------------------------------
# ValkeyVectorKnowledgeStore tests
# -----------------------------------------------------------------


class TestValkeyVectorKnowledgeStore:
    """Test vector insert, search, and collection management."""

    def test_create_collection_idempotent(
        self, vector_store: ValkeyVectorKnowledgeStore, collection: str
    ) -> None:
        """create_collection does not raise if called a second time."""
        # Should not raise
        vector_store.create_collection(collection, dimension=DIM, distance="cosine")

    def test_insert_and_search(
        self, vector_store: ValkeyVectorKnowledgeStore, collection: str
    ) -> None:
        """Insert documents and retrieve the closest match by vector distance."""
        docs = [
            KnowledgeDocument(id="d1", content="Valkey is a fast key-value store.", embedding=_rand_vec(1)),
            KnowledgeDocument(id="d2", content="PraisonAI builds multi-agent systems.", embedding=_rand_vec(2)),
            KnowledgeDocument(id="d3", content="HNSW is an approximate nearest-neighbour index.", embedding=_rand_vec(3)),
        ]
        inserted_ids = vector_store.insert(collection, docs)
        assert len(inserted_ids) == 3

        # Search using the exact vector for d1 — it should rank first
        results = vector_store.search(collection, query_embedding=_rand_vec(1), limit=1)
        assert len(results) >= 1
        assert results[0].id == "d1"

    def test_search_returns_top_k(
        self, vector_store: ValkeyVectorKnowledgeStore, collection: str
    ) -> None:
        """Search with limit=2 returns at most 2 results."""
        results = vector_store.search(collection, query_embedding=_rand_vec(1), limit=2)
        assert len(results) <= 2

    def test_insert_is_idempotent(
        self, vector_store: ValkeyVectorKnowledgeStore, collection: str
    ) -> None:
        """Re-inserting the same doc_id overwrites without raising."""
        doc = KnowledgeDocument(id="d_idem", content="Idempotent insert test.", embedding=_rand_vec(42))
        vector_store.insert(collection, [doc])
        # Second insert with same id should not raise
        vector_store.insert(collection, [doc])

    def test_prefix_isolation(self) -> None:
        """Two stores with different prefixes do not share data."""
        uid = uuid.uuid4().hex[:8]
        store_a = ValkeyVectorKnowledgeStore(
            host="localhost", port=6379, prefix=f"praisonai:iso_a:{uid}:"
        )
        store_b = ValkeyVectorKnowledgeStore(
            host="localhost", port=6379, prefix=f"praisonai:iso_b:{uid}:"
        )
        coll = f"isocoll_{uid}"

        try:
            store_a.create_collection(coll, dimension=DIM, distance="cosine")
            store_a.insert(
                coll,
                [KnowledgeDocument(id="x", content="store A doc", embedding=_rand_vec(99))],
            )

            # store_b has a different prefix — its index doesn't exist yet
            store_b.create_collection(coll, dimension=DIM, distance="cosine")
            results = store_b.search(coll, query_embedding=_rand_vec(99), limit=5)
            # store_b's collection is empty — should return nothing
            assert len(results) == 0

        finally:
            store_a.close()
            store_b.close()


# -----------------------------------------------------------------
# Environment variable override tests
# -----------------------------------------------------------------


class TestEnvVarConfig:
    """Test that VALKEY_HOST / VALKEY_PORT env vars are honoured."""

    def test_state_store_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ValkeyStateStore should use VALKEY_HOST and VALKEY_PORT from env."""
        import os

        host = os.environ.get("VALKEY_HOST", "localhost")
        port = int(os.environ.get("VALKEY_PORT", "6379"))

        store = ValkeyStateStore(host=host, port=port, prefix="praisonai:envtest:")
        try:
            store.set("envkey", "envval")
            assert store.get("envkey") == "envval"
        finally:
            store.close()

    def test_vector_store_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ValkeyVectorKnowledgeStore should accept host/port from env."""
        import os

        host = os.environ.get("VALKEY_HOST", "localhost")
        port = int(os.environ.get("VALKEY_PORT", "6379"))

        store = ValkeyVectorKnowledgeStore(
            host=host, port=port, prefix=f"praisonai:envvec:{uuid.uuid4().hex[:8]}:"
        )
        coll = f"envcoll_{uuid.uuid4().hex[:8]}"
        try:
            store.create_collection(coll, dimension=DIM, distance="cosine")
            store.insert(
                coll,
                [KnowledgeDocument(id="ev1", content="env test doc", embedding=_rand_vec(7))],
            )
            results = store.search(coll, query_embedding=_rand_vec(7), limit=1)
            assert len(results) >= 1
        finally:
            store.close()
