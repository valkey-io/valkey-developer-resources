"""Vector store demo using mock embeddings.

Demonstrates the Valkey patterns used by DB-GPT's ValkeyStore:
- HNSW index creation via FT.CREATE
- Document storage as HASH keys with vector embeddings
- KNN similarity search via FT.SEARCH
- Metadata filtering with TAG and NUMERIC fields
- Cleanup via FT.DROPINDEX and SCAN-based key deletion

Uses random float vectors as mock embeddings — no paid API required.
"""
from __future__ import annotations

import asyncio
import json
import random
import struct
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress

# Configuration matching ValkeyVectorConfig defaults
VECTOR_DIM = 128
INDEX_NAME = "dbgpt_demo_index"
KEY_PREFIX = "dbgpt:demo:"


def generate_mock_embedding(dim: int = VECTOR_DIM, seed: int | None = None) -> list[float]:
    """Generate a deterministic mock embedding vector."""
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def embedding_to_bytes(embedding: list[float]) -> bytes:
    """Convert a float list to FLOAT32 byte representation for Valkey."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


async def create_hnsw_index(client: GlideClient) -> None:
    """Create an HNSW index matching ValkeyStore's index creation pattern."""
    # Drop existing index if present (idempotent setup)
    try:
        await client.custom_command(["FT.DROPINDEX", INDEX_NAME])
    except Exception:
        pass  # Index doesn't exist yet — expected on first run

    await client.custom_command(
        [
            "FT.CREATE", INDEX_NAME,
            "ON", "HASH",
            "PREFIX", "1", KEY_PREFIX,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "10",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "M", "16",
            "EF_CONSTRUCTION", "200",
            "content", "TEXT",
            "category", "TAG",
            "year", "NUMERIC",
        ]
    )
    print(f"✓ Created HNSW index: {INDEX_NAME}")


async def wait_for_indexing(client: GlideClient) -> None:
    """Poll FT.INFO until indexing is complete (no time.sleep polling)."""
    while True:
        info = await client.custom_command(["FT.INFO", INDEX_NAME])
        # valkey-glide 2.3+ returns FT.INFO as a dict with bytes keys
        backfill = info.get(b"backfill_in_progress", b"0")
        if backfill in (b"0", "0", 0):
            break
        await asyncio.sleep(0.05)  # 50ms poll interval — demo only; production: poll FT.INFO "backfill_in_progress" field


async def load_documents(client: GlideClient) -> list[str]:
    """Store document chunks as HASH keys with embeddings and metadata."""
    documents = [
        {
            "content": "Valkey is a high-performance key-value store forked from Redis.",
            "category": "database",
            "year": 2024,
            "seed": 42,
        },
        {
            "content": "HNSW indexes provide approximate nearest neighbor search.",
            "category": "algorithms",
            "year": 2023,
            "seed": 43,
        },
        {
            "content": "DB-GPT supports multiple vector store backends including Valkey.",
            "category": "database",
            "year": 2024,
            "seed": 44,
        },
        {
            "content": "Cosine similarity measures the angle between two vectors.",
            "category": "algorithms",
            "year": 2022,
            "seed": 45,
        },
        {
            "content": "Vector databases enable semantic search over unstructured data.",
            "category": "database",
            "year": 2023,
            "seed": 46,
        },
    ]

    keys: list[str] = []
    for i, doc in enumerate(documents):
        key = f"{KEY_PREFIX}{i:04d}"
        embedding = generate_mock_embedding(VECTOR_DIM, seed=doc["seed"])
        vector_bytes = embedding_to_bytes(embedding)

        await client.hset(
            key,
            {
                "vector": vector_bytes,
                "content": doc["content"],
                "category": doc["category"],
                "year": str(doc["year"]),
                "metadata": json.dumps({"category": doc["category"], "year": doc["year"]}),
            },
        )
        keys.append(key)

    print(f"✓ Loaded {len(documents)} documents into Valkey")
    return keys


