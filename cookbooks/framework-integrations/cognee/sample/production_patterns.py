"""Cognee + Valkey production patterns — error handling, batch ops, monitoring.

Corresponds to cookbook: 03-production.md
"""

from __future__ import annotations

import asyncio
import logging
import pathlib

from common import configure_ollama_env

configure_ollama_env()

from cognee import SearchType, add, cognify, search  # noqa: E402
from cognee.modules.search.types import SearchResult  # noqa: E402
from cognee_community_vector_adapter_valkey import register  # noqa: E402, F401

from common import bootstrap_cognee  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def safe_add(documents: list[str]) -> int:
    """Add documents with per-document error handling.

    Returns:
        Number of successfully added documents.
    """
    added = 0
    for doc in documents:
        try:
            await add(doc)
            added += 1
        except Exception as e:
            # In production, narrow this to Cognee/Valkey-specific exceptions
            logger.error("Failed to add document: %s", e)
    return added


async def safe_search(query: str) -> list[SearchResult]:
    """Search with fallback from graph to chunks on failure."""
    try:
        return await search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=query,
        )
    except Exception as e:
        logger.warning("Graph search failed, falling back to chunks: %s", e)
        return await search(
            query_type=SearchType.CHUNKS,
            query_text=query,
        )


async def main() -> None:
    await bootstrap_cognee(pathlib.Path(__file__).parent)

    # Batch add with error handling
    documents = [
        "Valkey supports HNSW and FLAT vector indexing algorithms.",
        "HNSW provides approximate nearest neighbor search with tunable recall.",
        "TLS encryption should be enabled for any non-localhost Valkey deployment.",
        "Managed Valkey services like ElastiCache and MemoryDB handle failover automatically.",
    ]

    print(f"Adding {len(documents)} documents with error handling...")
    added = await safe_add(documents)
    print(f"  Successfully added: {added}/{len(documents)}")

    print("Running cognify...")
    try:
        await cognify()
    except Exception as e:
        logger.error("Cognify failed: %s", e)
        return

    # Search with fallback
    queries = [
        "What vector indexing does Valkey support?",
        "How do I connect securely to a production Valkey deployment?",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        results = await safe_search(query)
        for result in results:
            print(f"  Result: {result}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
