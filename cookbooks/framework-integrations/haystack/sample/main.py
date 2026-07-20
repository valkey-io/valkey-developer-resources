"""Deterministic Haystack + Valkey vector retrieval sample."""

from __future__ import annotations

import os

from haystack import Document
from haystack_integrations.components.retrievers.valkey import (
    ValkeyEmbeddingRetriever,
)
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

EMBEDDING_DIM = 4
INDEX_NAME = "haystack_sample"


def build_documents() -> list[Document]:
    return [
        Document(
            id="valkey-search",
            content="Valkey Search stores and retrieves documents by vector similarity.",
            embedding=[1.0, 0.0, 0.0, 0.0],
            meta={"category": "search"},
        ),
        Document(
            id="haystack-pipeline",
            content="Haystack connects document stores, embedders, and retrievers into pipelines.",
            embedding=[0.0, 1.0, 0.0, 0.0],
            meta={"category": "framework"},
        ),
        Document(
            id="rag-context",
            content="RAG retrieves relevant context before an answer is generated.",
            embedding=[0.0, 0.0, 1.0, 0.0],
            meta={"category": "rag"},
        ),
    ]


def query_embedding(query: str) -> list[float]:
    if query == "valkey search":
        return [1.0, 0.0, 0.0, 0.0]
    return [0.0, 0.0, 1.0, 0.0]


def build_store() -> ValkeyDocumentStore:
    return ValkeyDocumentStore(
        nodes_list=[
            (
                os.getenv("VALKEY_HOST", "localhost"),
                int(os.getenv("VALKEY_PORT", "6379")),
            )
        ],
        index_name=INDEX_NAME,
        embedding_dim=EMBEDDING_DIM,
        distance_metric="cosine",
        metadata_fields={"category": str},
        request_timeout=int(os.getenv("VALKEY_REQUEST_TIMEOUT_MS", "5000")),
    )


def build_retriever(store: ValkeyDocumentStore) -> ValkeyEmbeddingRetriever:
    return ValkeyEmbeddingRetriever(document_store=store, top_k=3)


def cleanup_store(store: ValkeyDocumentStore) -> None:
    try:
        store.delete_all_documents()
    finally:
        store.close()


def main() -> None:
    store = build_store()
    try:
        store.delete_all_documents()
        written = store.write_documents(build_documents())
        assert written == 3
        print(f"Indexed {written} documents")

        top = build_retriever(store).run(query_embedding("valkey search"))["documents"]
        assert top and top[0].id == "valkey-search"
        print(f"Top result: {top[0].id}")

        filtered = build_retriever(store).run(
            query_embedding("retrieval"),
            filters={"field": "meta.category", "operator": "==", "value": "search"},
        )["documents"]
        assert [doc.id for doc in filtered] == ["valkey-search"]
        print(f"Filtered result: {filtered[0].id}")
    finally:
        cleanup_store(store)

    print("Sample completed successfully")


if __name__ == "__main__":
    main()
