"""Tests for Haystack + Valkey integration.

Requires:
    - Valkey Bundle running on localhost:6379 (with search + json modules)

Tests use Haystack's built-in MockDocumentEmbedder and MockTextEmbedder
to generate deterministic embeddings without requiring Ollama. This validates
the Haystack ↔ ValkeyDocumentStore pipeline (write, retrieve, count, delete)
independently of the embedding provider.
"""

import pytest
from haystack import Document, Pipeline
from haystack.components.embedders import MockDocumentEmbedder, MockTextEmbedder
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
# MockDocumentEmbedder defaults to 768-dim; using 384 for a smaller test footprint
EMBEDDING_DIM = 384
INDEX_NAME = "test_haystack_idx"


@pytest.fixture(scope="module")
def document_store():
    """Create a ValkeyDocumentStore for testing and clean up after."""
    store = ValkeyDocumentStore(
        nodes_list=[(VALKEY_HOST, VALKEY_PORT)],
        index_name=INDEX_NAME,
        embedding_dim=EMBEDDING_DIM,
        distance_metric="cosine",
    )
    yield store
    # Cleanup: delete all documents in the test index
    store.delete_documents(store.filter_documents())


class TestDocumentStore:
    """Test basic ValkeyDocumentStore operations."""

    def test_connection(self, document_store):
        """ValkeyDocumentStore connects and responds to count."""
        count = document_store.count_documents()
        assert isinstance(count, int)

    def test_write_and_count(self, document_store):
        """Write documents with embeddings and verify count increases."""
        docs = [
            Document(content="Valkey is a high-performance data store."),
            Document(content="Haystack builds RAG pipelines."),
            Document(content="Vector search enables semantic matching."),
        ]

        # Use mock embedder for deterministic embeddings
        pipeline = Pipeline()
        pipeline.add_component("embedder", MockDocumentEmbedder(dimension=EMBEDDING_DIM))
        pipeline.add_component("writer", DocumentWriter(document_store=document_store))
        pipeline.connect("embedder.documents", "writer.documents")

        pipeline.run({"embedder": {"documents": docs}})
        assert document_store.count_documents() >= 3


class TestRetrieval:
    """Test embedding-based retrieval from ValkeyDocumentStore."""

    @pytest.fixture(autouse=True)
    def setup(self, document_store):
        """Ensure documents are indexed before retrieval tests."""
        self.store = document_store
        # Write docs if not already present
        if document_store.count_documents() < 3:
            docs = [
                Document(content="Valkey is a high-performance data store."),
                Document(content="Haystack builds RAG pipelines."),
                Document(content="Vector search enables semantic matching."),
            ]
            pipeline = Pipeline()
            pipeline.add_component(
                "embedder", MockDocumentEmbedder(dimension=EMBEDDING_DIM)
            )
            pipeline.add_component("writer", DocumentWriter(document_store=document_store))
            pipeline.connect("embedder.documents", "writer.documents")
            pipeline.run({"embedder": {"documents": docs}})

    def test_retriever_returns_documents(self):
        """ValkeyEmbeddingRetriever returns documents for a query embedding."""
        pipeline = Pipeline()
        pipeline.add_component(
            "embedder", MockTextEmbedder(dimension=EMBEDDING_DIM)
        )
        pipeline.add_component(
            "retriever",
            ValkeyEmbeddingRetriever(document_store=self.store, top_k=2),
        )
        pipeline.connect("embedder.embedding", "retriever.query_embedding")

        result = pipeline.run({"embedder": {"text": "What is Valkey?"}})
        docs = result["retriever"]["documents"]

        assert len(docs) > 0
        assert all(hasattr(doc, "content") for doc in docs)
        assert all(hasattr(doc, "score") for doc in docs)

    def test_retriever_respects_top_k(self):
        """Retriever returns at most top_k documents."""
        pipeline = Pipeline()
        pipeline.add_component(
            "embedder", MockTextEmbedder(dimension=EMBEDDING_DIM)
        )
        pipeline.add_component(
            "retriever",
            ValkeyEmbeddingRetriever(document_store=self.store, top_k=1),
        )
        pipeline.connect("embedder.embedding", "retriever.query_embedding")

        result = pipeline.run({"embedder": {"text": "data store"}})
        docs = result["retriever"]["documents"]

        assert len(docs) <= 1
