"""Cognee + Valkey knowledge graph — multi-document relationships.

Corresponds to cookbook: 02-knowledge-graph.md

Demonstrates how Cognee connects concepts across multiple documents
and answers questions that require reasoning across document boundaries.
"""

from __future__ import annotations

import asyncio
import pathlib

from common import configure_ollama_env

configure_ollama_env()

from cognee import SearchType, add, cognify, search  # noqa: E402
from cognee_community_vector_adapter_valkey import register  # noqa: E402, F401

from common import bootstrap_cognee  # noqa: E402


async def main() -> None:
    await bootstrap_cognee(pathlib.Path(__file__).parent)

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
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"{'=' * 60}")
        results = await search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=query,
        )
        for result in results:
            print(f"  {result}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
