#!/usr/bin/env python3
"""Test script for aiohttp async demo app."""

import asyncio
import json

import aiohttp

BASE_URL = "http://localhost:5001"


async def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
    print("✓ Health check passed")


async def test_create_index():
    """Test index creation."""
    print("\nTesting index creation...")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/index/create",
            json={"index_name": "test_idx", "dimensions": 3},
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["status"] in ["created", "exists"]
            print(f"✓ Index creation: {result['status']}")


async def test_recreate_index():
    """Test index recreation (delete + create)."""
    print("\nTesting index recreation...")
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{BASE_URL}/index/test_idx",
            json={"dimensions": 3},
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["status"] == "recreated"
            print(f"✓ Index recreated: {result['index']}")


async def test_delete_index():
    """Test index deletion."""
    print("\nTesting index deletion...")
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{BASE_URL}/index/test_idx") as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["status"] == "deleted"
            print(f"✓ Index deleted: {result['index']}")


async def test_add_documents():
    """Test adding documents."""
    print("\nTesting document addition...")
    docs = [
        {"id": "doc1", "embedding": [0.1, 0.2, 0.3], "category": "tech"},
        {"id": "doc2", "embedding": [0.2, 0.3, 0.4], "category": "science"},
        {"id": "doc3", "embedding": [0.1, 0.3, 0.5], "category": "tech"},
    ]

    async with aiohttp.ClientSession() as session:
        for doc in docs:
            async with session.post(f"{BASE_URL}/document", json=doc) as resp:
                assert resp.status == 200
                print(f"✓ Added {doc['id']}")

    # Wait for indexing
    await asyncio.sleep(1)


async def test_search():
    """Test vector search."""
    print("\nTesting vector search...")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/search",
            json={"index_name": "test_idx", "vector": [0.1, 0.2, 0.3], "k": 3},
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            print(f"✓ Found {result['count']} results")
            if result["count"] > 0:
                print(f"  Results: {json.dumps(result['results'], indent=2)}")


async def test_search_with_filter():
    """Test vector search with metadata filter."""
    print("\nTesting search with filter...")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/search",
            json={
                "index_name": "test_idx",
                "vector": [0.1, 0.2, 0.3],
                "k": 3,
                "filter": "@category:{tech}",
            },
        ) as resp:
            assert resp.status == 200
            result = await resp.json()
            print(f"✓ Found {result['count']} tech results")


async def test_index_info():
    """Test index info endpoint."""
    print("\nTesting index info...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/index/info/test_idx") as resp:
            assert resp.status == 200
            print("✓ Index info retrieved")


async def main():
    print("=" * 60)
    print("Aiohttp Async Demo Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("1. Valkey running: docker run -d -p 6379:6379 valkey/valkey:latest")
    print("2. Aiohttp app running: python app.py")
    print()

    try:
        # Check if app is running
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    pass
        except (aiohttp.ClientError, asyncio.TimeoutError):
            print("✗ Error: Aiohttp app not running at http://localhost:5001")
            print("  Start it with: python app.py")
            return

        await test_health()
        await test_create_index()
        await test_add_documents()
        await test_search()
        await test_search_with_filter()
        await test_index_info()
        await test_delete_index()
        await test_recreate_index()
        await test_add_documents()  # Re-add after recreate
        await test_search()  # Verify search works after recreate
        await test_delete_index()  # Final cleanup

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
