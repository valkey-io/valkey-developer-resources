#!/usr/bin/env python3
"""Test script for Flask demo app."""

import json
import time
import requests

BASE_URL = "http://localhost:5000"


def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("✓ Health check passed")


def test_create_index():
    """Test index creation."""
    print("\nTesting index creation...")
    resp = requests.post(
        f"{BASE_URL}/index/create",
        json={"index_name": "test_idx", "dimensions": 3},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] in ["created", "exists"]
    print(f"✓ Index creation: {result['status']}")


def test_add_documents():
    """Test adding documents."""
    print("\nTesting document addition...")
    docs = [
        {"id": "doc1", "embedding": [0.1, 0.2, 0.3], "category": "tech"},
        {"id": "doc2", "embedding": [0.2, 0.3, 0.4], "category": "science"},
        {"id": "doc3", "embedding": [0.1, 0.3, 0.5], "category": "tech"},
    ]

    for doc in docs:
        resp = requests.post(f"{BASE_URL}/document", json=doc)
        assert resp.status_code == 200
        print(f"✓ Added {doc['id']}")

    # Wait for indexing
    time.sleep(1)


def test_search():
    """Test vector search."""
    print("\nTesting vector search...")
    resp = requests.post(
        f"{BASE_URL}/search",
        json={"index_name": "test_idx", "vector": [0.1, 0.2, 0.3], "k": 3},
    )
    assert resp.status_code == 200
    result = resp.json()
    print(f"✓ Found {result['count']} results")
    if result["count"] > 0:
        print(f"  Results: {json.dumps(result['results'], indent=2)}")


def test_search_with_filter():
    """Test vector search with metadata filter."""
    print("\nTesting search with filter...")
    resp = requests.post(
        f"{BASE_URL}/search",
        json={
            "index_name": "test_idx",
            "vector": [0.1, 0.2, 0.3],
            "k": 3,
            "filter": "@category:{tech}",
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    print(f"✓ Found {result['count']} tech results")


def test_index_info():
    """Test index info endpoint."""
    print("\nTesting index info...")
    resp = requests.get(f"{BASE_URL}/index/info/test_idx")
    assert resp.status_code == 200
    print("✓ Index info retrieved")


if __name__ == "__main__":
    print("=" * 60)
    print("Flask Demo Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("1. Valkey running: docker run -d -p 6379:6379 valkey/valkey:latest")
    print("2. Flask app running: python app.py")
    print()

    try:
        # Check if Flask app is running
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
        except requests.exceptions.ConnectionError:
            print("✗ Error: Flask app not running at http://localhost:5000")
            print("  Start it with: python app.py")
            exit(1)

        test_health()
        test_create_index()
        test_add_documents()
        test_search()
        test_search_with_filter()
        test_index_info()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise
