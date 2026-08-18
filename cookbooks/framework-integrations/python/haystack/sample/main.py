"""Haystack + Valkey semantic-search demo using local embeddings.

Requires Valkey Bundle with the Valkey-Search and Valkey JSON modules.
"""

from __future__ import annotations

import os

from haystack import Document
from haystack.components.embedders import (
    SentenceTransformersDocumentEmbedder,
    SentenceTransformersTextEmbedder,
)
from haystack_integrations.components.retrievers.valkey import (
    ValkeyEmbeddingRetriever,
)
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
INDEX_NAME = "haystack_demo"


def build_store() -> ValkeyDocumentStore:
    """Create a ValkeyDocumentStore connection with environment overrides."""
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
    """Build the unembedded documents used by the demo."""
    return [
        Document(
            id="valkey-search",
            content=(
                "Valkey-Search creates vector indexes so applications can retrieve "
                "semantically similar documents."
            ),
            meta={"category": "search"},
        ),
        Document(
            id="haystack-pipeline",
            content=(
                "Haystack connects document stores, embedders, retrievers, and "
                "generators into RAG pipelines."
            ),
            meta={"category": "framework"},
        ),
        Document(
            id="rag-context",
            content=(
                "Retrieval-augmented generation supplies relevant context to an "
                "LLM before it produces an answer."
            ),
            meta={"category": "rag"},
        ),
    ]


def embed_documents(documents: list[Document]) -> list[Document]:
    """Embed documents with the local FLOAT32 model used for queries."""
    embedder = SentenceTransformersDocumentEmbedder(
        model=EMBEDDING_MODEL,
        progress_bar=False,
        precision="float32",
    )
    embedder.warm_up()
    return embedder.run(documents=documents)["documents"]


def embed_query(query: str) -> list[float]:
    """Embed a query with the same local model and FLOAT32 configuration."""
    embedder = SentenceTransformersTextEmbedder(
        model=EMBEDDING_MODEL,
        progress_bar=False,
        precision="float32",
    )
    embedder.warm_up()
    return embedder.run(text=query)["embedding"]


def build_retriever(valkey_store: ValkeyDocumentStore) -> ValkeyEmbeddingRetriever:
    """Create a retriever configured for the demo result count."""
    return ValkeyEmbeddingRetriever(document_store=valkey_store, top_k=3)


def cleanup_store(valkey_store: ValkeyDocumentStore) -> None:
    """Remove demo documents and always close the GLIDE connection."""
    try:
        valkey_store.delete_all_documents()
    finally:
        valkey_store.close()


def main() -> None:
    """Embed, store, retrieve, and clean up the sample documents."""
    print("=== Haystack + Valkey Demo ===\n")
    valkey_store = build_store()
    try:
        valkey_store.delete_all_documents()
        written = valkey_store.write_documents(embed_documents(build_documents()))
        print(f"Indexed {written} documents")

        results = build_retriever(valkey_store).run(
            query_embedding=embed_query("How can I search documents by meaning in Valkey?")
        )
        top = results["documents"]
        print(f"Top result: {top[0].id}")

        filtered = build_retriever(valkey_store).run(
            query_embedding=embed_query("How can I search documents by meaning in Valkey?"),
            filters={"field": "meta.category", "operator": "==", "value": "search"},
        )
        print(f"Filtered result: {filtered['documents'][0].id}")
    finally:
        cleanup_store(valkey_store)

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
