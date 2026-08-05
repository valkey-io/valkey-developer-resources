"""Integration tests for DSPy ValkeyCache patterns against a live Valkey instance.

These tests validate the Valkey operations that ValkeyCache performs:
- SET with and without TTL (EX option)
- GET returning bytes or nil
- EXISTS on namespaced keys
- DELETE for cache eviction
- Key namespacing with configurable prefix

No LLM calls are made — these test the cache layer in isolation.
"""

import asyncio
import pickle
import struct
import time

import pytest
from glide import ExpirySet, ExpiryType


# -- Test: basic SET/GET round-trip (the core cache pattern) --


def test_set_and_get_pickled_bytes(valkey_client, event_loop):
    """ValkeyCache stores pickled Python objects as bytes and retrieves them."""
    data = {"message": "Hello from DSPy", "usage": {"tokens": 42}}
    raw = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

    async def _test():
        await valkey_client.set("dspy:cache:abc123", raw)
        result = await valkey_client.get("dspy:cache:abc123")
        return result

    result = event_loop.run_until_complete(_test())
    assert result is not None
    restored = pickle.loads(result)
    assert restored == data


def test_get_returns_none_on_miss(valkey_client, event_loop):
    """GET on a non-existent key returns None (cache miss)."""
    async def _test():
        return await valkey_client.get("dspy:cache:nonexistent")

    result = event_loop.run_until_complete(_test())
    assert result is None


# -- Test: TTL expiry (EX option on SET) --


def test_set_with_ttl_expires(valkey_client, event_loop):
    """SET with EX option creates a key that expires after the TTL."""
    raw = pickle.dumps({"cached": True}, protocol=pickle.HIGHEST_PROTOCOL)

    async def _test():
        expiry = ExpirySet(expiry_type=ExpiryType.SEC, value=1)
        await valkey_client.set("dspy:cache:ttl_test", raw, expiry=expiry)

        # Key exists immediately
        exists_before = await valkey_client.exists(["dspy:cache:ttl_test"])
        assert exists_before == 1

        # Wait for expiry
        await asyncio.sleep(1.5)

        # Key is gone
        exists_after = await valkey_client.exists(["dspy:cache:ttl_test"])
        assert exists_after == 0

    event_loop.run_until_complete(_test())


def test_set_without_ttl_persists(valkey_client, event_loop):
    """SET without EX option creates a persistent key (no expiry)."""
    raw = pickle.dumps({"persistent": True}, protocol=pickle.HIGHEST_PROTOCOL)

    async def _test():
        await valkey_client.set("dspy:cache:no_ttl", raw)
        ttl = await valkey_client.ttl("dspy:cache:no_ttl")
        # TTL of -1 means no expiry set
        assert ttl == -1

    event_loop.run_until_complete(_test())


# -- Test: EXISTS for __contains__ --


def test_exists_returns_count(valkey_client, event_loop):
    """EXISTS returns 1 for present keys and 0 for absent keys."""
    async def _test():
        await valkey_client.set("dspy:cache:present", b"data")
        present = await valkey_client.exists(["dspy:cache:present"])
        absent = await valkey_client.exists(["dspy:cache:missing"])
        return present, absent

    present, absent = event_loop.run_until_complete(_test())
    assert present == 1
    assert absent == 0


# -- Test: DELETE for eviction --


def test_delete_removes_key(valkey_client, event_loop):
    """DELETE removes a key (used to evict poisoned entries)."""
    async def _test():
        await valkey_client.set("dspy:cache:evict_me", b"bad_data")
        await valkey_client.delete(["dspy:cache:evict_me"])
        result = await valkey_client.get("dspy:cache:evict_me")
        return result

    result = event_loop.run_until_complete(_test())
    assert result is None


# -- Test: key namespacing --


def test_key_prefix_isolation(valkey_client, event_loop):
    """Different key prefixes provide tenant isolation."""
    async def _test():
        await valkey_client.set("tenant-a:cache:key1", b"value_a")
        await valkey_client.set("tenant-b:cache:key1", b"value_b")

        a = await valkey_client.get("tenant-a:cache:key1")
        b = await valkey_client.get("tenant-b:cache:key1")
        return a, b

    a, b = event_loop.run_until_complete(_test())
    assert a == b"value_a"
    assert b == b"value_b"


# -- Test: large payload (typical LLM response) --


def test_large_payload_round_trip(valkey_client, event_loop):
    """A typical LLM response (several KB pickled) round-trips correctly."""
    large_response = {
        "choices": [{"message": {"content": "x" * 4096}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600},
        "model": "gpt-4",
    }
    raw = pickle.dumps(large_response, protocol=pickle.HIGHEST_PROTOCOL)

    async def _test():
        await valkey_client.set("dspy:cache:large", raw)
        result = await valkey_client.get("dspy:cache:large")
        return result

    result = event_loop.run_until_complete(_test())
    restored = pickle.loads(result)
    assert restored["choices"][0]["message"]["content"] == "x" * 4096
    assert restored["usage"]["total_tokens"] == 600


# -- Test: overwrite behavior --


def test_set_overwrites_existing(valkey_client, event_loop):
    """SET overwrites existing value (cache update behavior)."""
    async def _test():
        await valkey_client.set("dspy:cache:update", b"old_value")
        await valkey_client.set("dspy:cache:update", b"new_value")
        result = await valkey_client.get("dspy:cache:update")
        return result

    result = event_loop.run_until_complete(_test())
    assert result == b"new_value"
