"""Tests for Haystack + Valkey integration.

Requires:
    - Valkey Bundle running (with search + json modules)

Tests use fixed 4-dimensional vectors for deterministic results.
No Ollama, no model downloads, no API keys needed.
"""

from unittest.mock import patch

import pytest

from main import (
    EMBEDDING_DIM,
    build_documents,
    build_retriever,
    build_store,
    cleanup_store,
    query_embedding,
)


def test_retriever_returns_closest_document():
    """Write documents and verify KNN retrieval returns the best match."""
    store = build_store()
    try:
        store.delete_all_documents()
        written = store.write_documents(build_documents())
        assert written == 3

        result = build_retriever(store).run(query_embedding("valkey search"))
        documents = result["documents"]

        assert documents
        assert documents[0].id == "valkey-search"
        assert len(documents[0].embedding) == EMBEDDING_DIM
    finally:
        cleanup_store(store)


def test_retriever_applies_metadata_filters():
    """Metadata filters narrow results to matching documents only."""
    store = build_store()
    try:
        store.delete_all_documents()
        store.write_documents(build_documents())

        result = build_retriever(store).run(
            query_embedding("retrieval"),
            filters={
                "field": "meta.category",
                "operator": "==",
                "value": "search",
            },
        )

        assert [doc.id for doc in result["documents"]] == ["valkey-search"]
    finally:
        cleanup_store(store)


def test_build_store_uses_environment_overrides(monkeypatch):
    """Environment variables override connection parameters."""
    monkeypatch.setenv("VALKEY_HOST", "valkey.example")
    monkeypatch.setenv("VALKEY_PORT", "6380")
    monkeypatch.setenv("VALKEY_REQUEST_TIMEOUT_MS", "2500")

    with patch("main.ValkeyDocumentStore") as mock_store:
        build_store()

    mock_store.assert_called_once_with(
        nodes_list=[("valkey.example", 6380)],
        index_name="haystack_demo",
        embedding_dim=4,
        distance_metric="cosine",
        metadata_fields={"category": str},
        request_timeout=2500,
    )


def test_cleanup_closes_store_when_deletion_fails():
    """Store.close() is called even if delete_all_documents() raises."""

    class FailingStore:
        def __init__(self):
            self.closed = False

        def delete_all_documents(self):
            raise RuntimeError("delete failed")

        def close(self):
            self.closed = True

    store = FailingStore()
    with pytest.raises(RuntimeError, match="delete failed"):
        cleanup_store(store)
    assert store.closed
