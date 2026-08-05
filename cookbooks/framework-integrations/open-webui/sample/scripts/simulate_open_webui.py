"""Simulate Open WebUI's ValkeyClient patterns using valkey-py.

Demonstrates the exact flow Open WebUI performs:
1. Connect and validate server/module versions
2. Create HNSW index on HASH with TAG/TEXT fields
3. Store document chunks as HASH with float32 vector bytes
4. KNN search with and without TAG filters
5. Delete by ID and reset collection
"""

import json
import sys
from pathlib import Path

import numpy as np
import valkey

# Add sample root to path so helpers is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import (  # noqa: E402
    COLLECTION_NAME,
    COLLECTION_PREFIX,
    DIMENSION,
    INDEX_NAME,
    KEY_PREFIX,
    vector_to_bytes,
    wait_for_indexing,
)


def main() -> None:
    print("=== Open WebUI ValkeyClient Pattern Simulation ===\n")

    client = valkey.Valkey(host="localhost", port=6379)
    try:
        # Step 1: Connectivity + version check
        print("1. Connectivity and version check")
        client.ping()
        info = client.info("server")
        version = info.get("valkey_version", "unknown")
        print(f"   Valkey v{version} ✓")

        # Step 2: Create FT index (matches _create_index)
        print("\n2. Creating HNSW vector index")
        cleanup(client)

        client.execute_command(
            "FT.CREATE", INDEX_NAME,
            "ON", "HASH",
            "PREFIX", "1", KEY_PREFIX,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "10",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "M", "16",
            "EF_CONSTRUCTION", "200",
            "text", "TEXT",
            "id", "TAG",
            "metadata_json", "TEXT",
            "hash", "TAG",
            "file_id", "TAG",
            "source", "TAG",
            "knowledge_base_id", "TAG",
        )
        print(f"   Index '{INDEX_NAME}' created ✓")

        # Step 3: Store documents (matches insert method)
        print("\n3. Storing document chunks via HSET")
        rng = np.random.default_rng(42)
        docs = [
            {"id": "chunk-1", "text": "Valkey is a high-performance data store",
             "metadata": {"source": "docs.md", "file_id": "file-001", "hash": "abc123"}},
            {"id": "chunk-2", "text": "Open WebUI supports multiple vector backends",
             "metadata": {"source": "readme.md", "file_id": "file-002", "hash": "def456"}},
            {"id": "chunk-3", "text": "HNSW provides fast approximate nearest neighbors",
             "metadata": {"source": "docs.md", "file_id": "file-001", "hash": "ghi789"}},
            {"id": "chunk-4", "text": "RAG pipelines combine retrieval with generation",
             "metadata": {"source": "tutorial.md", "file_id": "file-003", "hash": "jkl012"}},
            {"id": "chunk-5", "text": "Valkey search module enables vector similarity",
             "metadata": {"source": "docs.md", "file_id": "file-001", "hash": "mno345"}},
        ]

        for doc in docs:
            key = KEY_PREFIX + doc["id"]
            vector = rng.random(DIMENSION, dtype=np.float32).tolist()
            mapping = {
                "id": doc["id"],
                "vector": vector_to_bytes(vector),
                "text": doc["text"],
                "metadata_json": json.dumps(doc["metadata"]),
                "hash": doc["metadata"].get("hash", ""),
                "file_id": doc["metadata"].get("file_id", ""),
                "source": doc["metadata"].get("source", ""),
                "knowledge_base_id": "kb-demo",
            }
            client.hset(key, mapping=mapping)
        print(f"   Stored {len(docs)} chunks ✓")

        # Wait for indexing
        wait_for_indexing(client, INDEX_NAME, expected=len(docs))

        # Step 4: KNN search (matches search method)
        print("\n4. KNN similarity search")
        query_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
        result = client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "*=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        print(f"   Query: *=>[KNN 3 @vector $query_vec]")
        print(f"   Results: {count} matches ✓")

        # Step 5: Filtered KNN (matches search with filter)
        print("\n5. TAG-filtered KNN search")
        result = client.execute_command(
            "FT.SEARCH", INDEX_NAME,
            "(@file_id:{file\\-001})=>[KNN 3 @vector $query_vec]",
            "PARAMS", "2", "query_vec", vector_to_bytes(query_vec),
            "DIALECT", "2",
        )
        count = result[0]
        print(f"   Filter: @file_id:{{file-001}}")
        print(f"   Results: {count} matches ✓")

        # Step 6: Delete by ID
        print("\n6. Delete document by ID")
        deleted = client.delete(KEY_PREFIX + "chunk-4")
        print(f"   Deleted 'chunk-4': {deleted} key removed ✓")

        # Step 7: Index info
        print("\n7. Collection stats (FT.INFO)")
        ft_info = client.execute_command("FT.INFO", INDEX_NAME)
        print(f"   FT.INFO returned successfully ✓")

        # Step 8: Cleanup
        print("\n8. Collection reset (drop index + delete keys)")
        cleanup(client)
        print("   Collection reset ✓")

        print("\n=== All patterns validated successfully ===")
    finally:
        client.close()


def cleanup(client: valkey.Valkey) -> None:
    """Drop index and delete keys (matches delete_collection)."""
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=KEY_PREFIX + "*", count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break


if __name__ == "__main__":
    main()
