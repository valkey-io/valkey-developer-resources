#!/usr/bin/env python3
"""Simulate Dify's vector store operations against a live Valkey instance.

Demonstrates the complete lifecycle:
1. Create an FT index (same schema Dify uses)
2. Store documents with embeddings as HASH keys
3. Perform KNN vector similarity search
4. Perform full-text search on page_content
5. Delete documents by group
6. Drop the index

Requires: Valkey with valkey-search module on localhost:6379.
"""

from __future__ import annotations

import asyncio
import json
import struct
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress


COLLECTION = "dify_demo_collection"
PREFIX = f"doc:{COLLECTION}:"
INDEX_NAME = f"idx:{COLLECTION}"
GROUP_ID = "dataset_demo_001"
VECTOR_DIM = 4  # Small dim for demo readability


def to_str(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


def float_vector_to_bytes(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def escape_tag(value: str) -> str:
    special = r"\.+*?[{()|^$!<>~@&\"-]"
    return "".join(f"\\{ch}" if ch in special else ch for ch in value)


async def main() -> None:
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dify_simulation",
        request_timeout=10000,
    )

    try:
        client = await GlideClient.create(config)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        print("=== Dify Vector Store Simulation ===\n")

        # 1. Create FT index
        print("1. Creating FT index...")
        try:
            await client.custom_command(["FT.DROPINDEX", INDEX_NAME])
        except Exception:
            pass  # Index might not exist

        await client.custom_command([
            "FT.CREATE", INDEX_NAME,
            "ON", "HASH",
            "PREFIX", "1", PREFIX,
            "SCHEMA",
            "vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(VECTOR_DIM),
            "DISTANCE_METRIC", "COSINE",
            "group_id", "TAG",
            "doc_id", "TAG",
            "document_id", "TAG",
            "page_content", "TEXT",
        ])
        print(f"   ✅ Index created: {INDEX_NAME}")

        # 2. Store documents
        print("\n2. Storing documents...")
        documents = [
            ("chunk_001", [1.0, 0.0, 0.0, 0.0], "Valkey is an open-source in-memory data store."),
            ("chunk_002", [0.0, 1.0, 0.0, 0.0], "Python is a versatile programming language."),
            ("chunk_003", [0.8, 0.2, 0.0, 0.0], "Valkey supports vector similarity search via modules."),
        ]

        for doc_id, embedding, content in documents:
            key = f"{PREFIX}{doc_id}"
            await client.hset(key, {
                "vector": float_vector_to_bytes(embedding),
                "page_content": content,
                "metadata": json.dumps({"doc_id": doc_id, "source": "demo.pdf"}),
                "group_id": GROUP_ID,
                "doc_id": doc_id,
                "document_id": "file_demo",
            })
            print(f"   ✅ Stored: {key}")

        # 3. KNN vector search
        print("\n3. KNN vector search (query similar to 'Valkey' docs)...")
        query_vector = float_vector_to_bytes([0.9, 0.1, 0.0, 0.0])
        query = f"(@group_id:{{{escape_tag(GROUP_ID)}}})=>[KNN 3 @vector $query_vector]"

        result = await client.custom_command([
            "FT.SEARCH", INDEX_NAME, query,
            "PARAMS", "2", "query_vector", query_vector,
            "LIMIT", "0", "3",
            "RETURN", "2", "page_content", "__vector_score",
        ])

        total = int(result[0])
        print(f"   Found {total} results:")
        # Parse results: [total, key1, [field, val, ...], key2, ...]
        i = 1
        while i < len(result):
            key = to_str(result[i])
            i += 1
            if i < len(result) and isinstance(result[i], list):
                fields = result[i]
                field_dict = {}
                for j in range(0, len(fields), 2):
                    fname = to_str(fields[j])
                    fval = to_str(fields[j + 1])
                    field_dict[fname] = fval
                score = field_dict.get("__vector_score", "?")
                content = field_dict.get("page_content", "")
                print(f"   [distance={score}] {key}: {content[:60]}")
                i += 1

        # 4. Full-text search
        print("\n4. Full-text search for 'Valkey'...")
        ft_query = f"@group_id:{{{escape_tag(GROUP_ID)}}} @page_content:Valkey"
        result = await client.custom_command([
            "FT.SEARCH", INDEX_NAME, ft_query,
            "LIMIT", "0", "10",
            "RETURN", "1", "page_content",
        ])

        total = int(result[0])
        print(f"   Found {total} results matching 'Valkey'")

        # 5. Delete by group (using ft.search from glide module)
        print("\n5. Deleting all documents in group...")
        from glide.async_commands.server_modules import ft
        from glide.async_commands.server_modules.ft_options.ft_search_options import (
            FtSearchLimit,
            FtSearchOptions,
        )

        del_query = f"@group_id:{{{escape_tag(GROUP_ID)}}}"
        opts = FtSearchOptions(
            return_fields=[],
            limit=FtSearchLimit(offset=0, count=100),
        )
        search_result = await ft.search(client, INDEX_NAME, del_query, opts)
        keys_to_delete = [
            k.decode() if isinstance(k, bytes) else str(k)
            for k in search_result[1].keys()
        ]
        if keys_to_delete:
            await client.delete(keys_to_delete)
            print(f"   ✅ Deleted {len(keys_to_delete)} documents")

        # 6. Drop index
        print("\n6. Dropping index...")
        await client.custom_command(["FT.DROPINDEX", INDEX_NAME])
        print(f"   ✅ Index dropped: {INDEX_NAME}")

        print("\n✅ Simulation complete — all Dify vector store patterns demonstrated.")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
