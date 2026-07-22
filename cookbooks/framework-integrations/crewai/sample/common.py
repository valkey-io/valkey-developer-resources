"""Shared configuration, GLIDE client factory, and helpers for the CrewAI cookbook sample."""

from __future__ import annotations

import os

from dotenv import dotenv_values
from glide import (
    AdvancedGlideClientConfiguration,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ft,
)
from glide_shared.exceptions import RequestError

VALKEY_HOST_DEFAULT = "localhost"
VALKEY_PORT_DEFAULT = 6379
REQUEST_TIMEOUT_MS = 5000


def _setting(name: str, default: str = "") -> str:
    """Read from shell env first, then optional .env file."""
    file_values = dotenv_values(".env")
    return os.environ.get(name, file_values.get(name, default)) or default


def connection_settings() -> tuple[str, int]:
    """Read Valkey connection overrides at call time."""
    return (
        _setting("VALKEY_HOST", VALKEY_HOST_DEFAULT),
        int(_setting("VALKEY_PORT", str(VALKEY_PORT_DEFAULT))),
    )


async def create_client() -> GlideClient:
    """Create a GLIDE client with bounded timeouts."""
    host, port = connection_settings()
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        request_timeout=REQUEST_TIMEOUT_MS,
        advanced_config=AdvancedGlideClientConfiguration(
            connection_timeout=REQUEST_TIMEOUT_MS,
        ),
    )
    return await GlideClient.create(config)


async def drop_index(client: GlideClient, index_name: str) -> None:
    """Drop an index if it exists; ignore 'not found' errors."""
    try:
        await ft.dropindex(client, index_name)
    except RequestError as exc:
        message = str(exc).lower()
        missing = (
            "unknown index" in message
            or ("index" in message and "not found in database" in message)
        )
        if not missing:
            raise


async def cleanup(client: GlideClient, index_name: str, keys: list[str]) -> None:
    """Remove sample indexes and keys for repeatable runs."""
    await drop_index(client, index_name)
    if keys:
        await client.delete(keys)


def field_text(fields: dict, name: str) -> str:
    """Extract a text field from ft.search result (handles bytes keys)."""
    for key in (name, name.encode("utf-8")):
        if key in fields:
            value = fields[key]
            return value.decode() if isinstance(value, bytes) else str(value)
    return ""


def field_float(fields: dict, name: str) -> float:
    """Extract a float field from ft.search result."""
    for key in (name, name.encode("utf-8")):
        if key in fields:
            return float(fields[key])
    raise KeyError(f"Field {name!r} not found in search result")
