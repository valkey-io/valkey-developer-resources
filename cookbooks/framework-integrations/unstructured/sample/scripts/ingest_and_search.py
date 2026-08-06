#!/usr/bin/env python3
"""Document Ingestion & Search: Upload documents and query with KNN.

Demonstrates the Valkey patterns used by the unstructured-ingest connector:
- Store document chunks as hashes with vector embeddings
- Create HNSW index for KNN similarity search
- Query using FT.SEARCH with vector parameters

Uses deterministic mock embeddings (no ML model download required) to keep
the sample fast and dependency-light for CI.
"""

import asyncio
import os
import struct
from typing import Optional

import numpy as np
from glide import (
    DistanceMetricType,
    FtCreateOptions,
    FtSearchLimit,
    FtSearchOptions,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    RequestError,
    ft,
)


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

# Simulated embedding dimension (384 = all-MiniLM-L6-v2)
DIMENSION = 384
INDEX_NAME = "documents_index"
KEY_PREFIX = "doc:unstructured:"


# --- Sample documents ---

SAMPLE_DOCUMENTS = [
    {
        "element_id": "doc_valkey_001",
        "type": "NarrativeText",
        "text": (
            "Valkey is a high-performance, open-source key-value store. "
            "It supports strings, hashes, lists, sets, and sorted sets."
        ),
        "metadata": {"filename": "valkey_overview.txt", "page_number": 1},
    },
    {
        "element_id": "doc_valkey_002",
        "type": "NarrativeText",
        "text": (
            "Valkey Search provides vector similarity search using HNSW indexes. "
            "Approximate nearest neighbor queries return results in sub-millisecond time."
        ),
        "metadata": {"filename": "valkey_overview.txt", "page_number": 1},
    },
    {
        "element_id": "doc_valkey_003",
        "type": "NarrativeText",
        "text": (
            "Hashes store field-value pairs and are ideal for document storage. "
            "Each field can hold text, numbers, or binary data like embeddings."
        ),
        "metadata": {"filename": "valkey_overview.txt", "page_number": 2},
    },
    {
        "element_id": "doc_valkey_004",
        "type": "NarrativeText",
        "text": (
            "Valkey supports cluster mode for horizontal scaling. Data is sharded "
            "across multiple nodes using hash slots for high availability."
        ),
        "metadata": {"filename": "valkey_overview.txt", "page_number": 3},
    },
    {
        "element_id": "doc_valkey_005",
        "type": "NarrativeText",
        "text": (
            "RDB snapshots and AOF provide persistence options. Data survives "
            "server restarts while maintaining in-memory performance."
        ),
        "metadata": {"filename": "valkey_overview.txt", "page_number": 3},
    },
]


def deterministic_embedding(text: str, dim: int = DIMENSION) -> list[float]:
    """Generate a deterministic embedding from text (for testing).

    Uses a seeded random generator based on text hash so identical text
    always produces the same vector. NOT suitable for real similarity —
    use sentence-transformers or similar for production.
    """
    seed = hash(text) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    # L2 normalize for cosine similarity
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def vector_to_bytes(vec: list[float]) -> bytes:
    """Convert a float list to bytes for Valkey HSET."""
    return np.array(vec, dtype=np.float32).tobytes()


async def get_client() -> GlideClient:
    """Create a GLIDE async client."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        request_timeout=10000,
    )
    return await GlideClient.create(config)


async def upload_documents(documents: list[dict]) -> None:
    """Upload document chunks to Valkey (mirrors connector behavior)."""
    client = await get_client()

    try:
        # Store each document as a hash
        for doc in documents:
            embedding = deterministic_embedding(doc["text"])
            key = f"{KEY_PREFIX}{doc['element_id']}"

            fields = {
                "text": doc["text"],
                "element_type": doc["type"],
                "source_document": doc["metadata"]["filename"],
                "page_number": str(doc["metadata"]["page_number"]),
                "record_id": f"ingest-{doc['metadata']['filename']}",
                "embedding": vector_to_bytes(embedding),
            }

            await client.hset(key, fields)

        print(f"✓ Uploaded {len(documents)} document chunks")

        # Create HNSW index (if it doesn't exist)
        try:
            from glide import (
                NumericField,
                TagField,
                TextField,
                VectorAlgorithm,
                VectorField,
                VectorFieldAttributesHnsw,
                VectorType,
            )

            schema = [
                TextField("text"),
                TagField("element_type"),
                TagField("source_document"),
                TagField("record_id"),
                NumericField("page_number"),
                VectorField(
                    "embedding",
                    VectorAlgorithm.HNSW,
                    VectorFieldAttributesHnsw(
                        dimensions=DIMENSION,
                        distance_metric=DistanceMetricType.COSINE,
                        type=VectorType.FLOAT32,
                    ),
                ),
            ]

            await ft.create(
                client,
                INDEX_NAME,
                schema,
                FtCreateOptions(prefixes=[KEY_PREFIX]),
            )
            print(f"✓ Created HNSW index '{INDEX_NAME}'")

        except RequestError as e:
            if "Index already exists" in str(e):
                print(f"  Index '{INDEX_NAME}' already exists (skipping)")
            else:
                raise

    finally:
        await client.close()


async def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """Run KNN vector search against the document index."""
    client = await get_client()

    try:
        # Generate query embedding
        query_vec = deterministic_embedding(query)
        query_bytes = vector_to_bytes(query_vec)

        # KNN search
        knn_query = f"*=>[KNN {top_k} @embedding $query_vec AS score]"
        options = FtSearchOptions(
            limit=FtSearchLimit(offset=0, count=top_k),
            params={"query_vec": query_bytes},
        )

        results = await ft.search(client, INDEX_NAME, knn_query, options)

        # Parse results
        total = results[0] if results else 0
        docs = results[1] if len(results) > 1 else {}

        print(f"\nQuery: '{query}'")
        print(f"Found {total} results (showing top {top_k}):\n")

        parsed = []
        for key, fields in docs.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            text = fields.get(b"text", b"").decode()
            score = fields.get(b"score", b"0").decode()
            print(f"  [{score}] {key_str}")
            print(f"    {text[:100]}...")
            print()
            parsed.append({"key": key_str, "text": text, "score": float(score)})

        return parsed

    finally:
        await client.close()


async def cleanup() -> None:
    """Remove test data and index."""
    client = await get_client()
    try:
        # Drop index
        try:
            await ft.dropindex(client, INDEX_NAME)
            print(f"✓ Dropped index '{INDEX_NAME}'")
        except RequestError:
            pass

        # Delete keys
        for doc in SAMPLE_DOCUMENTS:
            await client.delete([f"{KEY_PREFIX}{doc['element_id']}"])
        print(f"✓ Deleted {len(SAMPLE_DOCUMENTS)} keys")
    finally:
        await client.close()


async def main():
    """Run the full ingestion and search demo."""
    print("=" * 60)
    print("Unstructured + Valkey: Document Ingestion & Search Demo")
    print("=" * 60)

    # Upload
    print("\n--- Uploading documents ---")
    await upload_documents(SAMPLE_DOCUMENTS)

    # Wait for indexing
    await asyncio.sleep(0.5)

    # Search
    print("\n--- Semantic search ---")
    await semantic_search("vector similarity search")
    await semantic_search("data persistence and durability")

    # Cleanup
    print("\n--- Cleanup ---")
    await cleanup()

    print("\n✓ Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
