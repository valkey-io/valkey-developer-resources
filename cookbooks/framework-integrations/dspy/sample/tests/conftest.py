"""Shared fixtures for DSPy + Valkey cookbook integration tests."""

import asyncio
import os

import pytest
from glide import GlideClient, GlideClientConfiguration, NodeAddress


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def valkey_client(event_loop):
    """Create a GLIDE client connected to the test Valkey instance."""
    async def _create():
        config = GlideClientConfiguration(
            addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
            request_timeout=5000,
        )
        return await GlideClient.create(config)

    client = event_loop.run_until_complete(_create())
    yield client
    event_loop.run_until_complete(client.close())


@pytest.fixture(autouse=True)
def flush_valkey(valkey_client, event_loop):
    """Flush all keys before each test for isolation."""
    event_loop.run_until_complete(valkey_client.custom_command(["FLUSHALL"]))
    yield
