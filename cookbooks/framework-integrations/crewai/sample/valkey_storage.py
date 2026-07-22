"""Valkey StorageBackend for CrewAI's unified Memory system.

Implements the crewai.memory.storage.backend.StorageBackend protocol using
valkey-glide (async) with synchronous wrappers for CrewAI's sync call sites.

Uses:
- HASH keys with JSON-serialized record fields
- FT.CREATE HNSW vector index for semantic search
- TAG fields for scope/category filtering
"""

from __future__ import annotations

import asyncio
import json
import struct
import threading
from datetime import datetime, timezone
from typing import Any

from glide import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ft,
)
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType,
    DistanceMetricType,
    FtCreateOptions,
    NumericField,
    TagField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
)
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions,
    FtSearchLimit,
)
from glide_shared.exceptions import RequestError

from crewai.memory.types import MemoryRecord, ScopeInfo


INDEX_NAME = "crewai_memory_idx"
KEY_PREFIX = "crewai:mem:"

# Characters that are token separators in FT.SEARCH TAG query syntax.
# Sourced from RediSearch ToksepMap_g (src/toksep.h) — 32 characters total.
_TAG_SPECIAL = set(' \t,./(){}[]:;~!@#$%^&*-=+|\'`"<>?\\')


def _sanitize_tag_value(value: str) -> str:
    """Escape TAG-special characters to prevent query injection (CWE-943)."""
    out = []
    for ch in value:
        if ch in _TAG_SPECIAL:
            out.append(f"\\{ch}")
        else:
            out.append(ch)
    return "".join(out)


