"""Cognee + Valkey quick start — add documents, build knowledge graph, search.

Corresponds to cookbook: 01-getting-started.md
Uses Ollama (local, free) for both LLM and embeddings by default.
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
