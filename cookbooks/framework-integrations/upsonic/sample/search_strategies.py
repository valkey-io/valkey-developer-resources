"""
02 - Search Strategies: Dense, full-text, hybrid, and filtered search.

Corresponds to cookbook: 02-search-strategies.md

Requirements:
    - Valkey 8.1+ with valkey-search module loaded
    - pip install -r requirements.txt

Usage:
    docker compose up -d
    python search_strategies.py
"""

from __future__ import annotations

import asyncio

from upsonic.vectordb import ValkeyConfig, ValkeyProvider
from upsonic.vectordb.config import (
    ConnectionConfig,
    DistanceMetric,
    HNSWIndexConfig,
    Mode,
)


async def main() -> None:
    """Demonstrate all search modes."""
    config = ValkeyConfig(
        vector_size=384,
        collection_name="search_demo",
        key_prefix="demo:",
        connection=ConnectionConfig(mode=Mode.LOCAL, host="localhost", port=6379),
        distance_metric=DistanceMetric.COSINE,
        index=HNSWIndexConfig(m=16, ef_construction=200),
    )

    provider = ValkeyProvider(config)
    await provider.aconnect()
    try:
        # Clean slate
        if await provider.acollection_exists():
            await provider.adelete_collection()
        await provider.acreate_collection()

        # Index sample data across two knowledge bases
        await provider.aupsert(
            vectors=[
                [0.1] * 384,
                [0.2] * 384,
                [0.3] * 384,
                [0.4] * 384,
                [0.5] * 384,
            ],
            ids=["c1", "c2", "c3", "c4", "c5"],
            chunks=[
                "Valkey is a high-performance in-memory data store for caching",
                "Vector similarity search finds nearest neighbors in embedding space",
                "HNSW algorithm provides fast approximate nearest neighbor queries",
                "Full-text search matches documents by keyword relevance",
                "Hybrid search combines vector and text for best retrieval quality",
            ],
            document_ids=["doc_1", "doc_1", "doc_2", "doc_2", "doc_3"],
            document_names=[
                "valkey_intro.md",
                "valkey_intro.md",
                "vector_search.md",
                "vector_search.md",
                "hybrid.md",
            ],
            knowledge_base_ids=["kb_infra", "kb_infra", "kb_ml", "kb_ml", "kb_ml"],
        )
        print("Indexed 5 chunks")
        await asyncio.sleep(0.5)

        query_vector = [0.15] * 384

        # --- Dense search ---
        print("\n--- Dense Search (KNN) ---")
        results = await provider.adense_search(query_vector=query_vector, top_k=3)
        for r in results:
            print(f"  [{r.score:.3f}] {r.text[:70]}")

        # --- Full-text search ---
        print("\n--- Full-Text Search ---")
        results = await provider.afull_text_search(query_text="nearest neighbor", top_k=3)
        for r in results:
            print(f"  [{r.score:.3f}] {r.text[:70]}")

        # --- Hybrid search (RRF) ---
        print("\n--- Hybrid Search (RRF) ---")
        results = await provider.ahybrid_search(
            query_vector=query_vector,
            query_text="vector similarity",
            top_k=3,
        )
        for r in results:
            print(f"  [{r.score:.3f}] {r.text[:70]}")

        # --- Filtered search ---
        print("\n--- Filtered Search (document_name=valkey_intro.md) ---")
        results = await provider.adense_search(
            query_vector=query_vector,
            top_k=5,
            filter={"document_name": "valkey_intro.md"},
        )
        for r in results:
            print(f"  [{r.score:.3f}] {r.text[:70]}")

        # --- Filtered by knowledge_base_id ---
        print("\n--- Filtered Search (knowledge_base_id=kb_ml) ---")
        results = await provider.adense_search(
            query_vector=query_vector,
            top_k=5,
            filter={"knowledge_base_id": "kb_ml"},
        )
        for r in results:
            print(f"  [{r.score:.3f}] {r.text[:70]}")

        # Cleanup
        await provider.adelete_collection()
    finally:
        await provider.adisconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
