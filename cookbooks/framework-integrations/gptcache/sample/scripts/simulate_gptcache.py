#!/usr/bin/env python3
"""Simulate GPTCache's RedisVectorStore patterns using valkey-py.

This script exercises the exact command patterns that GPTCache uses when
configured with a Redis/Valkey vector backend.
"""

import numpy as np
import valkey

DIMENSION = 128
INDEX_NAME = "gptcache_sim"
PREFIX = "gptcache_sim:"


def create_index(client: valkey.Valkey) -> None:
    """Create a vector index matching GPTCache's FT.CREATE pattern."""
    client.execute_command(
        "FT.CREATE",
        INDEX_NAME,
        "ON",
        "HASH",
        "PREFIX",
        "1",
        PREFIX,
        "SCHEMA",
        "id",
        "TAG",
        "vector",
        "VECTOR",
        "FLAT",
        "6",
        "TYPE",
        "FLOAT32",
        "DIM",
        str(DIMENSION),
        "DISTANCE_METRIC",
        "COSINE",
    )
    print(f"Created index: {INDEX_NAME}")


def store_documents(client: valkey.Valkey, count: int = 5) -> list[str]:
    """Store documents with vectors via HSET (GPTCache pattern)."""
    keys = []
    for i in range(count):
        key = f"{PREFIX}{i}"
        vector = np.random.rand(DIMENSION).astype(np.float32).tobytes()
        client.hset(key, mapping={"id": str(i), "vector": vector})
        keys.append(key)
        print(f"  Stored: {key}")
    return keys


def knn_search(client: valkey.Valkey, query_vector: np.ndarray, k: int = 3) -> list:
    """Execute KNN search matching GPTCache's FT.SEARCH pattern."""
    query = f"*=>[KNN {k} @vector $vec AS score]"
    result = client.execute_command(
        "FT.SEARCH",
        INDEX_NAME,
        query,
        "PARAMS",
        "2",
        "vec",
        query_vector.astype(np.float32).tobytes(),
        "DIALECT",
        "2",
    )
    # Result format: [count, key1, fields1, key2, fields2, ...]
    count = result[0]
    print(f"  KNN search returned {count} results:")
    for i in range(1, len(result), 2):
        key = result[i]
        fields = result[i + 1]
        # fields is a list of [field_name, value, field_name, value, ...]
        field_dict = dict(zip(fields[0::2], fields[1::2]))
        score = field_dict.get("score", "N/A")
        print(f"    {key} (distance: {score})")
    return result


def detect_backend(client: valkey.Valkey) -> str:
    """Detect backend type via INFO SERVER (GPTCache pattern)."""
    info = client.info("server")
    server_name = info.get("server_name", "unknown")
    print(f"  Backend detected: {server_name}")
    return server_name


def probe_sortby(client: valkey.Valkey) -> None:
    """Probe SORTBY support — GPTCache tries this and catches the error."""
    query_vector = np.random.rand(DIMENSION).astype(np.float32).tobytes()
    query = f"*=>[KNN 3 @vector $vec AS score]"
    try:
        client.execute_command(
            "FT.SEARCH",
            INDEX_NAME,
            query,
            "SORTBY",
            "score",
            "ASC",
            "PARAMS",
            "2",
            "vec",
            query_vector,
            "DIALECT",
            "2",
        )
        print("  SORTBY: supported")
    except valkey.ResponseError as e:
        print(f"  SORTBY: not supported ({e})")


def cleanup(client: valkey.Valkey, keys: list[str]) -> None:
    """Clean up index and keys."""
    try:
        client.execute_command("FT.DROPINDEX", INDEX_NAME)
    except valkey.ResponseError:
        pass
    if keys:
        client.delete(*keys)
    print("Cleanup complete.")


def main():
    client = valkey.Valkey(host="localhost", port=6379)

    print("=== GPTCache RedisVectorStore Simulation ===\n")

    print("1. Backend detection")
    detect_backend(client)

    print("\n2. Creating vector index")
    create_index(client)

    print("\n3. Storing documents")
    keys = store_documents(client)

    print("\n4. KNN search")
    query = np.random.rand(DIMENSION).astype(np.float32)
    knn_search(client, query, k=3)

    print("\n5. SORTBY probe")
    probe_sortby(client)

    print("\n6. Cleanup")
    cleanup(client, keys)

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
