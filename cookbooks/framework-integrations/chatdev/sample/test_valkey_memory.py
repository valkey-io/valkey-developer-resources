# -*- coding: utf-8 -*-
"""Tests for the standalone ValkeyMemory sample.

Requires a running Valkey with the Search module:

    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    pytest test_valkey_memory.py -v
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from glide_sync import RequestError

from embeddings import LocalDeterministicEmbedding
from valkey_memory import ValkeyMemory, ValkeyMemoryConfig, sanitize_tag


def unique_config(**overrides) -> ValkeyMemoryConfig:
    suffix = str(time.time_ns())
    defaults = dict(
        index_name=f"test_idx_{suffix}",
        key_prefix=f"test:{suffix}:",
        ttl_seconds=None,
    )
    defaults.update(overrides)
    return ValkeyMemoryConfig(**defaults)


@pytest.fixture
def memory():
    """A ValkeyMemory instance with a unique index/prefix per test, closed after."""
    mem = ValkeyMemory(unique_config())
    try:
        yield mem
    finally:
        mem.close()


# --------------------------------------------------------------------------- #
# Sanitization
# --------------------------------------------------------------------------- #
def test_sanitize_tag_replaces_unsafe_chars():
    unsafe = "a,b{c}d|e<f>g h\ti\nj\rk"
    result = sanitize_tag(unsafe)
    assert result == "a_b_c_d_e_f_g_h_i_j_k"


def test_sanitize_tag_leaves_safe_chars_untouched():
    safe = "coder-agent_01"
    assert sanitize_tag(safe) == safe


# --------------------------------------------------------------------------- #
# Deterministic embedding (no network, no key)
# --------------------------------------------------------------------------- #
def test_local_embedding_is_deterministic_and_correct_dimension():
    provider = LocalDeterministicEmbedding()
    vec1 = provider.get_embedding("hello world")
    vec2 = provider.get_embedding("hello world")
    assert vec1 == vec2
    assert len(vec1) == 64


def test_local_embedding_differs_for_different_text():
    provider = LocalDeterministicEmbedding()
    vec_a = provider.get_embedding("python testing")
    vec_b = provider.get_embedding("completely unrelated astrophysics topic")
    assert vec_a != vec_b


# --------------------------------------------------------------------------- #
# Key format
# --------------------------------------------------------------------------- #
def test_update_returns_key_with_expected_prefix_and_hex_uuid(memory):
    key = memory.update(agent_role="coder", text="test memory")
    assert key.startswith(memory.config.key_prefix)
    suffix = key[len(memory.config.key_prefix):]
    assert len(suffix) == 32
    int(suffix, 16)  # raises ValueError if not valid hex


# --------------------------------------------------------------------------- #
# Query string construction
# --------------------------------------------------------------------------- #
def test_retrieve_builds_filtered_query_string(memory):
    memory.update(agent_role="coder", text="python testing")
    time.sleep(0.2)
    with patch("valkey_memory.ft.search", wraps=__import__("valkey_memory").ft.search) as spy:
        memory.retrieve(agent_role="coder", query_text="python", top_k=2)
        assert spy.call_count == 1
        query_arg = spy.call_args[0][2]
        assert query_arg.startswith("(@agent_role:{coder})=>[KNN 2 @embedding")


def test_retrieve_builds_unfiltered_query_string(memory):
    memory.update(agent_role="coder", text="python testing")
    time.sleep(0.2)
    with patch("valkey_memory.ft.search", wraps=__import__("valkey_memory").ft.search) as spy:
        memory.retrieve(agent_role=None, query_text="python", top_k=2)
        assert spy.call_count == 1
        query_arg = spy.call_args[0][2]
        assert query_arg.startswith("*=>[KNN 2 @embedding")


def test_retrieve_sanitizes_agent_role_in_query(memory):
    memory.update(agent_role="coder", text="python testing")
    time.sleep(0.2)
    with patch("valkey_memory.ft.search", wraps=__import__("valkey_memory").ft.search) as spy:
        memory.retrieve(agent_role="team,lead", query_text="python", top_k=2)
        query_arg = spy.call_args[0][2]
        assert "@agent_role:{team_lead}" in query_arg


# --------------------------------------------------------------------------- #
# Schema / round trip against real Valkey
# --------------------------------------------------------------------------- #
def test_update_and_retrieve_round_trip(memory):
    memory.update(agent_role="coder", text="Python is great for data science")
    memory.update(agent_role="designer", text="Use a dark theme for the dashboard")
    time.sleep(0.3)

    results = memory.retrieve(
        agent_role="coder", query_text="python data science", top_k=5, similarity_threshold=-1.0
    )
    assert len(results) >= 1
    assert all(item.agent_role == "coder" for item in results)
    assert results[0].content_summary == "Python is great for data science"
    assert results[0].similarity is not None


def test_retrieve_filters_by_agent_role(memory):
    memory.update(agent_role="coder", text="shared topic about testing")
    memory.update(agent_role="designer", text="shared topic about testing")
    time.sleep(0.3)

    coder_results = memory.retrieve(
        agent_role="coder", query_text="testing", top_k=5, similarity_threshold=-1.0
    )
    assert all(item.agent_role == "coder" for item in coder_results)
    assert len(coder_results) == 1


def test_similarity_threshold_filters_unrelated_results(memory):
    memory.update(agent_role="coder", text="python testing pipelines")
    time.sleep(0.3)

    strict = memory.retrieve(
        agent_role="coder",
        query_text="completely unrelated astrophysics topic",
        top_k=5,
        similarity_threshold=0.99,
    )
    assert strict == []


def test_count_memories_reflects_stored_items(memory):
    assert memory.count_memories() == 0
    memory.update(agent_role="coder", text="first memory")
    memory.update(agent_role="coder", text="second memory")
    time.sleep(0.3)
    assert memory.count_memories() == 2


# --------------------------------------------------------------------------- #
# HSET / EXPIRE separate, ordered calls
# --------------------------------------------------------------------------- #
def test_update_calls_hset_then_expire_separately():
    config = unique_config(ttl_seconds=300)
    mem = ValkeyMemory(config)
    try:
        call_order = []
        original_hset = mem._client.hset
        original_expire = mem._client.expire

        def tracked_hset(*args, **kwargs):
            call_order.append("hset")
            return original_hset(*args, **kwargs)

        def tracked_expire(*args, **kwargs):
            call_order.append("expire")
            return original_expire(*args, **kwargs)

        with patch.object(mem._client, "hset", side_effect=tracked_hset), patch.object(
            mem._client, "expire", side_effect=tracked_expire
        ):
            mem.update(agent_role="coder", text="ttl ordering check")

        assert call_order == ["hset", "expire"], (
            "HSET must be called before EXPIRE, as two separate non-atomic calls"
        )
    finally:
        mem.close()


def test_update_skips_expire_when_ttl_not_configured():
    config = unique_config(ttl_seconds=None)
    mem = ValkeyMemory(config)
    try:
        with patch.object(mem._client, "expire") as mock_expire:
            mem.update(agent_role="coder", text="no ttl")
            mock_expire.assert_not_called()
    finally:
        mem.close()


# --------------------------------------------------------------------------- #
# Failure-mode split: create raises, retrieve/count/update degrade
# --------------------------------------------------------------------------- #
def test_index_create_failure_raises_clearly():
    """FT.CREATE errors must propagate — there is no silent fallback."""
    config = unique_config()
    mem = ValkeyMemory(config)
    try:
        with patch("valkey_memory.ft.info", side_effect=RequestError("Index: not found")), patch(
            "valkey_memory.ft.create",
            side_effect=RequestError("ERR unknown command 'FT.CREATE'"),
        ):
            with pytest.raises(RequestError):
                mem.update(agent_role="coder", text="should raise on create failure")
    finally:
        mem.close()


def test_retrieve_degrades_to_empty_list_on_missing_index():
    """retrieve() must NOT raise when the index doesn't exist — it degrades."""
    config = unique_config()
    mem = ValkeyMemory(config)
    try:
        with patch(
            "valkey_memory.ft.info", side_effect=RequestError("Index: not found")
        ), patch(
            "valkey_memory.ft.create",
            side_effect=RequestError("Search module not loaded"),
        ):
            results = mem.retrieve(agent_role="coder", query_text="anything", top_k=3)
            assert results == []
    finally:
        mem.close()


def test_count_memories_degrades_to_zero_on_missing_index():
    """count_memories() must NOT raise when the index doesn't exist — it degrades."""
    config = unique_config()
    mem = ValkeyMemory(config)
    try:
        with patch(
            "valkey_memory.ft.info", side_effect=RequestError("Index: not found")
        ), patch(
            "valkey_memory.ft.create",
            side_effect=RequestError("Search module not loaded"),
        ):
            assert mem.count_memories() == 0
    finally:
        mem.close()


# --------------------------------------------------------------------------- #
# Cleanup
# --------------------------------------------------------------------------- #
def test_close_is_safe_to_call_and_releases_connection():
    config = unique_config()
    mem = ValkeyMemory(config)
    mem.update(agent_role="coder", text="closing test")
    mem.close()  # must not raise
    # Calling an operation after close should fail loudly, not hang or
    # silently no-op — verifies the connection was actually released.
    with pytest.raises(Exception):
        mem.update(agent_role="coder", text="after close")
