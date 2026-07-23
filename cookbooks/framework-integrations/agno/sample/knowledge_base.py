"""Agno + Valkey: Vector knowledge base demo.

Demonstrates ValkeyDB as a vector store with Ollama embeddings.
Requires Ollama running with nomic-embed-text model pulled.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    ollama pull nomic-embed-text
    pip install "agno[valkey,ollama]==2.8.0"
    python knowledge_base.py
"""

from __future__ import annotations

import asyncio

from agno.knowledge.document.base import Document
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.vectordb.search import SearchType
from agno.vectordb.valkey import ValkeyDB

INDEX_NAME = "agno_knowledge_demo"


async def main() -> None:
    embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768)

    vector_db = ValkeyDB(
        index_name=INDEX_NAME,
        host="localhost",
        port=6379,
        embedder=embedder,
        search_type=SearchType.vector,
    )

    # Clean slate
    try:
        await vector_db.async_drop()
    except Exception:
        pass
    await vector_db.async_create()

    # Insert documents
    documents = [
        Document(name="valkey-intro", content="Valkey is an open-source, high-performance key/value datastore."),
        Document(name="valkey-search", content="The valkey-search module adds full-text and vector search capabilities."),
        Document(name="valkey-license", content="Valkey is BSD-3 licensed under the Linux Foundation."),
        Document(name="valkey-glide", content="GLIDE is the official Valkey client library, available for multiple languages."),
    ]

    for doc in documents:
        await vector_db.async_insert(content_hash=doc.name, documents=[doc])
    print(f"Inserted {len(documents)} documents into ValkeyDB")

    # Vector search
    print("\n--- Vector Search: 'search capabilities' ---")
    results = await vector_db.async_search("What search capabilities does Valkey have?", limit=2)
    for doc in results:
        print(f"  [{doc.name}] {doc.content[:80]}")

    assert len(results) >= 1, "Expected at least 1 search result"

    # Keyword search
    print("\n--- Keyword Search: 'BSD' ---")
    vector_db_kw = ValkeyDB(
        index_name=INDEX_NAME,
        host="localhost",
        port=6379,
        embedder=embedder,
        search_type=SearchType.keyword,
    )
    kw_results = await vector_db_kw.async_search("BSD", limit=2)
    for doc in kw_results:
        print(f"  [{doc.name}] {doc.content[:80]}")

    # Cleanup
    await vector_db.async_drop()
    print("\n✓ All operations successful")


if __name__ == "__main__":
    asyncio.run(main())
