"""Integration tests for the Haystack + Valkey local semantic-search sample.

The public all-MiniLM-L6-v2 model is downloaded on a cold cache. Tests require
Valkey Bundle with the Valkey-Search and Valkey JSON modules running locally.
"""

from unittest.mock import patch

import pytest

from main import (
    EMBEDDING_DIM,
    build_documents,
    build_retriever,
    build_store,
    cleanup_store,
    embed_documents,
    embed_query,
)


@pytest.fixture(scope="session")
def embedded_documents():
    """Create reusable real FLOAT32 embeddings for the integration tests."""
    documents = embed_documents(build_documents())
    assert all(len(document.embedding) == EMBEDDING_DIM for document in documents)
    return documents


@pytest.fixture
def document_store():
    """Provide a clean store and close its connection after each test."""
    store = build_store()
    try:
        store.delete_all_documents()
        yield store
    finally:
        cleanup_store(store)


def test_semantic_retrieval_embeds_documents_and_query(document_store, embedded_documents):
    """A natural-language query retrieves the relevant Valkey-Search document."""
    assert document_store.write_documents(embedded_documents) == 3

    result = build_retriever(document_store).run(
        query_embedding=embed_query("Which Valkey feature supports semantic document search?")
    )

    assert result["documents"]
    assert result["documents"][0].id == "valkey-search"


def test_semantic_retrieval_applies_metadata_filters(document_store, embedded_documents):
    """Metadata filtering limits results after the same real embedding path."""
    document_store.write_documents(embedded_documents)

    result = build_retriever(document_store).run(
        query_embedding=embed_query("Which Valkey feature supports semantic document search?"),
        filters={"field": "meta.category", "operator": "==", "value": "search"},
    )

    assert result["documents"]
    assert {document.meta["category"] for document in result["documents"]} == {"search"}
    assert result["documents"][0].id == "valkey-search"


def test_build_store_uses_environment_overrides(monkeypatch):
    """Environment variables override the Valkey connection configuration."""
    monkeypatch.setenv("VALKEY_HOST", "valkey.example")
    monkeypatch.setenv("VALKEY_PORT", "6380")
    monkeypatch.setenv("VALKEY_REQUEST_TIMEOUT_MS", "2500")

    with patch("main.ValkeyDocumentStore") as mock_store:
        build_store()

    mock_store.assert_called_once_with(
        nodes_list=[("valkey.example", 6380)],
        index_name="haystack_demo",
        embedding_dim=EMBEDDING_DIM,
        distance_metric="cosine",
        metadata_fields={"category": str},
        request_timeout=2500,
    )


def test_cleanup_closes_store_when_deletion_fails():
    """Store cleanup closes the connection even when deletion raises."""

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
