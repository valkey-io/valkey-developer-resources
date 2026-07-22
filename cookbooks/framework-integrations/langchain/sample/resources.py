from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from urllib.parse import urlsplit

from langchain_core.embeddings import Embeddings
from langgraph_checkpoint_aws import ValkeyCache, ValkeySaver, ValkeyStore
from valkey import Valkey
from valkey.exceptions import ResponseError


_ResourceT = TypeVar("_ResourceT")
_INDEX_OWNER_PREFIX = "langchain:cookbook:index-owner:"


def _positive_int(name: str, value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be a positive integer")
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _positive_float(name: str, value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{name} must be a positive number")
    return parsed


def _validate_valkey_url(value: str) -> str:
    parsed = urlsplit(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme.lower() not in {
        "valkey",
        "valkeys",
        "unix",
    }:
        raise ValueError(
            "VALKEY_URL must use valkey://, valkeys://, or unix:// scheme"
        )
    return value


@dataclass(frozen=True)
class Settings:
    valkey_url: str = "valkey://127.0.0.1:6379"
    socket_timeout: float = 5.0
    checkpoint_ttl_seconds: int = 3600
    cache_ttl_seconds: int = 300
    store_ttl_minutes: int = 60
    cache_prefix: str = "langchain:cache:"
    store_collection_name: str = "langchain_store_idx"
    store_namespace: str = "langchain-cookbook"

    def __post_init__(self) -> None:
        object.__setattr__(self, "valkey_url", _validate_valkey_url(self.valkey_url))
        object.__setattr__(
            self,
            "socket_timeout",
            _positive_float("socket_timeout", self.socket_timeout),
        )
        object.__setattr__(
            self,
            "checkpoint_ttl_seconds",
            _positive_int(
                "checkpoint_ttl_seconds",
                self.checkpoint_ttl_seconds,
            ),
        )
        object.__setattr__(
            self,
            "cache_ttl_seconds",
            _positive_int("cache_ttl_seconds", self.cache_ttl_seconds),
        )
        object.__setattr__(
            self,
            "store_ttl_minutes",
            _positive_int("store_ttl_minutes", self.store_ttl_minutes),
        )

    @classmethod
    def from_env(cls) -> Settings:
        valkey_url = os.getenv("VALKEY_URL")
        if not valkey_url:
            host = os.getenv("VALKEY_HOST") or "127.0.0.1"
            port = _positive_int("VALKEY_PORT", os.getenv("VALKEY_PORT", "6379"))
            valkey_url = f"valkey://{host}:{port}"

        return cls(
            valkey_url=valkey_url,
            socket_timeout=_positive_float(
                "VALKEY_SOCKET_TIMEOUT",
                os.getenv("VALKEY_SOCKET_TIMEOUT", "5.0"),
            ),
            checkpoint_ttl_seconds=_positive_int(
                "CHECKPOINT_TTL_SECONDS",
                os.getenv("CHECKPOINT_TTL_SECONDS", "3600"),
            ),
            cache_ttl_seconds=_positive_int(
                "CACHE_TTL_SECONDS",
                os.getenv("CACHE_TTL_SECONDS", "300"),
            ),
            store_ttl_minutes=_positive_int(
                "STORE_TTL_MINUTES",
                os.getenv("STORE_TTL_MINUTES", "60"),
            ),
            cache_prefix=os.getenv("VALKEY_CACHE_PREFIX", "langchain:cache:"),
            store_collection_name=os.getenv(
                "VALKEY_STORE_COLLECTION",
                "langchain_store_idx",
            ),
            store_namespace=os.getenv(
                "VALKEY_STORE_NAMESPACE",
                "langchain-cookbook",
            ),
        )


def _validate_run_id(run_id: str) -> None:
    if not run_id or any(character in run_id for character in ("/", ":")):
        raise ValueError("run_id must be non-empty and cannot contain '/' or ':'")


def create_valkey_client(settings: Settings) -> Valkey:
    return Valkey.from_url(
        settings.valkey_url,
        decode_responses=False,
        socket_timeout=settings.socket_timeout,
        socket_connect_timeout=settings.socket_timeout,
    )


class DeterministicEmbeddings(Embeddings):
    """Small local embeddings for a credential-free, repeatable sample."""

    dimensions = 4

    @staticmethod
    def _embed(text: str) -> list[float]:
        normalized = text.lower()
        if any(
            term in normalized for term in ("password", "forgot", "reset", "credential")
        ):
            return [1.0, 0.0, 0.0, 1.0]
        if any(term in normalized for term in ("vpn", "network", "connect")):
            return [0.0, 1.0, 0.0, 1.0]
        return [0.0, 0.0, 1.0, 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


class _ManagedResource(Generic[_ResourceT]):
    """Expose a resource directly while also supporting context-manager use."""

    def __init__(self, resource: _ResourceT, owned_client: Valkey | None) -> None:
        self._resource = resource
        self._owned_client = owned_client
        self._closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resource, name)

    def __enter__(self) -> _ResourceT:
        return self._resource

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if not self._closed and self._owned_client is not None:
            self._owned_client.close()
            self._closed = True


def _client_for_resource(
    settings: Settings,
    client: Valkey | None,
) -> tuple[Valkey, Valkey | None]:
    if client is not None:
        return client, None
    created_client = create_valkey_client(settings)
    return created_client, created_client


def create_checkpointer(
    settings: Settings,
    client: Valkey | None = None,
) -> _ManagedResource[ValkeySaver]:
    valkey_client, owned_client = _client_for_resource(settings, client)
    try:
        checkpointer = ValkeySaver(
            client=valkey_client,
            ttl=settings.checkpoint_ttl_seconds,
        )
    except BaseException:
        if owned_client is not None:
            owned_client.close()
        raise
    return _ManagedResource(checkpointer, owned_client)


def create_cache(
    settings: Settings,
    client: Valkey | None = None,
) -> _ManagedResource[ValkeyCache]:
    valkey_client, owned_client = _client_for_resource(settings, client)
    try:
        cache = ValkeyCache(
            client=valkey_client,
            prefix=settings.cache_prefix,
            ttl=settings.cache_ttl_seconds,
        )
    except BaseException:
        if owned_client is not None:
            owned_client.close()
        raise
    return _ManagedResource(cache, owned_client)


def _index_exists(client: Valkey, index_name: str) -> bool:
    try:
        client.execute_command("FT.INFO", index_name)
    except ResponseError:
        return False
    return True


def _index_owner_key(index_name: str) -> str:
    return f"{_INDEX_OWNER_PREFIX}{index_name}"


def create_store(
    settings: Settings,
    client: Valkey | None = None,
    embeddings: Embeddings | None = None,
) -> _ManagedResource[ValkeyStore]:
    valkey_client, owned_client = _client_for_resource(settings, client)
    try:
        embedding_provider = embeddings or DeterministicEmbeddings()
        dimensions = getattr(embedding_provider, "dimensions", None)
        if dimensions is None:
            dimensions = len(embedding_provider.embed_query("dimension probe"))
        dimensions = _positive_int("embedding dimensions", dimensions)
        index = {
            "collection_name": settings.store_collection_name,
            "dims": dimensions,
            "embed": embedding_provider,
            "fields": ["text"],
            "index_type": "hnsw",
            "distance_metric": "COSINE",
        }
        index_existed = _index_exists(
            valkey_client,
            settings.store_collection_name,
        )
        store = ValkeyStore(
            client=valkey_client,
            index=index,
            ttl={"default_ttl": settings.store_ttl_minutes},
        )
        store.setup()
        if not index_existed and _index_exists(
            valkey_client, settings.store_collection_name
        ):
            valkey_client.set(_index_owner_key(settings.store_collection_name), "1")
    except BaseException:
        if owned_client is not None:
            owned_client.close()
        raise
    return _ManagedResource(store, owned_client)
