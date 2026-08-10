"""Tests for the standalone ValkeyVectorStore sample.

Requires a running Valkey with the Search + JSON modules:

    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    pytest test_valkey_vector_store.py -v
"""

from __future__ import annotations

import os
import time

import pytest
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import VectorStoreQuery

from valkey_vector_store import ValkeyVectorStore

EMBED_DIM = 4

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


def unique_store(**overrides) -> ValkeyVectorStore:
    """A ValkeyVectorStore with a unique index/prefix per test."""
    suffix = str(time.time_ns())
    defaults = dict(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        index_name=f"test_idx_{suffix}",
        prefix=f"test:{suffix}:",
        vector_dimensions=EMBED_DIM,
        distance_metric="COSINE",
        vector_algorithm="HNSW",
    )
    defaults.update(overrides)
    return ValkeyVectorStore(**defaults)


@pytest.fixture
def store():
    """A ValkeyVectorStore instance with a unique index/prefix, torn down after."""
    s = unique_store()
    try:
        yield s
    finally:
        # Best-effort cleanup even if a test failed mid-way.
        try:
            s.drop_index()
        finally:
            s.disconnect()


def make_node(node_id: str, text: str, vector: list[float], ref_doc_id: str | None = None) -> TextNode:
    kwargs = {"id_": node_id, "text": text, "embedding": vector}
    node = TextNode(**kwargs)
    if ref_doc_id is not None:
        # Set a source-node relationship so node.ref_doc_id resolves to
        # ref_doc_id, matching how llama-index chunks a document into nodes.
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo

        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=ref_doc_id)
    return node


# --------------------------------------------------------------------------- #
# Index lifecycle
# --------------------------------------------------------------------------- #
def test_ensure_index_creates_index_and_is_idempotent(store):
    store.ensure_index()
    assert store._index_exists()

    # Calling it again must not raise or recreate the index.
    store.ensure_index()
    assert store._index_exists()


def test_drop_index_is_safe_on_first_run_before_any_index_exists():
    """drop_index() must no-op cleanly when there is nothing to drop yet."""
    s = unique_store()
    try:
        s.drop_index()  # must not raise even though the index never existed
        assert s.scan_all_docs() == []
    finally:
        s.disconnect()


# --------------------------------------------------------------------------- #
# Add (atomic batch write)
# --------------------------------------------------------------------------- #
def test_add_stores_atomic_batch_and_returns_ids(store):
    nodes = [
        make_node("doc1", "Valkey supports HNSW and FLAT vector indexes.", [1.0, 0.0, 0.0, 0.0]),
        make_node("doc2", "FT.SEARCH runs KNN similarity queries.", [0.9, 0.1, 0.0, 0.0]),
        make_node("doc3", "Unrelated content about the weather.", [0.0, 0.0, 1.0, 1.0]),
    ]
    ids = store.add(nodes)
    assert ids == ["doc1", "doc2", "doc3"]

    stored_keys = store.scan_all_docs()
    assert len(stored_keys) == 3
    assert all(k.startswith(store.prefix) for k in stored_keys)


def test_add_defaults_ref_doc_id_to_doc_id_when_unset(store):
    """Nodes with no explicit source relationship fall back to ref_doc_id == doc_id."""
    node = make_node("solo_doc", "standalone node with no ref_doc_id set", [1.0, 0.0, 0.0, 0.0])
    assert node.ref_doc_id is None
    store.add([node])

    # delete() matches on ref_doc_id OR doc_id, so passing the node's own id
    # must remove it because add() stored ref_doc_id = doc_id as a fallback.
    store.delete("solo_doc")
    assert store.scan_all_docs() == []


# --------------------------------------------------------------------------- #
# KNN query
# --------------------------------------------------------------------------- #
def test_query_returns_knn_results_ranked_by_similarity(store):
    nodes = [
        make_node("doc1", "closest match", [1.0, 0.0, 0.0, 0.0]),
        make_node("doc2", "second closest", [0.9, 0.1, 0.0, 0.0]),
        make_node("doc3", "far away", [0.0, 0.0, 1.0, 1.0]),
    ]
    store.add(nodes)

    result = store.query(VectorStoreQuery(query_embedding=[1.0, 0.0, 0.0, 0.0], similarity_top_k=2))
    assert len(result.nodes) == 2
    assert result.ids[0] == "doc1"
    assert result.similarities[0] >= result.similarities[1]


def test_query_dimension_mismatch_raises_value_error(store):
    """A query embedding of the wrong length must fail loudly, not silently truncate."""
    store.ensure_index()
    with pytest.raises(ValueError, match="does not match"):
        store.query(VectorStoreQuery(query_embedding=[1.0, 0.0], similarity_top_k=1))


# --------------------------------------------------------------------------- #
# Delete by ref_doc_id
# --------------------------------------------------------------------------- #
def test_delete_removes_all_chunks_by_ref_doc_id(store):
    nodes = [
        make_node("chunk_a", "first chunk of source doc", [1.0, 0.0, 0.0, 0.0], ref_doc_id="source_doc"),
        make_node("chunk_b", "second chunk of source doc", [0.9, 0.1, 0.0, 0.0], ref_doc_id="source_doc"),
        make_node("chunk_c", "unrelated chunk", [0.0, 1.0, 0.0, 0.0], ref_doc_id="other_doc"),
    ]
    store.add(nodes)
    assert len(store.scan_all_docs()) == 3

    store.delete("source_doc")

    remaining = store.scan_all_docs()
    assert len(remaining) == 1
    assert remaining[0] == f"{store.prefix}chunk_c"


# --------------------------------------------------------------------------- #
# drop_index cleanup
# --------------------------------------------------------------------------- #
def test_drop_index_removes_index_and_orphaned_keys(store):
    node = make_node("doc1", "will be cleaned up", [1.0, 0.0, 0.0, 0.0])
    store.add([node])
    assert store._index_exists()
    assert len(store.scan_all_docs()) == 1

    store.drop_index()

    assert not store._index_exists()
    assert store.scan_all_docs() == []


# --------------------------------------------------------------------------- #
# Connection lifecycle
# --------------------------------------------------------------------------- #
def test_check_connection_returns_true_when_reachable(store):
    assert store.check_connection() is True


def test_check_connection_returns_false_for_glide_request_error(store):
    """Generic GLIDE request failures must be reported as a failed check."""

    class FailingClient:
        def ping(self):
            from glide_sync import RequestError

            raise RequestError("authentication failed")

        def close(self):
            pass

    store._client = FailingClient()

    assert store.check_connection() is False
    assert store.client is None


def test_disconnect_is_safe_to_call_twice(store):
    store.ensure_index()
    store.disconnect()
    store.disconnect()  # must not raise on a second close