async def knn_search(client: GlideClient, query_seed: int, topk: int = 3) -> None:
    """Perform KNN vector similarity search (matching ValkeyStore.similar_search)."""
    query_embedding = generate_mock_embedding(VECTOR_DIM, seed=query_seed)
    query_bytes = embedding_to_bytes(query_embedding)

    # FT.SEARCH with KNN query — same pattern as ValkeyStore
    result = await client.custom_command(
        [
            "FT.SEARCH", INDEX_NAME,
            f"*=>[KNN {topk} @vector $query_vec]",
            "PARAMS", "2", "query_vec", query_bytes,
            "RETURN", "2", "content", "__vector_score",
            "DIALECT", "2",
        ]
    )

    # Parse results: [total_count, {key: {field: value, ...}, ...}]
    total = result[0]
    results_dict = result[1]
    print(f"\n  KNN Search (top-{topk}, {total} total matches):")

    for key_bytes, fields in results_dict.items():
        key = key_bytes if isinstance(key_bytes, str) else key_bytes.decode()
        score = fields.get(b"__vector_score", b"?")
        if isinstance(score, bytes):
            score = score.decode()
        content = fields.get(b"content", b"?")
        if isinstance(content, bytes):
            content = content.decode()
        print(f"    {score:>12s} | {key} | {content[:60]}")


async def filtered_search(client: GlideClient, query_seed: int) -> None:
    """Perform metadata-filtered KNN search (TAG + NUMERIC filters)."""
    query_embedding = generate_mock_embedding(VECTOR_DIM, seed=query_seed)
    query_bytes = embedding_to_bytes(query_embedding)

    # TAG filter: @category:{database}
    print("\n  Filtered search (category=database):")
    result = await client.custom_command(
        [
            "FT.SEARCH", INDEX_NAME,
            "(@category:{database})=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", query_bytes,
            "RETURN", "2", "content", "category",
            "DIALECT", "2",
        ]
    )

    results_dict = result[1]
    for key_bytes, fields in results_dict.items():
        category = fields.get(b"category", b"?")
        if isinstance(category, bytes):
            category = category.decode()
        content = fields.get(b"content", b"?")
        if isinstance(content, bytes):
            content = content.decode()
        print(f"    [{category}] {content[:50]}")

    # NUMERIC filter: @year:[2024 2024]
    print("\n  Filtered search (year=2024):")
    result = await client.custom_command(
        [
            "FT.SEARCH", INDEX_NAME,
            "(@year:[2024 2024])=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", query_bytes,
            "RETURN", "2", "content", "year",
            "DIALECT", "2",
        ]
    )

    results_dict = result[1]
    for key_bytes, fields in results_dict.items():
        year = fields.get(b"year", b"?")
        if isinstance(year, bytes):
            year = year.decode()
        content = fields.get(b"content", b"?")
        if isinstance(content, bytes):
            content = content.decode()
        print(f"    [year={year}] {content[:50]}")


async def cleanup(client: GlideClient) -> None:
    """Remove test index and keys using SCAN (never KEYS)."""
    # Drop the index (keys remain but are harmless without the index)
    try:
        await client.custom_command(["FT.DROPINDEX", INDEX_NAME])
    except Exception as exc:
        print(f"\n⚠ Index cleanup warning: {exc}")

    # Delete document keys via SCAN
    cursor = "0"
    deleted = 0
    while True:
        result = await client.custom_command(
            ["SCAN", cursor, "MATCH", f"{KEY_PREFIX}*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys = result[1]
        if keys:
            key_list = [k if isinstance(k, str) else k.decode() for k in keys]
            await client.delete(key_list)
            deleted += len(key_list)
        if cursor == "0":
            break

    print(f"\n✓ Cleaned up index and {deleted} document keys")


async def main() -> int:
    """Run the vector store demo."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dbgpt_vector_store_demo",
        request_timeout=5000,
    )

    try:
        client = await GlideClient.create(config)
    except Exception as exc:
        print(f"✗ Failed to connect to Valkey: {exc}")
        return 1

    try:
        print("=== DB-GPT ValkeyStore Pattern Demo ===\n")

        # Create index (mirrors ValkeyStore index creation)
        await create_hnsw_index(client)

        # Load documents (mirrors ValkeyStore.load_document)
        await load_documents(client)

        # Wait for indexing to complete
        await wait_for_indexing(client)
        print("✓ Indexing complete")

        # KNN search (mirrors ValkeyStore.similar_search)
        await knn_search(client, query_seed=42, topk=3)

        # Filtered search (mirrors ValkeyStore with metadata_schema)
        await filtered_search(client, query_seed=42)

        # Cleanup
        await cleanup(client)

        print("\n✅ Vector store demo complete!")
        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
