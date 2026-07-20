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


def test_haystack_retriever_returns_the_closest_document():
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


def test_build_store_uses_environment_overrides(monkeypatch):
    monkeypatch.setenv("VALKEY_HOST", "valkey.example")
    monkeypatch.setenv("VALKEY_PORT", "6380")
    monkeypatch.setenv("VALKEY_REQUEST_TIMEOUT_MS", "2500")

    with patch("main.ValkeyDocumentStore") as document_store:
        build_store()

    document_store.assert_called_once_with(
        nodes_list=[("valkey.example", 6380)],
        index_name="haystack_sample",
        embedding_dim=4,
        distance_metric="cosine",
        metadata_fields={"category": str},
        request_timeout=2500,
    )


def test_cleanup_closes_store_when_index_deletion_fails():
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


def test_haystack_retriever_applies_metadata_filters():
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
