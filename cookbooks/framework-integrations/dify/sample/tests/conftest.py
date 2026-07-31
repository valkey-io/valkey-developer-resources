"""Pytest configuration and shared fixtures for Dify + Valkey cookbook tests."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def valkey_client() -> AsyncGenerator[GlideClient, None]:
    """Create a Valkey client connected to localhost:6379."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dify_cookbook_test",
        request_timeout=5000,
    )
    client = await GlideClient.create(config)
    try:
        yield client
    finally:
        await client.close()
