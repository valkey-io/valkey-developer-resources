"""Simulate Kong AI Gateway's Valkey usage patterns.

Demonstrates:
1. Server auto-detection (INFO server_name check)
2. JSON vector document storage (semantic cache entries)
3. FT.CREATE index on JSON with HNSW COSINE
4. FT.SEARCH KNN for semantic similarity matching
5. Threshold-based filtering (cache hit/miss decision)
"""

import json
import struct
import time

import numpy as np
import valkey

DIMENSION = 128


def vector_to_bytes(vector: list[float]) -> bytes:
    """Pack floats as little-endian float32."""
    return struct.pack(f"<{len(vector)}f", *vector)


def main() -> None:
    print("=== Kong AI Gateway + Valkey Pattern Simulation ===\n")

    client = valkey.Valkey(host="localhost", port=6379)
    rng = np.random.default_rng(42)

    try:
        # Step 1: Auto-detection (Kong checks server_name)
        print("1. Server auto-detection")
        info = client.info("server")
        server_name = info.get("server_name", "unknown")
        print(f"   INFO server_name: {server_name}")
        if server_name == "valkey":
            print("   → Kong will use Valkey-specific driver ✓")
        else:
            print("   → Kong will use Redis driver")

        # Step 2: Create semantic cache index
        print("\n2. Creating semantic cache index (FT.CREATE)")
        index_name = "demo:kong:semantic-cache"
        prefix = "demo:kong:cache:"

        try:
            client.execute_command("FT.DROPINDEX", index_name)
        except valkey.ResponseError:
            pass

        client.execute_command(
            "FT.CREATE", index_name,
            "ON", "JSON",
            "PREFIX", "1", prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "$.content", "AS", "content", "TEXT",
        )
        print(f"   Index '{index_name}' created ✓")

        # Step 3: Store cached responses (like ai-semantic-cache)
        print("\n3. Storing cached prompt/response pairs via JSON.SET")
        cached_items = [
            {"content": "What is Valkey?", "response": "Valkey is a high-performance key-value store..."},
            {"content": "How do I configure Kong?", "response": "Kong can be configured via..."},
            {"content": "Explain vector search", "response": "Vector search finds similar items..."},
            {"content": "What is semantic caching?", "response": "Semantic caching stores responses..."},
        ]

        for i, item in enumerate(cached_items):
            vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            doc = {"content": item["content"], "embedding": vec, "response": item["response"]}
            client.execute_command("JSON.SET", f"{prefix}{i}", "$", json.dumps(doc))

        print(f"   Stored {len(cached_items)} cached entries ✓")
        time.sleep(0.5)

        # Step 4: Semantic cache lookup (KNN search)
        print("\n4. Semantic cache lookup (FT.SEARCH KNN)")
        query_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
        result = client.execute_command(
            "FT.SEARCH", index_name,
            "*=>[KNN 1 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(query_vec),
            "SORTBY", "vector_score",
            "DIALECT", "2",
        )
        count = result[0]
        print(f"   Query: *=>[KNN 1 @embedding $BLOB AS vector_score]")
        print(f"   Best match found: {count} result(s)")

        if count > 0:
            fields = dict(zip(result[2][::2], result[2][1::2]))
            distance = float(fields[b"vector_score"])
            print(f"   Cosine distance: {distance:.4f}")

            # Step 5: Threshold check
            threshold = 0.1
            if distance <= threshold:
                print(f"   → Cache HIT (distance {distance:.4f} ≤ threshold {threshold})")
            else:
                print(f"   → Cache MISS (distance {distance:.4f} > threshold {threshold})")

        # Step 6: Semantic routing (embed prompt, compare to model descriptions)
        print("\n5. Semantic routing simulation")
        routing_index = "demo:kong:routing"
        routing_prefix = "demo:kong:route:"

        try:
            client.execute_command("FT.DROPINDEX", routing_index)
        except valkey.ResponseError:
            pass

        client.execute_command(
            "FT.CREATE", routing_index,
            "ON", "JSON",
            "PREFIX", "1", routing_prefix,
            "SCHEMA",
            "$.embedding", "AS", "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(DIMENSION),
            "DISTANCE_METRIC", "COSINE",
            "$.model", "AS", "model", "TAG",
        )

        models = [
            {"model": "gpt-3.5-turbo", "description": "Code specialist"},
            {"model": "gpt-4o", "description": "IT support"},
            {"model": "gpt-4o-mini", "description": "General queries"},
        ]
        for i, m in enumerate(models):
            vec = rng.random(DIMENSION, dtype=np.float32).tolist()
            doc = {"model": m["model"], "description": m["description"], "embedding": vec}
            client.execute_command("JSON.SET", f"{routing_prefix}{i}", "$", json.dumps(doc))

        time.sleep(0.5)

        # Route a request
        request_vec = rng.random(DIMENSION, dtype=np.float32).tolist()
        result = client.execute_command(
            "FT.SEARCH", routing_index,
            "*=>[KNN 1 @embedding $BLOB AS vector_score]",
            "PARAMS", "2", "BLOB", vector_to_bytes(request_vec),
            "SORTBY", "vector_score",
            "DIALECT", "2",
        )
        if result[0] > 0:
            doc_json = client.execute_command("JSON.GET", result[1].decode(), "$")
            routed_doc = json.loads(doc_json)[0]
            print(f"   Request routed to: {routed_doc['model']} ({routed_doc['description']})")
        print("   Routing decision made ✓")

        # Cleanup
        print("\n6. Cleanup")
        client.execute_command("FT.DROPINDEX", index_name)
        client.execute_command("FT.DROPINDEX", routing_index)
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="demo:kong:*", count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
        print("   All test data removed ✓")

        print("\n=== All Kong AI Gateway patterns validated successfully ===")
    finally:
        client.close()


if __name__ == "__main__":
    main()
