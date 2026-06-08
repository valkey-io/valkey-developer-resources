"""Cognee + Valkey knowledge graph — multi-document relationships.

Corresponds to cookbook: 02-knowledge-graph.md

Demonstrates how Cognee connects concepts across multiple documents
and answers questions that require reasoning across document boundaries.
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

    # Add multiple related documents — no single document has the full picture
    print("Adding related documents...")
    await add("""
    Machine learning is a subset of artificial intelligence that
    enables systems to learn from data without explicit programming.
    """)

    await add("""
    Deep learning uses neural networks with multiple layers.
    It has revolutionized natural language processing and computer vision.
    """)

    await add("""
    Transformers are a deep learning architecture introduced in 2017.
    They form the basis of models like BERT and GPT.
    """)

    print("Running cognify (building knowledge graph across documents)...")
    await cognify()

    # Queries that require connecting information across documents
    queries = [
        "How do transformers relate to artificial intelligence?",
        "What has deep learning revolutionized?",
        "What is the relationship between machine learning and transformers?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        results = await search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=query,
        )
        for result in results:
            print(f"  {result}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
