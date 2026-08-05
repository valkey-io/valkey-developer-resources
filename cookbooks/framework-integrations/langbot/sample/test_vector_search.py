"""Tests for the LangBot + Valkey Search vector backend.

Requires:
    - Valkey Bundle running (search module loaded)

Uses the same deterministic word-hash embedding as vector_search.py — no
Ollama, no model downloads, no API keys needed. Each test operates on its own
collection (derived from the test name) so tests have no ordering
dependencies and can run in isolation (`pytest -k test_name`) or shuffled.
"""

from __future__ import annotations

import asyncio

import pytest

from vector_search import (
    add_documents,
    create_client,
    delete_by_file_id,
    delete_collection,
    embed,
    full_text_search,
    hybrid_search,
    poll_until,
    vector_search,
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def collection(request) -> str:
    # One collection per test, isolated by test name — no shared state,
    # no ordering dependency between tests. Cleanup happens inside each
    # test's own asyncio.run() call (see `scenario()` below), not in fixture
    # teardown: awaiting a GLIDE client from post-yield fixture teardown code
    # hangs the pytest process on exit, even though the exact same call
    # completes fine from a plain script or from within a test body.
    return f"test_{request.node.name}"


DOCS = [
    "Valkey is a high performance in-memory data store",
    "Vector search finds similar embeddings using KNN",
    "LangBot builds agentic instant messaging bots",
    "Rate limiting protects services from request floods",
]
IDS = [f"chunk-{i}" for i in range(len(DOCS))]
FILE_IDS = ["fileA", "fileA", "fileB", "fileB"]


async def _seed(client, collection: str) -> None:
    # Idempotent: clear any leftovers from a prior interrupted run.
    await delete_collection(client, collection)
    await add_documents(client, collection, IDS, DOCS, FILE_IDS)


def test_vector_search_ranks_most_similar_first(collection: str):
    async def scenario():
        client = await create_client()
        try:
            await _seed(client, collection)
            hits = await poll_until(
                lambda: vector_search(client, collection, "similar vector embeddings", k=3),
                predicate=lambda r: len(r) > 0,
            )
            assert hits, "vector search returned no results (indexing lag?)"
            # The embeddings doc shares the most query words -> should rank first.
            assert hits[0]["id"] == "chunk-1"
            assert hits[0]["distance"] is not None
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_full_text_search_matches_term(collection: str):
    async def scenario():
        client = await create_client()
        try:
            await _seed(client, collection)
            hits = await poll_until(
                lambda: full_text_search(client, collection, "bots", k=5),
                predicate=lambda r: len(r) > 0,
            )
            assert any(h["id"] == "chunk-2" for h in hits), "expected the LangBot doc"
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_full_text_search_no_terms_returns_empty(collection: str):
    async def scenario():
        client = await create_client()
        try:
            await _seed(client, collection)
            hits = await full_text_search(client, collection, "", k=5)
            assert hits == []
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_hybrid_search_filters_by_file_id(collection: str):
    async def scenario():
        client = await create_client()
        try:
            await _seed(client, collection)
            hits = await poll_until(
                lambda: hybrid_search(client, collection, "messaging bots", file_id="fileB", k=5),
                predicate=lambda r: len(r) > 0,
            )
            assert hits, "hybrid search returned no results"
            assert all(h["id"] in ("chunk-2", "chunk-3") for h in hits), "filter leaked outside fileB"
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_delete_by_file_id_removes_only_matching_chunks(collection: str):
    async def scenario():
        client = await create_client()
        try:
            await _seed(client, collection)
            # Wait for the initial write to be indexed before deleting.
            await poll_until(
                lambda: vector_search(client, collection, "data store", k=5),
                predicate=lambda r: len(r) > 0,
            )

            removed = await delete_by_file_id(client, collection, "fileA")
            assert removed == 2

            remaining = await poll_until(
                lambda: hybrid_search(client, collection, "data store", file_id="fileA", k=5),
                predicate=lambda r: len(r) == 0,
            )
            assert remaining == [], "fileA chunks still present after delete"

            # fileB chunks must survive the fileA-scoped delete.
            still_there = await hybrid_search(client, collection, "bots", file_id="fileB", k=5)
            assert any(h["id"] == "chunk-2" for h in still_there)
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_delete_by_file_id_with_tag_unsafe_characters(collection: str):
    # file_id_filter() percent-encodes {, }, *, % on the query side. This only
    # round-trips correctly if add_documents() stores the file_id through the
    # same encoding — regression coverage for that write/query consistency.
    async def scenario():
        client = await create_client()
        try:
            await delete_collection(client, collection)
            weird_id = "file{special}*id%"
            await add_documents(client, collection, ["chunk-0"], [DOCS[0]], [weird_id])

            hits = await poll_until(
                lambda: hybrid_search(client, collection, "data store", file_id=weird_id, k=5),
                predicate=lambda r: len(r) > 0,
            )
            assert hits, "file_id containing {, }, *, % never matched its own filter"

            removed = await delete_by_file_id(client, collection, weird_id)
            assert removed == 1
        finally:
            await delete_collection(client, collection)
            await client.close()

    run(scenario())


def test_delete_by_file_id_on_nonexistent_index_returns_zero(collection: str):
    async def scenario():
        client = await create_client()
        try:
            # No add_documents call — the index for this collection never gets created.
            removed = await delete_by_file_id(client, collection, "fileA")
            assert removed == 0
        finally:
            await client.close()

    run(scenario())


def test_embed_is_deterministic_and_normalized():
    vec_a = embed("valkey vector search")
    vec_b = embed("valkey vector search")
    assert vec_a == vec_b

    norm = sum(x * x for x in vec_a) ** 0.5
    assert abs(norm - 1.0) < 1e-6
