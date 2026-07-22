"""CrewAI + Valkey getting started: connect, store a vector, and search.

Corresponds to cookbook: 01-getting-started.md.

Runs without any LLM or embedding service — uses fixed test vectors.
"""

from __future__ import annotations

import asyncio

import numpy as np
from glide import ft, GlideClient
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType,
    DistanceMetricType,
    FtCreateOptions,
    NumericField,
    TagField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
)
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions,
)

from common import cleanup, create_client, drop_index, field_text, field_float


INDEX_NAME = "crewai-getting-started"
PREFIX = "demo:mem:"
EMBEDDING_DIM = 4


async def run_demo() -> None:
    """Demonstrate basic Valkey vector operations with GLIDE v2."""
    client = await create_client()
    keys: list[str] = []
    try:
        # Step 1: Verify connection
        pong = await client.ping()
        print(f"Connected to Valkey: {pong}")

        # Step 2: Create HNSW index
        await drop_index(client, INDEX_NAME)
        hnsw = VectorFieldAttributesHnsw(
            dimensions=EMBEDDING_DIM,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        )
        schema = [
            TagField("scope"),
            TagField("content"),
            NumericField("importance"),
            VectorField("embedding", VectorAlgorithm.HNSW, hnsw),
        ]
        await ft.create(
            client, INDEX_NAME, schema,
            FtCreateOptions(DataType.HASH, prefixes=[PREFIX]),
        )
        print("Created vector index")

        # Step 3: Store memory records as HASH with embeddings
        memories = [
            {"id": "1", "content": "Valkey uses HNSW for vector search",
             "scope": "/tech", "importance": "0.9",
             "embedding": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)},
            {"id": "2", "content": "Python is great for AI",
             "scope": "/tech", "importance": "0.7",
             "embedding": np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)},
            {"id": "3", "content": "Jazz originated in New Orleans",
             "scope": "/music", "importance": "0.5",
             "embedding": np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)},
        ]

        for mem in memories:
            key = f"{PREFIX}{mem['id']}"
            keys.append(key)
            await client.hset(key, {
                "content": mem["content"],
                "scope": mem["scope"],
                "importance": mem["importance"],
                "embedding": mem["embedding"].tobytes(),
            })
        print(f"Stored {len(memories)} memory records")

        # Wait for indexing
        await asyncio.sleep(0.5)

        # Step 4: KNN search — find memories similar to a query vector
        query_vec = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
        query_vec = query_vec / np.linalg.norm(query_vec)
        query_bytes = query_vec.tobytes()

        count, docs = await ft.search(
            client, INDEX_NAME,
            "(*)=>[KNN 2 @embedding $query_vec AS score]",
            FtSearchOptions(params={"query_vec": query_bytes}, dialect=2),
        )

        print(f"\nSearch results (top {count} by similarity to 'tech' vector):")
        for doc_key, fields in docs.items():
            content = field_text(fields, "content")
            score = field_float(fields, "score")
            similarity = 1.0 - score
            print(f"  {content} (similarity: {similarity:.3f})")

        # Verify we got results
        assert count >= 1, "Expected at least 1 search result"
        print("\nAll operations successful.")

    finally:
        try:
            await cleanup(client, INDEX_NAME, keys)
        finally:
            await client.close()


async def main() -> None:
    await run_demo()


if __name__ == "__main__":
    asyncio.run(main())
