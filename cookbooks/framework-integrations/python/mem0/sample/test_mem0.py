"""Integration tests for the Mem0 + Valkey sample.

The tests use Mem0's built-in deterministic MockEmbeddings and infer=False,
so no LLM or embedding service credentials are required.
"""

import os

import pytest

os.environ["MEM0_TELEMETRY"] = "false"

from main import build_memory, reset_memory  # noqa: E402


@pytest.fixture
def memory():
    instance = build_memory("test_mem0")
    reset_memory(instance)
    try:
        yield instance
    finally:
        reset_memory(instance)
        instance.close()


def test_add_search_and_get_all_use_mem0_api(memory):
    result = memory.add(
        [{"role": "user", "content": "Alice prefers Python for data work."}],
        user_id="alice",
        infer=False,
    )

    assert result["results"][0]["event"] == "ADD"

    search_result = memory.search(
        "What language does Alice prefer?",
        filters={"user_id": "alice"},
        threshold=1.0,
    )
    assert search_result["results"][0]["memory"] == "Alice prefers Python for data work."

    all_result = memory.get_all(filters={"user_id": "alice"})
    assert [item["memory"] for item in all_result["results"]] == [
        "Alice prefers Python for data work."
    ]


def test_filters_isolate_users(memory):
    memory.add(
        [{"role": "user", "content": "Alice prefers Python."}],
        user_id="alice",
        infer=False,
    )
    memory.add(
        [{"role": "user", "content": "Bob prefers TypeScript."}],
        user_id="bob",
        infer=False,
    )

    alice_results = memory.search(
        "preferred programming language",
        filters={"user_id": "alice"},
        threshold=1.0,
    )
    bob_results = memory.search(
        "preferred programming language",
        filters={"user_id": "bob"},
        threshold=1.0,
    )

    assert [item["memory"] for item in alice_results["results"]] == [
        "Alice prefers Python."
    ]
    assert [item["memory"] for item in bob_results["results"]] == [
        "Bob prefers TypeScript."
    ]
