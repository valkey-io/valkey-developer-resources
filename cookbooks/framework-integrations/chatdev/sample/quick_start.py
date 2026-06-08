# -*- coding: utf-8 -*-
"""Cookbook 01 - Getting Started with ChatDev + Valkey.

Demonstrates: connecting to Valkey, creating an FT index, storing memory
items with synthetic embeddings, running KNN vector search, and cleanup.

No API key required — uses hardcoded vectors to demonstrate the
ValkeyMemory storage and retrieval mechanics.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    pip install valkey-glide-sync
"""

from __future__ import annotations

import struct
import time
import uuid

import glide_sync


def main() -> None:
    """Run the quick start example."""
    print("=== ChatDev + Valkey: Quick Start ===\n")

    # 1. Connect to Valkey
    config = glide_sync.GlideClientConfiguration(
        addresses=[glide_sync.NodeAddress("localhost", 6379)]
    )
    client = glide_sync.GlideClient.create(config)
    print("Connected to Valkey\n")

    # 2. Create an FT index (same schema ValkeyMemory uses)
    index_name = "quickstart_memory"
    prefix = "memory:"
    dim = 3  # Synthetic 3-dim vectors for demo

    schema = [
        glide_sync.TagField("content_summary"),
        glide_sync.TagField("agent_role"),
        glide_sync.NumericField("timestamp"),
        glide_sync.VectorField(
            "embedding",
            glide_sync.VectorAlgorithm.HNSW,
            glide_sync.VectorFieldAttributesHnsw(
                dimensions=dim,
                distance_metric=glide_sync.DistanceMetricType.COSINE,
                type=glide_sync.VectorType.FLOAT32,
            ),
        ),
    ]
    options = glide_sync.FtCreateOptions(glide_sync.DataType.HASH, prefixes=[prefix])

    try:
        glide_sync.ft.create(client, index_name, schema, options)
        print(f"Created FT index '{index_name}' (HNSW, COSINE, dim={dim})")
    except Exception as exc:
        if "already exists" in str(exc).lower():
            print(f"Index '{index_name}' already exists")
        else:
            raise

    # 3. Store memory items (same as ValkeyMemory.update())
    memories = [
        ("Python is great for data science", [0.9, 0.1, 0.2], "coder"),
        ("The UI should follow material design", [0.1, 0.9, 0.2], "designer"),
        ("We need integration tests for the API", [0.8, 0.2, 0.3], "coder"),
        ("Use a dark theme for the dashboard", [0.2, 0.8, 0.4], "designer"),
    ]

    stored_keys = []
    print(f"\nStoring {len(memories)} memory items...")
    for text, embedding, role in memories:
        key = f"{prefix}{uuid.uuid4().hex}"
        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)

        client.hset(key, {
            "content_summary": text,
            "embedding": embedding_bytes,
            "agent_role": role,
            "timestamp": str(time.time()),
        })
        stored_keys.append(key)
        print(f"  [{role}] {text}")

    # Small delay for indexing
    time.sleep(0.5)

    # 4. KNN vector search (same as ValkeyMemory.retrieve())
    print("\n--- KNN Search (role=coder, top_k=2) ---")
    query_vec = [0.85, 0.15, 0.25]  # Similar to coding-related memories
    query_bytes = struct.pack(f"{len(query_vec)}f", *query_vec)

    ft_query = "(@agent_role:{coder})=>[KNN 2 @embedding $vec]"
    search_options = glide_sync.FtSearchOptions(
        params={"vec": query_bytes},
        dialect=2,
    )

    results = glide_sync.ft.search(client, index_name, ft_query, search_options)

    if results:
        count = results[0]
        print(f"Found {count} results:")
        for entry in results[1:]:
            if isinstance(entry, dict):
                for key, fields in entry.items():
                    content = fields.get(b"content_summary", b"").decode()
                    score = fields.get(b"__embedding_score", b"1.0").decode()
                    similarity = 1.0 - float(score)
                    print(f"  • {content} (similarity: {similarity:.3f})")

    # 5. Cleanup
    print("\n--- Cleanup ---")
    glide_sync.ft.dropindex(client, index_name)
    for key in stored_keys:
        client.delete([key])
    print(f"Dropped index and deleted {len(stored_keys)} keys")
    print("\nDone!")


if __name__ == "__main__":
    main()
