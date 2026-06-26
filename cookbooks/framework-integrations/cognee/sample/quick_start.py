"""Cognee + Valkey quick start — add documents, build knowledge graph, search.

Corresponds to cookbook: 01-getting-started.md
"""

from __future__ import annotations

import asyncio
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

    print("Adding documents...")
    await add("""
    Natural language processing (NLP) is an interdisciplinary
    subfield of computer science and information retrieval.
    """)

    await add("""
    Valkey is an open-source, high-performance key-value datastore
    that supports vector similarity search through the Valkey Search module.
    """)

    print("Running cognify (building knowledge graph)...")
    await cognify()

    print("\nSearching: 'Tell me about NLP'")
    results = await search(
        query_type=SearchType.GRAPH_COMPLETION,
        query_text="Tell me about NLP",
    )
    for result in results:
        print(f"  Result: {result}")

    print("\nSearching: 'What is Valkey?'")
    results = await search(
        query_type=SearchType.GRAPH_COMPLETION,
        query_text="What is Valkey?",
    )
    for result in results:
        print(f"  Result: {result}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
