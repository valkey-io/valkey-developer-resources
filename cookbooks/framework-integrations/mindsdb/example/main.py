"""
MindsDB + Valkey Vector Store — Cookbook Example

Demonstrates the full lifecycle of the Valkey vector store handler:
1. Connect to Valkey
2. Create a vector index
3. Insert documents with embeddings
4. KNN vector similarity search
5. ID-based lookup
6. Delete documents
7. Drop the index

Usage:
    python main.py

Requires:
    - Valkey running locally with search module (port 6379)
    - pip install valkey-glide numpy
"""

from __future__ import annotations

import sys
import os

import numpy as np
import pandas as pd

# Add the project root to path so we can import the handler
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from mindsdb.integrations.handlers.valkey_handler.valkey_handler import ValkeyHandler
from mindsdb.integrations.libs.vectordatabase_handler import (
    FilterCondition,
    FilterOperator,
    TableField,
)


# Configuration
VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
VECTOR_DIM = 384
INDEX_NAME = "cookbook_demo"


def main():
    print("=" * 60)
    print("MindsDB + Valkey Vector Store — Cookbook Demo")
    print("=" * 60)

    # ─── Step 1: Connect ─────────────────────────────────────────
    print("\n▶ Step 1: Connecting to Valkey...")
    handler = ValkeyHandler(
        name="cookbook_valkey",
        connection_data={
            "host": VALKEY_HOST,
            "port": VALKEY_PORT,
            "vector_dimension": VECTOR_DIM,
            "distance_metric": "COSINE",
            "prefix": "doc:",
        },
    )

    status = handler.check_connection()
    if not status.success:
        print(f"  ✗ Connection failed: {status.error_message}")
        sys.exit(1)
    print("  ✓ Connected to Valkey!")

    # ─── Step 2: Create Index ────────────────────────────────────
    print("\n▶ Step 2: Creating vector index...")
    handler.create_table(INDEX_NAME, if_not_exists=True)
    print(f"  ✓ Index '{INDEX_NAME}' ready")

    # List all indexes
    tables = handler.get_tables()
    print(f"  Available indexes: {tables.data_frame['table_name'].tolist()}")

    # ─── Step 3: Insert Documents ────────────────────────────────
    print("\n▶ Step 3: Inserting documents with embeddings...")
    documents = [
        {
            "id": "doc_001",
            "content": "Valkey is a high-performance in-memory data store that supports vector similarity search.",
            "metadata": {"source": "valkey_docs", "category": "overview"},
        },
        {
            "id": "doc_002",
            "content": "HNSW indexes provide approximate nearest neighbor search with sub-millisecond latency.",
            "metadata": {"source": "valkey_docs", "category": "indexing"},
        },
        {
            "id": "doc_003",
            "content": "MindsDB brings machine learning into databases using a SQL-like interface.",
            "metadata": {"source": "mindsdb_docs", "category": "overview"},
        },
        {
            "id": "doc_004",
            "content": "The valkey-glide client uses a Rust core for high-throughput async operations.",
            "metadata": {"source": "valkey_docs", "category": "client"},
        },
        {
            "id": "doc_005",
            "content": "Knowledge bases in MindsDB use vector stores for semantic document retrieval.",
            "metadata": {"source": "mindsdb_docs", "category": "rag"},
        },
    ]

    # Generate random embeddings (in production, use a real embedding model)
    np.random.seed(42)
    for doc in documents:
        doc["embeddings"] = np.random.randn(VECTOR_DIM).astype(np.float32).tolist()

    df = pd.DataFrame(documents)
    handler.insert(INDEX_NAME, df)
    print(f"  ✓ Inserted {len(documents)} documents")

    # ─── Step 4: KNN Vector Search ───────────────────────────────
    print("\n▶ Step 4: KNN vector similarity search...")
    # Use doc_001's vector as query (should return doc_001 as closest match)
    query_vector = documents[0]["embeddings"]

    conditions = [
        FilterCondition(
            column=TableField.SEARCH_VECTOR.value,
            op=FilterOperator.EQUAL,
            value=query_vector,
        )
    ]

    results = handler.select(
        table_name=INDEX_NAME,
        columns=["id", "content", "distance"],
        conditions=conditions,
        limit=3,
    )

    print(f"  Top 3 results:")
    for _, row in results.iterrows():
        distance = row.get("distance", "N/A")
        dist_str = f"{distance:.4f}" if isinstance(distance, (int, float)) else str(distance)
        print(f"    [{dist_str}] {row['id']}: {row['content'][:60]}...")

    # ─── Step 5: ID Lookup ───────────────────────────────────────
    print("\n▶ Step 5: Looking up documents by ID...")

    # Single ID lookup
    conditions = [
        FilterCondition(
            column=TableField.ID.value,
            op=FilterOperator.EQUAL,
            value="doc_002",
        )
    ]
    result = handler.select(
        table_name=INDEX_NAME,
        columns=["id", "content", "metadata"],
        conditions=conditions,
    )
    if not result.empty:
        print(f"  Single: {result.iloc[0]['id']} → {result.iloc[0]['content'][:50]}...")

    # Batch ID lookup
    conditions = [
        FilterCondition(
            column=TableField.ID.value,
            op=FilterOperator.IN,
            value=["doc_001", "doc_003", "doc_005"],
        )
    ]
    results = handler.select(
        table_name=INDEX_NAME,
        columns=["id", "content"],
        conditions=conditions,
    )
    print(f"  Batch ({len(results)} found):")
    for _, row in results.iterrows():
        print(f"    {row['id']}: {row['content'][:50]}...")

    # ─── Step 6: Delete Documents ────────────────────────────────
    print("\n▶ Step 6: Deleting documents...")

    # Delete single
    conditions = [
        FilterCondition(
            column=TableField.ID.value,
            op=FilterOperator.EQUAL,
            value="doc_005",
        )
    ]
    handler.delete(INDEX_NAME, conditions)
    print("  ✓ Deleted doc_005")

    # Delete multiple
    conditions = [
        FilterCondition(
            column=TableField.ID.value,
            op=FilterOperator.IN,
            value=["doc_003", "doc_004"],
        )
    ]
    handler.delete(INDEX_NAME, conditions)
    print("  ✓ Deleted doc_003 and doc_004")

    # Verify remaining (search with doc_001's vector)
    conditions = [
        FilterCondition(
            column=TableField.SEARCH_VECTOR.value,
            op=FilterOperator.EQUAL,
            value=query_vector,
        )
    ]
    results = handler.select(
        table_name=INDEX_NAME,
        columns=["id"],
        conditions=conditions,
        limit=10,
    )
    print(f"  Remaining documents: {results['id'].tolist()}")

    # ─── Step 7: Drop Index ──────────────────────────────────────
    print("\n▶ Step 7: Dropping index...")
    handler.drop_table(INDEX_NAME)
    print(f"  ✓ Dropped index '{INDEX_NAME}' and all its documents")

    # Verify
    tables = handler.get_tables()
    remaining = tables.data_frame["table_name"].tolist()
    assert INDEX_NAME not in remaining, f"Index still exists: {remaining}"
    print(f"  ✓ Verified: index no longer listed")

    # ─── Cleanup ─────────────────────────────────────────────────
    handler.disconnect()
    print("\n" + "=" * 60)
    print("All steps completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
