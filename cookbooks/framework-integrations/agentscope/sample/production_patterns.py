# -*- coding: utf-8 -*-
"""Cookbook 03 - Production Patterns with AgentScope + Valkey.

Demonstrates: HNSW tuning, metadata filtering, batch ingestion,
and connection lifecycle management.

Prerequisites:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    pip install agentscope[valkey]
"""

from __future__ import annotations

import asyncio
import random
import time

from agentscope.message import TextBlock
from agentscope.rag import Document, DocMetadata, ValkeyStore


def make_document(doc_id: str, chunk_id: int, dimensions: int) -> Document:
    """Create a document with a random embedding."""
    return Document(
        embedding=[random.uniform(-1, 1) for _ in range(dimensions)],
        metadata=DocMetadata(
            content=TextBlock(
                type="text",
                text=f"Document {doc_id}, chunk {chunk_id}.",
            ),
            doc_id=doc_id,
            chunk_id=chunk_id,
            total_chunks=10,
        ),
    )


async def demo_hnsw_tuning() -> None:
    """Demonstrate HNSW parameter configuration."""
    print("--- HNSW Tuning ---\n")

    # High-recall configuration
    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="hnsw_tuning_idx",
        prefix="hnsw:doc:",
        dimensions=64,
        distance="COSINE",
        hnsw_m=16,
        hnsw_ef_construction=200,
        hnsw_ef_runtime=20,
        initial_cap=100,
    )

    print("Created store with high-recall HNSW config:")
    print(f"  M={store.hnsw_m}, ef_construction={store.hnsw_ef_construction}, "
          f"ef_runtime={store.hnsw_ef_runtime}")

    # Ingest some documents
    docs = [make_document("tuning-doc", i, 64) for i in range(50)]
    await store.add(docs)
    print(f"  Stored {len(docs)} documents")

    await asyncio.sleep(0.5)

    # Search
    query_vec = [random.uniform(-1, 1) for _ in range(64)]
    results = await store.search(query_embedding=query_vec, limit=5)
    print(f"  Search returned {len(results)} results\n")

    await store.drop_index()
    await store.close()


async def demo_metadata_filtering() -> None:
    """Demonstrate metadata filtering on search."""
    print("--- Metadata Filtering ---\n")

    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="filter_demo_idx",
        prefix="filter:doc:",
        dimensions=8,
        distance="COSINE",
    )

    # Add documents from multiple sources
    docs = []
    for doc_id in ["user_manual", "api_reference", "changelog"]:
        for chunk_id in range(5):
            docs.append(make_document(doc_id, chunk_id, 8))

    await store.add(docs)
    print(f"Stored {len(docs)} documents across 3 doc_ids")
    await asyncio.sleep(0.5)

    query_vec = [random.uniform(-1, 1) for _ in range(8)]

    # Unfiltered search
    results = await store.search(query_embedding=query_vec, limit=10)
    doc_ids = {r.metadata.doc_id for r in results}
    print(f"\nUnfiltered search: {len(results)} results from {doc_ids}")

    # Filter by single doc_id
    results = await store.search(
        query_embedding=query_vec,
        limit=10,
        filter_expression="@doc_id:{user_manual}",
    )
    print(f"Filter @doc_id:{{user_manual}}: {len(results)} results")

    # Filter by multiple doc_ids (run separate queries per doc_id)
    results_combined = []
    for did in ["user_manual", "api_reference"]:
        r = await store.search(
            query_embedding=query_vec,
            limit=10,
            filter_expression=f"@doc_id:{{{did}}}",
        )
        results_combined.extend(r)
    doc_ids = {r.metadata.doc_id for r in results_combined}
    print(f"Filter user_manual + api_reference: "
          f"{len(results_combined)} results from {doc_ids}")

    # Filter by chunk range
    results = await store.search(
        query_embedding=query_vec,
        limit=10,
        filter_expression="@chunk_id:[0 2]",
    )
    chunk_ids = {r.metadata.chunk_id for r in results}
    print(f"Filter @chunk_id:[0 2]: {len(results)} results, "
          f"chunks={sorted(chunk_ids)}\n")

    await store.drop_index()
    await store.close()


async def demo_batch_ingestion() -> None:
    """Demonstrate batch ingestion with timing."""
    print("--- Batch Ingestion ---\n")

    store = ValkeyStore(
        host="localhost",
        port=6379,
        index_name="batch_demo_idx",
        prefix="batch:doc:",
        dimensions=128,
        distance="COSINE",
        initial_cap=500,
    )

    total_docs = 500
    batch_size = 100
    all_docs = [make_document(f"batch-{i // 10}", i % 10, 128) for i in range(total_docs)]

    start = time.perf_counter()
    for i in range(0, total_docs, batch_size):
        batch = all_docs[i:i + batch_size]
        await store.add(batch)
        print(f"  Ingested {min(i + batch_size, total_docs)}/{total_docs}")

    elapsed = time.perf_counter() - start
    print(f"\nIngested {total_docs} documents in {elapsed:.2f}s "
          f"({total_docs / elapsed:.0f} docs/sec)\n")

    await store.drop_index()
    await store.close()


async def main() -> None:
    """Run all production pattern demos."""
    print("=== AgentScope + Valkey Production Patterns ===\n")

    await demo_hnsw_tuning()
    await demo_metadata_filtering()
    await demo_batch_ingestion()

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
