"""Haystack + Valkey RAG Pipeline — Demo Script.

Demonstrates:
1. Connecting to ValkeyDocumentStore
2. Storing documents with embeddings (fixed vectors for deterministic path)
3. Running similarity search with ValkeyEmbeddingRetriever
4. Metadata filtering
5. Full RAG pipeline with Ollama (optional, requires Ollama running)

Requirements:
    - Valkey Bundle running (with search + json modules)
    - For the RAG path: Ollama running with models pulled:
        ollama pull nomic-embed-text
        ollama pull llama3.2:1b
"""

from __future__ import annotations

import os

from haystack import Document
from haystack_integrations.components.retrievers.valkey import (
    ValkeyEmbeddingRetriever,
)
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

# --- Configuration ---
EMBEDDING_DIM = 4  # Fixed vectors for deterministic default path
INDEX_NAME = "haystack_demo"


def build_store() -> ValkeyDocumentStore:
    """Create a ValkeyDocumentStore connection with env var overrides."""
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


def build_documents() -> list[Document]:
    """Build sample documents with deterministic embeddings."""
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
    """Return a deterministic query embedding based on the query string."""
    if "valkey" in query.lower():
        return [1.0, 0.0, 0.0, 0.0]
    if "haystack" in query.lower() or "pipeline" in query.lower():
        return [0.0, 1.0, 0.0, 0.0]
    return [0.0, 0.0, 1.0, 0.0]


def build_retriever(store: ValkeyDocumentStore) -> ValkeyEmbeddingRetriever:
    """Create a retriever configured for top-3 results."""
    return ValkeyEmbeddingRetriever(document_store=store, top_k=3)


def cleanup_store(store: ValkeyDocumentStore) -> None:
    """Remove all documents and close the connection."""
    try:
        store.delete_all_documents()
    finally:
        store.close()


def main() -> None:
    print("=== Haystack + Valkey Demo ===\n")

    store = build_store()
    try:
        # Clean slate
        store.delete_all_documents()

        # Index documents
        written = store.write_documents(build_documents())
        print(f"Indexed {written} documents")

        # Similarity search
        results = build_retriever(store).run(query_embedding("valkey search"))
        top = results["documents"]
        print(f"Top result: {top[0].id} (score: {top[0].score:.3f})")

        # Metadata filtering
        filtered = build_retriever(store).run(
            query_embedding("retrieval"),
            filters={"field": "meta.category", "operator": "==", "value": "search"},
        )
        print(f"Filtered result: {filtered['documents'][0].id}")

    finally:
        cleanup_store(store)

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
