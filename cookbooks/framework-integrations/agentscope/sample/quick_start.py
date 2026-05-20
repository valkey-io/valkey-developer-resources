# -*- coding: utf-8 -*-
"""Cookbook 01 - Getting Started with AgentScope + Valkey.

Demonstrates: connecting to Valkey, storing document embeddings,
running vector similarity search, and deleting documents.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    pip install agentscope[valkey]
"""

from __future__ import annotations

import asyncio

from agentscope.message import TextBlock
from agentscope.rag import Document, DocMetadata, ValkeyStore


async def main() -> None:
    """Run the quick start example."""
    print("=== AgentScope + Valkey Quick Start ===\n")

    # 1. Create the store
    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="quickstart_idx",
        prefix="quickstart:doc:",
        dimensions=3,
        distance="COSINE",
    )
    print("Created ValkeyStore (COSINE, 3 dimensions)")

    # 2. Add documents with synthetic embeddings
    documents = [
        Document(
            embedding=[0.1, 0.2, 0.3],
            metadata=DocMetadata(
                content=TextBlock(
                    type="text",
                    text="Valkey is a high-performance key-value store.",
                ),
                doc_id="valkey-intro",
                chunk_id=0,
                total_chunks=3,
            ),
        ),
        Document(
            embedding=[0.9, 0.1, 0.4],
            metadata=DocMetadata(
                content=TextBlock(
                    type="text",
                    text="Vector search finds similar items by embedding distance.",
                ),
                doc_id="valkey-intro",
                chunk_id=1,
                total_chunks=3,
            ),
        ),
        Document(
            embedding=[0.5, 0.5, 0.5],
            metadata=DocMetadata(
                content=TextBlock(
                    type="text",
                    text="HNSW is an algorithm for approximate nearest neighbors.",
                ),
                doc_id="valkey-intro",
                chunk_id=2,
                total_chunks=3,
            ),
        ),
    ]

    await store.add(documents)
    print(f"Stored {len(documents)} documents\n")

    # Wait for indexing
    await asyncio.sleep(0.5)

    # 3. Search by vector similarity
    query_vec = [0.15, 0.25, 0.35]
    print(f"Query vector: {query_vec}")
    print("Results:")

    results = await store.search(
        query_embedding=query_vec,
        limit=3,
        score_threshold=0.5,
    )

    for doc in results:
        print(f"  {doc.score:.4f}: {doc.metadata.content['text']}")

    # 4. Delete by doc_id
    print("\nDeleting doc_id='valkey-intro'...")
    await store.delete(ids="valkey-intro")
    await asyncio.sleep(0.3)

    # Verify deletion
    results = await store.search(query_embedding=query_vec, limit=3)
    print(f"Results after delete: {len(results)} documents")

    # 5. Cleanup
    await store.drop_index()
    await store.close()
    print("\nDone! Cleaned up and closed connection.")


if __name__ == "__main__":
    asyncio.run(main())
