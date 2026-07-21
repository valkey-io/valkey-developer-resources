"""Haystack + Valkey RAG Pipeline — Demo Script.

Demonstrates:
1. Connecting to ValkeyDocumentStore
2. Embedding and storing documents with Ollama
3. Running similarity search
4. Full RAG pipeline with local LLM

Requirements:
    - Valkey Bundle running on localhost:6379 (with search + json modules)
    - Ollama running with models pulled:
        ollama pull nomic-embed-text
        ollama pull llama3.2:1b
"""

from haystack import Document, Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.writers import DocumentWriter
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.embedders.ollama import (
    OllamaDocumentEmbedder,
    OllamaTextEmbedder,
)
from haystack_integrations.components.generators.ollama import OllamaChatGenerator
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore


def create_document_store() -> ValkeyDocumentStore:
    """Create a ValkeyDocumentStore connection."""
    return ValkeyDocumentStore(
        nodes_list=[("localhost", 6379)],
        index_name="haystack_demo",
        embedding_dim=768,
        distance_metric="cosine",
    )


def index_documents(document_store: ValkeyDocumentStore) -> int:
    """Embed and store sample documents."""
    docs = [
        Document(content="Valkey is an open-source, high-performance in-memory data store."),
        Document(content="Valkey supports vector search natively via its search module."),
        Document(content="The ValkeyDocumentStore integrates with Haystack pipelines."),
        Document(content="RAG grounds LLM responses in retrieved facts."),
        Document(content="Cosine similarity measures the angle between embedding vectors."),
    ]

    pipeline = Pipeline()
    pipeline.add_component(
        "embedder", OllamaDocumentEmbedder(model="nomic-embed-text")
    )
    pipeline.add_component("writer", DocumentWriter(document_store=document_store))
    pipeline.connect("embedder.documents", "writer.documents")

    pipeline.run({"embedder": {"documents": docs}})
    return document_store.count_documents()


def search(document_store: ValkeyDocumentStore, query: str, top_k: int = 2) -> list:
    """Run a similarity search."""
    pipeline = Pipeline()
    pipeline.add_component("embedder", OllamaTextEmbedder(model="nomic-embed-text"))
    pipeline.add_component(
        "retriever", ValkeyEmbeddingRetriever(document_store=document_store, top_k=top_k)
    )
    pipeline.connect("embedder.embedding", "retriever.query_embedding")

    result = pipeline.run({"embedder": {"text": query}})
    return result["retriever"]["documents"]


def rag_query(document_store: ValkeyDocumentStore, query: str) -> str:
    """Run a full RAG pipeline with local LLM."""
    prompt_template = [
        ChatMessage.from_system(
            "Answer the question using only the provided context. "
            "If the context doesn't contain the answer, say 'I don't know'."
        ),
        ChatMessage.from_user(
            "Context:\n{% for doc in documents %}{{ doc.content }}\n{% endfor %}\n"
            "Question: {{query}}"
        ),
    ]

    pipeline = Pipeline()
    pipeline.add_component("embedder", OllamaTextEmbedder(model="nomic-embed-text"))
    pipeline.add_component(
        "retriever", ValkeyEmbeddingRetriever(document_store=document_store, top_k=3)
    )
    pipeline.add_component(
        "prompt_builder",
        ChatPromptBuilder(template=prompt_template, required_variables=["query", "documents"]),
    )
    pipeline.add_component("generator", OllamaChatGenerator(model="llama3.2:1b"))

    pipeline.connect("embedder.embedding", "retriever.query_embedding")
    pipeline.connect("retriever.documents", "prompt_builder.documents")
    pipeline.connect("prompt_builder.messages", "generator.messages")

    result = pipeline.run({
        "embedder": {"text": query},
        "prompt_builder": {"query": query},
    })
    return result["generator"]["replies"][0].text


def main():
    print("=== Haystack + Valkey RAG Demo ===\n")

    # 1. Connect
    print("Connecting to ValkeyDocumentStore...")
    store = create_document_store()
    print(f"Connected. Current documents: {store.count_documents()}\n")

    # 2. Index
    print("Indexing documents with Ollama embeddings...")
    count = index_documents(store)
    print(f"Indexed {count} documents.\n")

    # 3. Search
    query = "What is Valkey?"
    print(f'--- Similarity Search: "{query}" ---')
    docs = search(store, query)
    for doc in docs:
        print(f"  Score: {doc.score:.3f} | {doc.content}")
    print()

    # 4. RAG
    rag_question = "How does Valkey integrate with Haystack?"
    print(f'--- RAG Query: "{rag_question}" ---')
    answer = rag_query(store, rag_question)
    print(f"  Answer: {answer}\n")

    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
