"""Pytest configuration and shared fixtures for DB-GPT + Valkey cookbook tests."""
from __future__ import annotations

from typing import AsyncGenerator

import pytest_asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress


@pytest_asyncio.fixture
async def valkey_client() -> AsyncGenerator[GlideClient, None]:
    """Create a Valkey client connected to localhost:6379."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dbgpt_cookbook_test",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture
async def clean_valkey(valkey_client: GlideClient) -> AsyncGenerator[GlideClient, None]:
    """Provide a Valkey client and clean up test keys/indexes after the test."""
    yield valkey_client

    # Cleanup: drop any test indexes
    for index_name in ["__test_hnsw_idx__", "__test_flat_idx__", "__test_meta_idx__"]:
        try:
            await valkey_client.custom_command(["FT.DROPINDEX", index_name])
        except Exception:
            pass

    # Cleanup: scan and delete test keys
    cursor = "0"
    while True:
        result = await valkey_client.custom_command(
            ["SCAN", cursor, "MATCH", "__test__:*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys = result[1]
        if keys:
            key_list = [k if isinstance(k, str) else k.decode() for k in keys]
            await valkey_client.delete(key_list)
        if cursor == "0":
            break

    # Cleanup: scan and delete cache test keys
    cursor = "0"
    while True:
        result = await valkey_client.custom_command(
            ["SCAN", cursor, "MATCH", "__test_cache__:*", "COUNT", "100"]
        )
        cursor = result[0] if isinstance(result[0], str) else result[0].decode()
        keys = result[1]
        if keys:
            key_list = [k if isinstance(k, str) else k.decode() for k in keys]
            await valkey_client.delete(key_list)
        if cursor == "0":
            break
