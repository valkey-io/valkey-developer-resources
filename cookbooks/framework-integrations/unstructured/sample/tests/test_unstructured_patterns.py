"""Integration tests for Unstructured + Valkey patterns.

Tests the core Valkey patterns used by the unstructured-ingest connector:
- Hash storage with vector embeddings
- HNSW index creation
- KNN vector search
- Incremental upload (idempotent overwrites)
- TTL on uploaded keys

Requires Valkey with Search module on localhost:6379.
"""

import asyncio

import numpy as np
import pytest
from glide import (
    FtCreateOptions,
    FtSearchLimit,
    FtSearchOptions,
    RequestError,
    ft,
)

from conftest import (
    DIMENSION,
    INDEX_NAME,
    INDEX_PREFIX,
    random_vector,
    vector_to_bytes,
    wait_for_indexed,
)


@pytest.fixture(autouse=True)
async def cleanup_after_test(client):
    """Drop test index and delete test keys after each test."""
    yield
    # Cleanup index
    try:
        await ft.dropindex(client, INDEX_NAME)
    except RequestError:
        pass
    # Cleanup keys (scan for test prefix)
    cursor = b"0"
    while True:
        result = await client.scan(cursor, match=f"{INDEX_PREFIX}*", count=100)
        cursor = result[0]
        keys = result[1]
        if keys:
            await client.delete(keys)
        if cursor == b"0":
            break


@pytest.mark.asyncio
async def test_store_document_hash(client):
    """Test storing a document chunk as a Valkey hash."""
    key = f"{INDEX_PREFIX}elem_001"
    embedding = random_vector()

    fields = {
        "text": "Valkey supports vector similarity search.",
        "element_type": "NarrativeText",
        "source_document": "test.pdf",
        "page_number": "1",
        "record_id": "ingest-test",
        "embedding": vector_to_bytes(embedding),
    }

    await client.hset(key, fields)

    # Verify stored data
    result = await client.hgetall(key)
    decoded = {k.decode(): v for k, v in result.items()}

    assert decoded["text"].decode() == "Valkey supports vector similarity search."
    assert decoded["element_type"].decode() == "NarrativeText"
    assert decoded["source_document"].decode() == "test.pdf"

    # Verify embedding roundtrip
    stored_vec = np.frombuffer(decoded["embedding"], dtype=np.float32)
    expected_vec = np.array(embedding, dtype=np.float32)
    assert np.allclose(stored_vec, expected_vec, atol=1e-6)


@pytest.mark.asyncio
async def test_create_hnsw_index(client, create_hnsw_index):
    """Test creating an HNSW vector index."""
    await create_hnsw_index(client)

    # Verify index exists via FT._LIST
    indexes = await ft.list(client)
    index_names = [
        idx.decode() if isinstance(idx, bytes) else idx for idx in indexes
    ]
    assert INDEX_NAME in index_names


@pytest.mark.asyncio
async def test_knn_vector_search(client, create_hnsw_index):
    """Test KNN search returns nearest neighbors."""
    # Store 5 documents with known vectors
    base_vec = random_vector()
    for i in range(5):
        key = f"{INDEX_PREFIX}search_{i:03d}"
        # Create vectors with increasing distance from base
        noise = np.random.default_rng(i).standard_normal(DIMENSION).astype(np.float32) * 0.1 * i
        vec = (np.array(base_vec, dtype=np.float32) + noise)
        vec = vec / np.linalg.norm(vec)

        await client.hset(key, {
            "text": f"Document chunk {i}",
            "element_type": "NarrativeText",
            "source_document": "test.pdf",
            "page_number": str(i),
            "record_id": "ingest-test",
            "embedding": vector_to_bytes(vec.tolist()),
        })

    # Create index
    await create_hnsw_index(client)
    await wait_for_indexed(client, INDEX_NAME, expected_docs=5)

    # Search with base vector (should find closest match)
    query_bytes = vector_to_bytes(base_vec)
    knn_query = f"*=>[KNN 3 @embedding $query_vec AS score]"
    options = FtSearchOptions(
        limit=FtSearchLimit(offset=0, count=3),
        params={"query_vec": query_bytes},
    )

    results = await ft.search(client, INDEX_NAME, knn_query, options)
    total = results[0]
    docs = results[1]

    assert total >= 3
    assert len(docs) == 3

    # First result should be closest (lowest score for cosine)
    scores = []
    for key, fields in docs.items():
        score = float(fields.get(b"score", b"0").decode())
        scores.append(score)

    # Scores should be in ascending order (closest first)
    assert scores == sorted(scores)


