"""Demonstrate document ingestion and KNN search patterns from Cookbook 02.

This script creates an HNSW index, ingests documents with embeddings,
performs KNN vector similarity search, and demonstrates source isolation —
all patterns used by DocsGPT's ValkeyStore implementation.

Uses synthetic embeddings (no paid API needed). The patterns are identical
to what DocsGPT does with real embeddings from an LLM.

Usage:
    python scripts/ingestion_demo.py

Requirements:
    - Valkey running on localhost:6379 with valkey-search module
    - pip install valkey-glide-sync
"""
from __future__ import annotations

import json
import os
import struct
import sys
import uuid
from typing import List

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

INDEX_NAME = "__docsgpt_demo_index__"
PREFIX = "__docsgpt_demo__:"
EMBEDDING_DIM = 768


def make_embedding(seed: float) -> bytes:
    """Create a synthetic embedding vector as packed float32 bytes.

    In production, DocsGPT generates these from the configured embedding model.
    Here we use synthetic vectors to demonstrate the storage and search patterns.
    """
    floats = [seed + (i * 0.001) for i in range(EMBEDDING_DIM)]
    return struct.pack(f"<{EMBEDDING_DIM}f", *floats)


def create_index(client: GlideClient) -> None:
    """Create the HNSW search index matching DocsGPT's schema."""
    try:
        client.custom_command(
            [
                "FT.CREATE", INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", PREFIX,
                "SCHEMA",
                "content", "TEXT",
                "source_id", "TAG",
                "metadata", "TEXT",
                "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(EMBEDDING_DIM),
                "DISTANCE_METRIC", "COSINE",
            ]
        )
        print(f"✓ Created HNSW index '{INDEX_NAME}' (dim={EMBEDDING_DIM}, cosine)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"✓ Index '{INDEX_NAME}' already exists")
        else:
            raise


def ingest_documents(client: GlideClient, source_id: str, documents: List[dict]) -> List[str]:
    """Ingest documents as HASH keys with embeddings.

    This mirrors DocsGPT's ValkeyStore.add_texts() method.
    """
    doc_ids = []
    for doc in documents:
        doc_id = str(uuid.uuid4())
        key = f"{PREFIX}{doc_id}"

        client.hset(
            key,
            {
                "content": doc["text"],
                "source_id": source_id,
                "metadata": json.dumps(doc.get("metadata", {})),
                "embedding": make_embedding(doc["embedding_seed"]),
            },
        )
        doc_ids.append(doc_id)

    return doc_ids


def search(client: GlideClient, source_id: str, query_seed: float, k: int = 3) -> None:
    """Perform KNN vector search filtered by source_id.

    This mirrors DocsGPT's ValkeyStore.search() method.
    """
    import time
    time.sleep(0.2)  # Brief wait for indexing

    query_embedding = make_embedding(query_seed)

    # Escape special characters in source_id for TAG query
    escaped_source = source_id.replace("-", "\\-").replace("/", "\\/")

    # GLIDE RESP3 returns: [total, {key: {field: value}, ...}]
    result = client.custom_command(
        [
            "FT.SEARCH", INDEX_NAME,
            f"@source_id:{{{escaped_source}}}=>[KNN {k} @embedding $BLOB AS score]",
            "PARAMS", "2", "BLOB", query_embedding,
            "RETURN", "3", "content", "source_id", "score",
            "LIMIT", "0", str(k),
        ]
    )

    total = result[0]
    docs_map = result[1] if len(result) > 1 else {}

    print(f"\n  Search results (source={source_id}, k={k}, total_matches={total}):")

    # Parse RESP3 response: {key: {field: value}, ...}
    rank = 1
    for key, fields in docs_map.items():
        key_str = key if isinstance(key, str) else key.decode()
        content = fields.get(b"content", fields.get("content", b"?"))
        score = fields.get(b"score", fields.get("score", b"?"))
        if isinstance(content, bytes):
            content = content.decode()
        if isinstance(score, bytes):
            score = score.decode()
        print(f"    {rank}. [score={score}] {content[:60]}...")
        rank += 1


def cleanup(client: GlideClient) -> None:
    """Remove the demo index and all demo keys."""
    # Drop the index (keeps keys intact)
    try:
        client.custom_command(["FT.DROPINDEX", INDEX_NAME])
    except Exception:
        pass

    # Delete all keys with the demo prefix
    cursor = "0"
    while True:
        result = client.custom_command(
            ["SCAN", cursor, "MATCH", f"{PREFIX}*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys = result[1] if isinstance(result[1], list) else []
        if keys:
            key_list = [k if isinstance(k, str) else k.decode() for k in keys]
            client.delete(key_list)
        if cursor == "0":
            break

    print("\n✓ Cleaned up demo index and keys")


def main() -> None:
    """Run the full ingestion and search demo."""
    print(f"Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)]
    )
    client = GlideClient.create(config)
    assert client.ping() == b"PONG"
    print("✓ Connected")

    # Clean up any leftover data from previous runs
    cleanup(client)

    # Step 1: Create the HNSW index
    print("\n--- Step 1: Create HNSW Index ---")
    create_index(client)

    # Step 2: Ingest documents for two sources
    print("\n--- Step 2: Ingest Documents ---")
    docs_source_a = [
        {"text": "Valkey is a high-performance in-memory data store.", "embedding_seed": 0.10, "metadata": {"page": 1}},
        {"text": "HNSW provides sub-millisecond approximate nearest neighbor search.", "embedding_seed": 0.20, "metadata": {"page": 2}},
        {"text": "The GLIDE client uses multiplexed connections for throughput.", "embedding_seed": 0.30, "metadata": {"page": 3}},
        {"text": "FT.CREATE builds the index incrementally as documents are added.", "embedding_seed": 0.40, "metadata": {"page": 4}},
    ]
    ids_a = ingest_documents(client, "projectdocs", docs_source_a)
    print(f"  ✓ Ingested {len(ids_a)} docs into source 'projectdocs'")

    docs_source_b = [
        {"text": "DocsGPT is an open-source AI assistant for document retrieval.", "embedding_seed": 0.50, "metadata": {"page": 1}},
        {"text": "RAG combines retrieval with generation for grounded answers.", "embedding_seed": 0.60, "metadata": {"page": 2}},
    ]
    ids_b = ingest_documents(client, "readmedocs", docs_source_b)
    print(f"  ✓ Ingested {len(ids_b)} docs into source 'readmedocs'")

    # Step 3: KNN Search with source isolation
    print("\n--- Step 3: KNN Search (Source Isolation) ---")
    print("\n  Searching source 'projectdocs' (query closest to first doc):")
    search(client, "projectdocs", query_seed=0.10, k=3)

    print("\n  Searching source 'readmedocs' (query closest to RAG doc):")
    search(client, "readmedocs", query_seed=0.60, k=2)

    # Step 4: Demonstrate chunk deletion
    print("\n--- Step 4: Chunk Deletion ---")
    key_to_delete = f"{PREFIX}{ids_a[0]}"
    client.delete([key_to_delete])
    print(f"  ✓ Deleted chunk: {ids_a[0]}")

    # Verify it's gone from search
    search(client, "projectdocs", query_seed=0.10, k=3)

    # Step 5: FT.INFO for index health
    print("\n--- Step 5: Index Health (FT.INFO) ---")
    info = client.custom_command(["FT.INFO", INDEX_NAME])

    # FT.INFO with RESP3 returns a dict or list depending on version
    if isinstance(info, dict):
        # RESP3 dict format
        num_docs = info.get(b"num_docs", info.get("num_docs", "?"))
        indexing = info.get(b"indexing", info.get("indexing", "?"))
        if isinstance(num_docs, bytes):
            num_docs = num_docs.decode()
        if isinstance(indexing, bytes):
            indexing = indexing.decode()
        print(f"  Index name: {INDEX_NAME}")
        print(f"  Num docs:   {num_docs}")
        print(f"  Indexing:   {indexing}")
    else:
        # Flat list format
        print(f"  Index name: {INDEX_NAME}")
        print(f"  FT.INFO returned {len(info)} fields")

    # Cleanup
    cleanup(client)
    client.close()
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    main()
