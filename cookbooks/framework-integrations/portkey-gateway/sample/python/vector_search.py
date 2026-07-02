"""Portkey AI Gateway + Valkey vector search — full CRUD via the Portkey SDK.

Corresponds to cookbook: 02-vector-search.md

Uses the official `portkey-ai` SDK with the valkey-search provider. The custom
vector endpoints are reached through the SDK's generic post/get/delete methods.

Tests:
  1. Create an HNSW vector index
  2. Upsert documents with embeddings
  3. KNN vector search
  4. Filtered search with TAG
  5. Drop index
"""

from __future__ import annotations

import os
import time

try:
    from dotenv import load_dotenv
    from portkey_ai import Portkey
except ImportError:
    raise SystemExit(
        "Missing dependency: portkey-ai\n"
        "Install first: pip install -r requirements.txt"
    )

load_dotenv()

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8787") + "/v1"
VALKEY_HOST = os.environ.get("VALKEY_CUSTOM_HOST", "valkey://localhost:6379")
INDEX_NAME = "sample-docs"

client = Portkey(
    api_key="dummy",
    base_url=GATEWAY_URL,
    provider="valkey-search",
    custom_host=VALKEY_HOST,
)


def create_index() -> None:
    resp = client.post(
        "/indexes",
        name=INDEX_NAME,
        schema={
            "vector": {
                "type": "VECTOR",
                "algorithm": "HNSW",
                "dims": 3,  # toy dimension — use 1536 for text-embedding-ada-002, 768 for MiniLM, etc.
                "distance": "COSINE",
            },
            "content": {"type": "TEXT"},
            "source": {"type": "TAG"},
        },
        options={"prefix": f"{INDEX_NAME}:"},
    )
    assert resp.status == "created", f"Unexpected create response: {dict(resp)}"
    print("OK: Create index")


def upsert_documents() -> None:
    resp = client.post(
        f"/indexes/{INDEX_NAME}/upsert",
        documents=[
            {"id": "doc1", "vector": [0.1, 0.2, 0.3],
             "fields": {"content": "Valkey is a high-performance key-value store", "source": "docs"}},
            {"id": "doc2", "vector": [0.4, 0.5, 0.6],
             "fields": {"content": "Vector search finds similar items by embedding distance", "source": "tutorial"}},
            {"id": "doc3", "vector": [0.11, 0.21, 0.31],
             "fields": {"content": "Valkey supports HNSW and FLAT indexing algorithms", "source": "docs"}},
        ],
    )
    statuses = [d["status"] for d in dict(resp)["data"]]
    assert all(s == "upserted" for s in statuses), f"Upsert failed: {statuses}"
    print("OK: Upserted 3 documents")


def search_knn() -> None:
    resp = client.post(
        f"/indexes/{INDEX_NAME}/search",
        vector=[0.12, 0.22, 0.32],  # distinct from stored docs so ranking is non-trivial
        top_k=2,
        return_fields=["content", "source", "__score"],
    )
    count = dict(resp)["data"][0]
    assert count == 2, f"Expected 2 results, got {count}"
    print(f"OK: KNN search returned {count} results")


def search_filtered() -> None:
    resp = client.post(
        f"/indexes/{INDEX_NAME}/search",
        vector=[0.12, 0.22, 0.32],  # distinct from stored docs so ranking is non-trivial
        top_k=5,
        filter="@source:{docs}",
        return_fields=["content", "__score"],
    )
    count = dict(resp)["data"][0]
    assert count == 2, f"Expected 2 filtered results (docs only), got {count}"
    print(f"OK: Filtered search returned {count} results (source:docs only)")


def drop_index() -> None:
    resp = client.delete(path=f"/indexes/{INDEX_NAME}").json()
    assert resp["deleted"] is True
    print("OK: Dropped index")


def drop_index_if_exists() -> None:
    """Remove the index if it exists from a previous run."""
    try:
        client.delete(path=f"/indexes/{INDEX_NAME}")
    except Exception:
        pass  # index didn't exist — safe to ignore


def main() -> None:
    print("=== Cookbook 02: Vector Search ===\n")
    drop_index_if_exists()  # idempotent cleanup so reruns don't fail
    create_index()
    upsert_documents()
    time.sleep(1)  # allow Valkey Search to index — increase on slow machines
    search_knn()
    search_filtered()
    drop_index()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
