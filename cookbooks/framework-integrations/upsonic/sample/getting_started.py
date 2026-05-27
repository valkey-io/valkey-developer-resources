"""
01 - Getting Started: Connect, index, and search with Upsonic + Valkey.

Corresponds to cookbook: 01-getting-started.md

Requirements:
    - Valkey 9.1+ with valkey-search module loaded
    - pip install -r requirements.txt

Usage:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9.1
    python getting_started.py
"""

from __future__ import annotations

import asyncio

from upsonic.vectordb import ValkeyConfig, ValkeyProvider
from upsonic.vectordb.config import ConnectionConfig, DistanceMetric, Mode


async def main() -> None:
    """Index documents and run a dense vector search."""
    config = ValkeyConfig(
        vector_size=384,
        collection_name="getting_started",
        key_prefix="doc:",
        connection=ConnectionConfig(mode=Mode.LOCAL, host="localhost", port=6379),
        distance_metric=DistanceMetric.COSINE,
    )

    provider = ValkeyProvider(config)
    await provider.aconnect()
    try:
        # Clean slate
        if await provider.acollection_exists():
            await provider.adelete_collection()
        await provider.acreate_collection()

        # Upsert sample documents
        await provider.aupsert(
            vectors=[
                [0.1] * 384,
                [0.2] * 384,
                [0.3] * 384,
            ],
            ids=["chunk_1", "chunk_2", "chunk_3"],
            chunks=[
                "Valkey is a high-performance in-memory data store",
                "Vector search enables semantic similarity matching",
                "HNSW provides fast approximate nearest neighbor search",
            ],
            document_ids=["doc_1", "doc_1", "doc_2"],
            document_names=["valkey_intro.md", "valkey_intro.md", "vector_search.md"],
        )
        print("Indexed 3 chunks")

        # Valkey Search indexes asynchronously; brief pause ensures results are searchable
        await asyncio.sleep(0.5)

        # Dense search
        query_vector = [0.15] * 384
        results = await provider.adense_search(query_vector=query_vector, top_k=2)

        print("\nDense search results:")
        for r in results:
            print(f"  [{r.score:.3f}] {r.id}: {r.text}")

        # Cleanup
        await provider.adelete_collection()
    finally:
        await provider.adisconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