@pytest.mark.asyncio
async def test_idempotent_upload(client, create_hnsw_index):
    """Test that uploading same element_id twice overwrites, not duplicates."""
    key = f"{INDEX_PREFIX}idem_001"
    embedding = random_vector()

    # First upload
    await client.hset(key, {
        "text": "Original text",
        "element_type": "NarrativeText",
        "source_document": "test.pdf",
        "page_number": "1",
        "record_id": "ingest-test",
        "embedding": vector_to_bytes(embedding),
    })

    # Second upload (same key, different text)
    await client.hset(key, {
        "text": "Updated text",
        "element_type": "NarrativeText",
        "source_document": "test.pdf",
        "page_number": "1",
        "record_id": "ingest-test",
        "embedding": vector_to_bytes(embedding),
    })

    # Verify only one key exists and text is updated
    result = await client.hgetall(key)
    decoded = {k.decode(): v for k, v in result.items()}
    assert decoded["text"].decode() == "Updated text"

    # Verify no duplicates via scan
    cursor = b"0"
    all_keys = []
    while True:
        cursor_result = await client.scan(cursor, match=f"{INDEX_PREFIX}idem_*", count=100)
        cursor = cursor_result[0]
        all_keys.extend(cursor_result[1])
        if cursor == b"0":
            break
    assert len(all_keys) == 1


@pytest.mark.asyncio
async def test_ttl_on_keys(client):
    """Test that TTL can be set on document keys."""
    key = f"{INDEX_PREFIX}ttl_001"
    embedding = random_vector()

    await client.hset(key, {
        "text": "Temporary document",
        "element_type": "NarrativeText",
        "source_document": "temp.pdf",
        "page_number": "1",
        "record_id": "ingest-temp",
        "embedding": vector_to_bytes(embedding),
    })

    # Set TTL (3600 seconds = 1 hour)
    await client.expire(key, 3600)

    # Verify TTL is set
    ttl = await client.ttl(key)
    assert ttl > 0
    assert ttl <= 3600


@pytest.mark.asyncio
async def test_batch_upload(client, create_hnsw_index):
    """Test uploading multiple documents in a batch."""
    num_docs = 10
    keys = []

    for i in range(num_docs):
        key = f"{INDEX_PREFIX}batch_{i:03d}"
        keys.append(key)
        embedding = random_vector()

        await client.hset(key, {
            "text": f"Batch document {i} about topic {i % 3}",
            "element_type": "NarrativeText",
            "source_document": f"batch_{i // 5}.pdf",
            "page_number": str(i % 5),
            "record_id": f"ingest-batch_{i // 5}",
            "embedding": vector_to_bytes(embedding),
        })

    # Create index and wait
    await create_hnsw_index(client)
    await wait_for_indexed(client, INDEX_NAME, expected_docs=num_docs)

    # Verify all documents are searchable
    query_vec = random_vector()
    knn_query = f"*=>[KNN {num_docs} @embedding $query_vec AS score]"
    options = FtSearchOptions(
        limit=FtSearchLimit(offset=0, count=num_docs),
        params={"query_vec": vector_to_bytes(query_vec)},
    )

    results = await ft.search(client, INDEX_NAME, knn_query, options)
    total = results[0]
    assert total == num_docs


@pytest.mark.asyncio
async def test_tag_field_search(client, create_hnsw_index):
    """Test filtering by tag field (element_type, source_document)."""
    # Store docs with different types
    for i, etype in enumerate(["NarrativeText", "Title", "NarrativeText"]):
        key = f"{INDEX_PREFIX}tag_{i:03d}"
        await client.hset(key, {
            "text": f"Content {i}",
            "element_type": etype,
            "source_document": "test.pdf",
            "page_number": str(i),
            "record_id": "ingest-test",
            "embedding": vector_to_bytes(random_vector()),
        })

    await create_hnsw_index(client)
    await wait_for_indexed(client, INDEX_NAME, expected_docs=3)

    # Search for only NarrativeText elements
    query_vec = vector_to_bytes(random_vector())
    knn_query = "@element_type:{NarrativeText}=>[KNN 10 @embedding $query_vec AS score]"
    options = FtSearchOptions(
        limit=FtSearchLimit(offset=0, count=10),
        params={"query_vec": query_vec},
    )

    results = await ft.search(client, INDEX_NAME, knn_query, options)
    total = results[0]
    assert total == 2  # Only NarrativeText elements


@pytest.mark.asyncio
async def test_index_already_exists(client, create_hnsw_index):
    """Test that creating a duplicate index raises RequestError."""
    await create_hnsw_index(client)

    # Try creating again — should raise "Index already exists"
    with pytest.raises(RequestError, match="already exists"):
        await create_hnsw_index(client)
