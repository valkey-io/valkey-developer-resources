"""Shared configuration and deterministic embedding helpers for the sample."""

from __future__ import annotations

import hashlib
import math
import os
import re

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
OPENAI_TIMEOUT_SECONDS = 10.0
LOCAL_EMBEDDING_DIM = 16
_openai_client = None
_openai_client_key = None


def _setting(name: str, default: str) -> str:
    """Read a shell value first, then the optional local .env file."""
    file_values = dotenv_values(".env")
    return os.environ.get(name, file_values.get(name, default)) or default


def _field_value(fields, name: str):
    for key in (name, name.encode("utf-8")):
        if key in fields:
            return fields[key]
    return None


def field_text(fields, name: str) -> str:
    value = _field_value(fields, name)
    if value is None:
        return ""
    return value.decode() if isinstance(value, bytes) else str(value)


def vector_similarity(fields) -> float:
    value = _field_value(fields, "score")
    if value is None:
        value = _field_value(fields, "vector_score")
    if value is None:
        raise KeyError("vector score was not returned by Valkey Search")
    return 1 - float(value)


def connection_settings() -> tuple[str, int]:
    """Read connection overrides at call time so tests and users can override them."""
    return (
        _setting("VALKEY_HOST", VALKEY_HOST_DEFAULT),
        int(_setting("VALKEY_PORT", str(VALKEY_PORT_DEFAULT))),
    )


def embedding_dimension() -> int:
    """Return the dimension used by the selected embedding provider."""
    if not _setting("OPENAI_API_KEY", ""):
        return LOCAL_EMBEDDING_DIM
    dimension = int(_setting("OPENAI_EMBEDDING_DIM", "1536"))
    if dimension < 1:
        raise ValueError("OPENAI_EMBEDDING_DIM must be a positive integer")
    return dimension


def validate_k(k: int) -> int:
    """Bound KNN result size before placing it in query syntax."""
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 1000:
        raise ValueError("k must be an integer between 1 and 1000")
    return k


def _local_embedding(text: str) -> list[float]:
    """Create a stable, normalized vector without network access or model downloads."""
    vector = [0.0] * LOCAL_EMBEDDING_DIM
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:4], "big") % LOCAL_EMBEDDING_DIM] += 1.0
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _get_openai_client(api_key: str):
    global _openai_client, _openai_client_key

    if _openai_client is None or _openai_client_key != api_key:
        close_embedder()
        from openai import OpenAI

        _openai_client = OpenAI(
            api_key=api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=1,
        )
        _openai_client_key = api_key
    return _openai_client


def close_embedder() -> None:
    """Close the optional provider client and release its HTTP resources."""
    global _openai_client, _openai_client_key

    if _openai_client is not None:
        _openai_client.close()
    _openai_client = None
    _openai_client_key = None


def embed(texts: list[str]) -> list[list[float]]:
    """Embed locally by default, or use OpenAI when an API key is explicitly set."""
    api_key = _setting("OPENAI_API_KEY", "")
    if not api_key:
        return [_local_embedding(text) for text in texts]

    client = _get_openai_client(api_key)
    response = client.embeddings.create(
        input=texts,
        model=_setting("EMBED_MODEL", "text-embedding-3-small"),
        dimensions=embedding_dimension(),
    )
    return [item.embedding for item in response.data]


async def create_client() -> GlideClient:
    """Create a GLIDE client with a bounded request timeout."""
    host, port = connection_settings()
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        request_timeout=REQUEST_TIMEOUT_MS,
        advanced_config=AdvancedGlideClientConfiguration(
            connection_timeout=REQUEST_TIMEOUT_MS
        ),
    )
    return await GlideClient.create(config)


async def drop_index(client: GlideClient, index_name: str) -> None:
    """Drop an index when present; preserve real Valkey errors."""
    try:
        await ft.dropindex(client, index_name)
    except RequestError as exc:
        message = str(exc).lower()
        missing_index = (
            "unknown index" in message
            or (
                "index: with name" in message
                and "not found in database" in message
            )
        )
        if not missing_index:
            raise


async def cleanup(client: GlideClient, index_name: str, keys: list[str]) -> None:
    """Remove sample indexes and keys so success and failure paths are repeatable."""
    await drop_index(client, index_name)
    if keys:
        await client.delete(keys)
