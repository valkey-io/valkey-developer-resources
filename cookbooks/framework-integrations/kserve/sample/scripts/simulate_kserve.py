"""Simulate KServe's Valkey usage patterns.

Demonstrates:
1. LMCache KV cache chunk storage (binary blobs with model-specific keys)
2. Prefix-cache block index (hash → pod mapping)
3. Feast feature store reads (HSET/HGET/pipeline)
"""

import hashlib
import struct
import time

import numpy as np
import valkey


def main() -> None:
    client = valkey.Valkey(host="localhost", port=6379)
    try:
        print("=== KServe + Valkey Pattern Simulation ===\n")

        # --- Pattern 1: LMCache KV Cache Offloading ---
        print("1. LMCache KV Cache Offloading")
        print("   Simulating vLLM KV cache chunk storage...\n")

        model_name = "meta-llama/Llama-3.2-1B-Instruct"
        chunk_size = 256  # tokens per chunk
        # Simulate KV cache chunk (simplified: normally this is layers × heads × dim × chunk × dtype)
        rng = np.random.default_rng(42)
        chunk_data = rng.random(1024, dtype=np.float16).tobytes()  # ~2KB simulated chunk

        # LMCache key format: model@worker@layer@hash@dtype
        chunks_stored = 0
        for layer in range(4):  # Simulate 4 layers
            token_hash = hashlib.sha256(f"prompt_tokens_chunk0_layer{layer}".encode()).hexdigest()[:16]
            key = f"{model_name}@0@{layer}@{token_hash}@half"
            client.set(key, chunk_data)
            chunks_stored += 1

        print(f"   Stored {chunks_stored} KV cache chunks")
        print(f"   Key pattern: {model_name}@<worker>@<layer>@<hash>@half")
        print(f"   Chunk size: {len(chunk_data)} bytes each")

        # Simulate cache hit (same prompt, second request)
        first_key = f"{model_name}@0@0@{hashlib.sha256(b'prompt_tokens_chunk0_layer0').hexdigest()[:16]}@half"
        hit = client.get(first_key)
        if hit:
            print(f"   Cache HIT: retrieved {len(hit)} bytes ✓")
        else:
            print("   Cache MISS (expected on first run)")

        # --- Pattern 2: Prefix-Cache Block Index ---
        print("\n2. Prefix-Cache Block Index (EPP shared state)")
        print("   Simulating block hash → pod IP mapping...\n")

        pod_ips = ["10.0.1.10", "10.0.1.11", "10.0.1.12"]
        block_hashes = [
            hashlib.sha256(f"block_{i}_seed42".encode()).hexdigest()
            for i in range(12)
        ]

        # Store block→pod mappings (round-robin across pods)
        for i, bh in enumerate(block_hashes):
            pod_ip = pod_ips[i % len(pod_ips)]
            client.set(f"idx:{bh}", pod_ip)

        # Simulate routing lookup: find which pod has a given block
        lookup_hash = block_hashes[5]
        pod = client.get(f"idx:{lookup_hash}")
        print(f"   Stored {len(block_hashes)} block→pod mappings")
        print(f"   Lookup block {lookup_hash[:12]}... → pod {pod.decode()}")

        # Simulate eviction (pod restart)
        evicted = 0
        for bh in block_hashes:
            if client.get(f"idx:{bh}") == b"10.0.1.12":
                client.delete(f"idx:{bh}")
                evicted += 1
        print(f"   Evicted {evicted} entries for pod 10.0.1.12 (simulated restart)")

        # --- Pattern 3: Feast Feature Store ---
        print("\n3. Feast Feature Store (online feature serving)")
        print("   Simulating feature materialization + retrieval...\n")

        # Materialize features (normally done by `feast materialize`)
        users = ["user_001", "user_002", "user_003", "user_004", "user_005"]
        for user in users:
            features = {
                "age": str(rng.integers(18, 65)),
                "purchase_count": str(rng.integers(0, 100)),
                "avg_session_mins": f"{rng.uniform(1.0, 60.0):.2f}",
                "embedding": rng.random(8, dtype=np.float32).tobytes().hex(),
            }
            client.hset(f"feast:project:user_features:{user}", mapping=features)

        print(f"   Materialized features for {len(users)} users")

        # Simulate inference-time feature lookup (pipeline for batch)
        pipe = client.pipeline()
        for user in users[:3]:
            pipe.hgetall(f"feast:project:user_features:{user}")
        results = pipe.execute()

        print(f"   Retrieved features for {len(results)} users via pipeline")
        for i, r in enumerate(results):
            print(f"     {users[i]}: {len(r)} features")

        # --- Cleanup ---
        print("\n4. Cleanup")
        # Delete LMCache keys
        for key in client.keys(f"{model_name}@*"):
            client.delete(key)
        # Delete index keys
        for key in client.keys("idx:*"):
            client.delete(key)
        # Delete feast keys
        for key in client.keys("feast:*"):
            client.delete(key)
        print("   All test data removed ✓")

        print("\n=== All KServe patterns validated successfully ===")
    finally:
        client.close()


if __name__ == "__main__":
    main()