class ValkeyStorageBackend:
    """CrewAI StorageBackend backed by Valkey with vector search.

    Args:
        host: Valkey hostname.
        port: Valkey port.
        embedding_dim: Dimension of embedding vectors stored.
        index_name: Name of the FT index.
        key_prefix: Key prefix for memory records.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        embedding_dim: int = 384,
        index_name: str = INDEX_NAME,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        self._host = host
        self._port = port
        self._embedding_dim = embedding_dim
        self._index_name = index_name
        self._key_prefix = key_prefix
        self._client: GlideClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    async def _get_client(self) -> GlideClient:
        if self._client is None:
            config = GlideClientConfiguration(
                addresses=[NodeAddress(self._host, self._port)],
                request_timeout=5000,
            )
            self._client = await GlideClient.create(config)
            await self._ensure_index()
        return self._client

    async def _ensure_index(self) -> None:
        """Create the HNSW vector index if it doesn't exist."""
        client = self._client
        if client is None:
            raise RuntimeError("Client not initialized before _ensure_index")
        try:
            existing = await ft.list(client)
            if self._index_name.encode() in existing:
                return
        except RequestError as exc:
            # Only swallow "unknown command" (module not loaded); re-raise real errors
            if "unknown command" not in str(exc).lower():
                raise

        hnsw = VectorFieldAttributesHnsw(
            dimensions=self._embedding_dim,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        )
        schema = [
            TagField("scope"),
            TagField("categories", separator="|"),
            NumericField("importance"),
            NumericField("created_at"),
            VectorField("embedding", VectorAlgorithm.HNSW, hnsw),
        ]
        await ft.create(
            client,
            self._index_name,
            schema,
            FtCreateOptions(DataType.HASH, prefixes=[self._key_prefix]),
        )

    def _record_to_hash(self, record: MemoryRecord) -> dict[str, str | bytes]:
        """Serialize a MemoryRecord to HASH field mapping."""
        embedding_bytes = b""
        if record.embedding:
            if len(record.embedding) != self._embedding_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(record.embedding)}, "
                    f"expected {self._embedding_dim}"
                )
            embedding_bytes = struct.pack(
                f"<{len(record.embedding)}f", *record.embedding
            )
        return {
            "id": record.id,
            "content": record.content,
            "scope": record.scope,
            "categories": "|".join(record.categories),
            "metadata_json": json.dumps(record.metadata),
            "importance": str(record.importance),
            "created_at": str(record.created_at.timestamp()),
            "last_accessed": str(record.last_accessed.timestamp()),
            "embedding": embedding_bytes,
            "source": record.source or "",
            "private": "1" if record.private else "0",
        }

    def _hash_to_record(self, fields: dict) -> MemoryRecord:
        """Deserialize HASH fields back to a MemoryRecord."""

        def _get(name: str) -> str:
            for key in (name, name.encode()):
                if key in fields:
                    val = fields[key]
                    return val.decode() if isinstance(val, bytes) else str(val)
            return ""

        def _get_bytes(name: str) -> bytes:
            for key in (name, name.encode()):
                if key in fields:
                    val = fields[key]
                    return val if isinstance(val, bytes) else val.encode()
            return b""

        embedding_bytes = _get_bytes("embedding")
        embedding = None
        if embedding_bytes:
            count = len(embedding_bytes) // 4
            embedding = list(struct.unpack(f"<{count}f", embedding_bytes))

        categories_str = _get("categories")
        categories = [c for c in categories_str.split("|") if c]

        created_ts = float(_get("created_at") or "0")
        accessed_ts = float(_get("last_accessed") or "0")

        metadata_str = _get("metadata_json")
        metadata = json.loads(metadata_str) if metadata_str else {}

        return MemoryRecord(
            id=_get("id"),
            content=_get("content"),
            scope=_get("scope") or "/",
            categories=categories,
            metadata=metadata,
            importance=float(_get("importance") or "0.5"),
            created_at=datetime.fromtimestamp(created_ts, tz=timezone.utc) if created_ts else datetime.now(timezone.utc),
            last_accessed=datetime.fromtimestamp(accessed_ts, tz=timezone.utc) if accessed_ts else datetime.now(timezone.utc),
            embedding=embedding,
            source=_get("source") or None,
            private=_get("private") == "1",
        )

    # ------------------------------------------------------------------
    # Async StorageBackend methods
    # ------------------------------------------------------------------

    async def asave(self, records: list[MemoryRecord]) -> None:
        client = await self._get_client()
        for record in records:
            key = f"{self._key_prefix}{record.id}"
            mapping = self._record_to_hash(record)
            await client.hset(key, mapping)

    async def asearch(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        if metadata_filter:
            raise NotImplementedError(
                "metadata_filter is not yet implemented in ValkeyStorageBackend"
            )
        client = await self._get_client()

        # Build filter
        filters = []
        if scope_prefix:
            escaped = _sanitize_tag_value(scope_prefix)
            filters.append(f"@scope:{{{escaped}}}")
        if categories:
            sanitized = [_sanitize_tag_value(c) for c in categories]
            joined = "|".join(sanitized)
            filters.append(f"@categories:{{{joined}}}")

        filter_str = " ".join(filters) if filters else "*"
        query = f"({filter_str})=>[KNN {limit} @embedding $query_vec AS score]"

        vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)
        options = FtSearchOptions(
            params={"query_vec": vec_bytes},
            dialect=2,
        )

        result = await ft.search(client, self._index_name, query, options)
        count = result[0]
        docs = result[1] if count > 0 else {}

        results = []
        for key, fields in docs.items():
            score_val = float(fields.get(b"score", fields.get("score", 999)))
            similarity = 1.0 - score_val  # COSINE: distance → similarity
            if similarity < min_score:
                continue
            record = self._hash_to_record(fields)
            results.append((record, similarity))

        return sorted(results, key=lambda x: x[1], reverse=True)

    async def adelete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        if older_than is not None:
            raise NotImplementedError(
                "older_than filtering is not yet implemented in ValkeyStorageBackend"
            )
        if metadata_filter:
            raise NotImplementedError(
                "metadata_filter is not yet implemented in ValkeyStorageBackend"
            )
        client = await self._get_client()
        deleted = 0

        if record_ids:
            keys = [f"{self._key_prefix}{rid}" for rid in record_ids]
            deleted = await client.delete(keys)
            return int(deleted)

        # For scope/category deletion, scan matching keys
        # Use FT.SEARCH to find matching records, then delete
        filters = []
        if scope_prefix:
            escaped = _sanitize_tag_value(scope_prefix)
            filters.append(f"@scope:{{{escaped}}}")
        if categories:
            sanitized = [_sanitize_tag_value(c) for c in categories]
            joined = "|".join(sanitized)
            filters.append(f"@categories:{{{joined}}}")

        if not filters:
            # Delete all — use SCAN
            cursor = "0"
            while True:
                result = await client.custom_command(
                    ["SCAN", cursor, "MATCH", f"{self._key_prefix}*", "COUNT", "100"]
                )
                cursor = result[0].decode() if isinstance(result[0], bytes) else str(result[0])
                keys = result[1]
                if keys:
                    deleted += await client.delete(keys)
                if cursor == "0":
                    break
            return int(deleted)

        query = " ".join(filters)
        options = FtSearchOptions(
            limit=FtSearchLimit(0, 1000),
            nocontent=True,
        )
        result = await ft.search(client, self._index_name, query, options)
        count = result[0]
        if count > 0:
            keys_to_delete = []
            # When nocontent=True, result[1] is still a dict with empty field maps
            for key in result[1].keys():
                k = key.decode() if isinstance(key, bytes) else key
                keys_to_delete.append(k)
            if keys_to_delete:
                deleted = await client.delete(keys_to_delete)

        return int(deleted)

    # ------------------------------------------------------------------
    # Sync StorageBackend methods (CrewAI calls these)
    # ------------------------------------------------------------------

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create a persistent event loop in a daemon thread.

        The GLIDE client is bound to this loop. All async operations
        must run here.
        """
        if self._loop is None or self._loop.is_closed():
            with self._loop_lock:
                if self._loop is None or self._loop.is_closed():
                    self._loop = asyncio.new_event_loop()
                    self._loop_thread = threading.Thread(
                        target=self._loop.run_forever, daemon=True
                    )
                    self._loop_thread.start()
                    # Reset client so it's recreated on this loop
                    self._client = None
        return self._loop

    def _run_sync(self, coro) -> Any:
        """Submit a coroutine to the persistent loop and wait for the result."""
        loop = self._get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)

    def save(self, records: list[MemoryRecord]) -> None:
        self._run_sync(self.asave(records))

    def search(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        return self._run_sync(
            self.asearch(query_embedding, scope_prefix, categories, metadata_filter, limit, min_score)
        )

    def delete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return self._run_sync(
            self.adelete(scope_prefix, categories, record_ids, older_than, metadata_filter)
        )

    def update(self, record: MemoryRecord) -> None:
        self._run_sync(self.asave([record]))

    def get_record(self, record_id: str) -> MemoryRecord | None:
        async def _get():
            client = await self._get_client()
            key = f"{self._key_prefix}{record_id}"
            fields = await client.hgetall(key)
            if not fields:
                return None
            return self._hash_to_record(fields)
        return self._run_sync(_get())

    def list_records(
        self,
        scope_prefix: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        async def _list():
            client = await self._get_client()
            if scope_prefix:
                escaped = _sanitize_tag_value(scope_prefix)
                query = f"@scope:{{{escaped}}}"
            else:
                # Match all records — use numeric range that covers everything
                query = "@importance:[-inf +inf]"
            options = FtSearchOptions(
                limit=FtSearchLimit(offset, limit),
            )
            result = await ft.search(client, self._index_name, query, options)
            count = result[0]
            if count == 0:
                return []
            records = []
            for key, fields in result[1].items():
                records.append(self._hash_to_record(fields))
            return records
        return self._run_sync(_list())

    def get_scope_info(self, scope: str) -> ScopeInfo:
        async def _info():
            client = await self._get_client()
            escaped = _sanitize_tag_value(scope)
            query = f"@scope:{{{escaped}}}"
            options = FtSearchOptions(
                limit=FtSearchLimit(0, 1000),
                dialect=2,
            )
            result = await ft.search(client, self._index_name, query, options)
            count = result[0]
            categories_set: set[str] = set()
            oldest = None
            newest = None
            if count > 0:
                for key, fields in result[1].items():
                    record = self._hash_to_record(fields)
                    categories_set.update(record.categories)
                    if oldest is None or record.created_at < oldest:
                        oldest = record.created_at
                    if newest is None or record.created_at > newest:
                        newest = record.created_at
            return ScopeInfo(
                path=scope,
                record_count=count,
                categories=sorted(categories_set),
                oldest_record=oldest,
                newest_record=newest,
                child_scopes=[],
            )
        return self._run_sync(_info())

    def list_scopes(self, parent: str = "/") -> list[str]:
        # Scan all records and extract unique scopes
        records = self.list_records(limit=1000)
        scopes: set[str] = set()
        for record in records:
            if record.scope.startswith(parent) and record.scope != parent:
                # Get immediate child
                rest = record.scope[len(parent):].lstrip("/")
                child = rest.split("/")[0]
                full_child = f"{parent.rstrip('/')}/{child}"
                scopes.add(full_child)
        return sorted(scopes)

    def list_categories(self, scope_prefix: str | None = None) -> dict[str, int]:
        records = self.list_records(scope_prefix=scope_prefix, limit=1000)
        counts: dict[str, int] = {}
        for record in records:
            for cat in record.categories:
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    def count(self, scope_prefix: str | None = None) -> int:
        async def _count():
            client = await self._get_client()
            if scope_prefix is None:
                # Use FT.INFO for total count (fast, no query needed)
                info = await ft.info(client, self._index_name)
                return int(info.get(b"num_docs", info.get("num_docs", 0)))
            # For scoped count, we need to search
            escaped = _sanitize_tag_value(scope_prefix)
            query = f"@scope:{{{escaped}}}"
            options = FtSearchOptions(
                limit=FtSearchLimit(0, 1),
                nocontent=True,
            )
            result = await ft.search(client, self._index_name, query, options)
            return result[0]
        return self._run_sync(_count())

    def reset(self, scope_prefix: str | None = None) -> None:
        if scope_prefix:
            self.delete(scope_prefix=scope_prefix)
        else:
            async def _reset():
                client = await self._get_client()
                try:
                    await ft.dropindex(client, self._index_name)
                except RequestError as exc:
                    # Only swallow "unknown index" (index doesn't exist); re-raise real errors
                    if "not found" not in str(exc).lower() and "unknown index" not in str(exc).lower():
                        raise
                # Delete all keys with our prefix
                # GLIDE v2 doesn't have scan_iter; use custom_command
                cursor = "0"
                while True:
                    result = await client.custom_command(
                        ["SCAN", cursor, "MATCH", f"{self._key_prefix}*", "COUNT", "100"]
                    )
                    cursor = result[0].decode() if isinstance(result[0], bytes) else str(result[0])
                    keys = result[1]
                    if keys:
                        await client.delete(keys)
                    if cursor == "0":
                        break
                # Recreate index
                await self._ensure_index()
            self._run_sync(_reset())

    def close(self) -> None:
        """Close the GLIDE client connection and stop the background loop."""
        if self._client:
            self._run_sync(self._client.close())
            self._client = None
        if hasattr(self, "_loop") and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop_thread.join(timeout=5)
            self._loop.close()
            self._loop = None
