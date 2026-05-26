"""
03 - Production Deployment: Batch ingest, deduplication, and error handling.

Corresponds to cookbook: 03-production-deployment.md

Requirements:
    - Valkey 9.1+ with valkey-search module loaded
    - pip install -r requirements.txt

Usage:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    python production_deployment.py
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from upsonic.vectordb import ValkeyConfig, ValkeyProvider
from upsonic.vectordb.config import (
    ConnectionConfig,
    DistanceMetric,
    HNSWIndexConfig,
    Mode,
)
from upsonic.utils.package.exception import (
    CollectionDoesNotExistError,
    SearchError,
    VectorDBConnectionError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_batch_ingest(provider: ValkeyProvider) -> None:
    """Demonstrate batch upsert with deduplication."""
    print("\n--- Batch Ingest with Deduplication ---")

    chunks = [
        "Valkey supports HNSW and FLAT vector indexing algorithms",
        "HNSW provides approximate nearest neighbor search with tunable recall",
        "ElastiCache for Valkey includes the Search module by default",
        "TLS encryption is mandatory for ElastiCache Serverless",
        # Duplicate of first chunk — should be skipped
        "Valkey supports HNSW and FLAT vector indexing algorithms",
    ]

    ingested = 0
    skipped = 0

    for i, chunk in enumerate(chunks):
        content_hash = hashlib.md5(chunk.encode()).hexdigest()

        if await provider.achunk_content_hash_exists(content_hash):
            skipped += 1
            continue

        await provider.aupsert(
            vectors=[[0.1 * (i + 1)] * 384],
            ids=[f"batch_{i}"],
            chunks=[chunk],
            document_ids=["batch_doc"],
            document_names=["batch_test.md"],
        )
        ingested += 1

    print(f"  Ingested: {ingested}, Skipped (duplicates): {skipped}")


async def demo_error_handling(provider: ValkeyProvider) -> None:
    """Demonstrate error handling patterns."""
    print("\n--- Error Handling ---")

    query_vector = [0.15] * 384

    try:
        results = await provider.adense_search(query_vector=query_vector, top_k=3)
        print(f"  Search returned {len(results)} results")
        for r in results:
            print(f"    [{r.score:.3f}] {r.text[:60]}")
    except VectorDBConnectionError:
        logger.error("Valkey unreachable — check connection")
        raise
    except CollectionDoesNotExistError:
        logger.warning("Index missing — recreating")
        await provider.acreate_collection()
    except SearchError as e:
        logger.error("Search failed: %s", e)


async def demo_delete_operations(provider: ValkeyProvider) -> None:
    """Demonstrate delete by ID and by document name."""
    print("\n--- Delete Operations ---")

    # Delete specific chunks
    await provider.adelete(ids=["batch_0"])
    print("  Deleted batch_0")

    # Delete all chunks from a document
    await provider.adelete_by_document_name(document_name="batch_test.md")
    print("  Deleted all chunks from batch_test.md")


async def main() -> None:
    """Run production pattern demos."""
    config = ValkeyConfig(
        vector_size=384,
        collection_name="prod_demo",
        key_prefix="prod:",
        connection=ConnectionConfig(mode=Mode.LOCAL, host="localhost", port=6379),
        distance_metric=DistanceMetric.COSINE,
        index=HNSWIndexConfig(m=32, ef_construction=300),
        batch_size=200,
    )

    provider = ValkeyProvider(config)
    await provider.aconnect()

    # Clean slate
    if await provider.acollection_exists():
        await provider.adelete_collection()
    await provider.acreate_collection()

    await demo_batch_ingest(provider)
    await asyncio.sleep(0.5)  # Allow index to update
    await demo_error_handling(provider)
    await demo_delete_operations(provider)

    # Final cleanup
    await provider.adelete_collection()
    await provider.adisconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
