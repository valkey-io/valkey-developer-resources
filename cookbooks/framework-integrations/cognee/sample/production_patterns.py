"""Cognee + Valkey production patterns — error handling, batch ops, monitoring.

Corresponds to cookbook: 03-production.md
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
from os import path

# --- Configuration (before cognee imports) ---
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("LLM_PROVIDER", "bedrock")
os.environ.setdefault("LLM_MODEL", "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0")
os.environ.setdefault("EMBEDDING_PROVIDER", "bedrock")
os.environ.setdefault("EMBEDDING_MODEL", "bedrock/amazon.titan-embed-text-v2:0")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "1024")

from cognee import SearchType, add, cognify, config, prune, search  # noqa: E402
from cognee_community_vector_adapter_valkey import register  # noqa: E402, F401

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


async def safe_search(query: str) -> list[str]:
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
    system_path = pathlib.Path(__file__).parent
    config.system_root_directory(path.join(system_path, ".cognee-system"))
    config.data_root_directory(path.join(system_path, ".cognee-data"))

    config.set_vector_db_config({
        "vector_db_provider": "valkey",
        "vector_db_url": os.getenv("VECTOR_DB_URL", "valkey://localhost:6379"),
    })

    print("Pruning existing data...")
    await prune.prune_data()
    await prune.prune_system(metadata=True)

    # Batch add with error handling
    documents = [
        "Valkey supports HNSW and FLAT vector indexing algorithms.",
        "HNSW provides approximate nearest neighbor search with tunable recall.",
        "ElastiCache for Valkey 8.2+ includes the Search module by default.",
        "TLS encryption is mandatory for ElastiCache Serverless connections.",
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
        "How do I connect securely to ElastiCache?",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        results = await safe_search(query)
        for result in results:
            print(f"  Result: {result}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
