# -*- coding: utf-8 -*-
"""Standalone re-implementation of ChatDev's ValkeyMemory backend.

This module reproduces the verified store/retrieve/expire behavior of
OpenBMB/ChatDev's `ValkeyMemory` (see upstream PR
https://github.com/OpenBMB/ChatDev/pull/634, open/unmerged at the time of
writing) using the real `valkey-glide-sync` API directly. It does NOT import
ChatDev — ChatDev's `pyproject.toml` declares `package = false`, so it cannot
be installed as a library dependency. This sample is independently runnable
and only depends on `valkey-glide-sync`.

Reproduced behavior:
    - Client name is set to "chatdev_memory_client" (see cookbook 01 and the
      client-name tracking initiative for why this matters operationally).
    - Keys follow the pattern f"{key_prefix}{uuid.uuid4().hex}".
    - The FT index schema is:
        content_summary TEXT
        agent_role       TAG
        timestamp        NUMERIC
        embedding        VECTOR HNSW COSINE FLOAT32 (dimension probed at
                          runtime from a live embedding call, matching
                          upstream's dynamic-dimension behavior)
    - TAG values are sanitized by replacing `,{}|<>` and whitespace
      (space/tab/newline/CR) with `_`, matching Valkey Search's TAG field
      escaping rules.
    - Writes are HSET followed by a *separate*, non-atomic EXPIRE call —
      exactly as upstream does it. If the process crashes between the two
      calls, the key persists without a TTL. See cookbook 02 for the
      transaction/Lua-script mitigation upstream leaves as an exercise.
    - Retrieval builds either a filtered query
      "(@agent_role:{role})=>[KNN k @embedding $vec]" or an unfiltered
      "*=>[KNN k @embedding $vec]" query, matching upstream's two code paths.
    - Similarity is computed as `1.0 - distance` and filtered by
      `similarity_threshold` (any negative threshold disables filtering).
    - `FT.CREATE` failures (e.g., Search module not loaded) raise clearly —
      there is no silent fallback for index creation. `update()`,
      `retrieve()`, and `count_memories()` degrade the same way upstream's
      `MemoryFactory`-created stores do: retrieval on a missing/unusable
      index returns an empty list instead of raising, since a workflow
      should keep running (just without memory) rather than crash.
"""

from __future__ import annotations

import os
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from glide_sync import (
    DataType,
    DistanceMetricType,
    FtCreateOptions,
    FtSearchOptions,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    NumericField,
    RequestError,
    ServerCredentials,
    TagField,
    TextField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
    ft,
)

from embeddings import EmbeddingProvider, LocalDeterministicEmbedding

# Characters that Valkey Search's TAG parser treats specially. Sanitizing
# them to "_" mirrors upstream ChatDev's ValkeyMemory.sanitize_tag().
_TAG_UNSAFE_CHARS = ",{}|<> \t\n\r"


def sanitize_tag(value: str) -> str:
    """Replace TAG-unsafe characters with "_".

    Matches upstream: any of `,{}|<>` plus space, tab, newline, and carriage
    return become "_" so the value can be safely embedded in a
    `@agent_role:{value}` TAG filter without breaking the query parser.
    """
    out = []
    for ch in value:
        out.append("_" if ch in _TAG_UNSAFE_CHARS else ch)
    return "".join(out)


def _decode(value: object) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def _pack_embedding(vector: list[float]) -> bytes:
    """Pack a float list into float32 little-endian bytes for VECTOR fields."""
    return struct.pack(f"<{len(vector)}f", *[float(x) for x in vector])


@dataclass
class MemoryItem:
    """A single retrieved memory, mirroring upstream's MemoryItem shape."""

    key: str
    content_summary: str
    agent_role: str
    timestamp: float
    similarity: Optional[float] = None


@dataclass
class ValkeyMemoryConfig:
    """Connection and behavior configuration for ValkeyMemory.

    Field names and defaults mirror upstream's EmbeddingConfig/ValkeyMemory
    config so the Configuration Reference tables in the cookbook stay
    accurate against this implementation.
    """

    host: str = field(default_factory=lambda: os.getenv("VALKEY_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("VALKEY_PORT", "6379")))
    request_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("VALKEY_REQUEST_TIMEOUT_MS", "5000"))
    )
    index_name: str = "memory_index"
    key_prefix: str = "memory:"
    ttl_seconds: Optional[int] = None
    use_tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    db: int = 0


class ValkeyMemory:
    """Standalone reproduction of ChatDev's ValkeyMemory backend.

    Usage:
        memory = ValkeyMemory(ValkeyMemoryConfig(...), embedding=LocalDeterministicEmbedding())
        try:
            memory.update(agent_role="coder", text="...")
            results = memory.retrieve(agent_role="coder", query_text="...", top_k=3)
        finally:
            memory.close()
    """

    def __init__(
        self,
        config: ValkeyMemoryConfig,
        embedding: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.config = config
        self.embedding: EmbeddingProvider = embedding or LocalDeterministicEmbedding()
        self._client = self._create_client()
        self._dimension: Optional[int] = None
        self._index_ready = False

    # -- connection lifecycle ------------------------------------------------
    def _create_client(self) -> GlideClient:
        credentials = None
        if self.config.password:
            credentials = ServerCredentials(
                username=self.config.username or "default",
                password=self.config.password,
            )
        client_config = GlideClientConfiguration(
            addresses=[NodeAddress(self.config.host, self.config.port)],
            client_name="chatdev_memory_client",
            request_timeout=self.config.request_timeout_ms,
            use_tls=self.config.use_tls,
            credentials=credentials,
            database_id=self.config.db if self.config.db != 0 else None,
        )
        return GlideClient.create(client_config)

    def close(self) -> None:
        """Close the underlying GLIDE connection. Always call this in a finally block."""
        self._client.close()

    # -- index management -----------------------------------------------------
    def _ensure_index(self) -> None:
        """Create the FT index on first use. Raises clearly if creation fails.

        Unlike retrieve()/update(), which degrade gracefully when the index
        is missing or unusable, index creation failures (e.g., the Search
        module isn't loaded) are NOT swallowed — a workflow that can never
        create its memory index should fail loudly at startup, not silently
        run with no persistence.
        """
        if self._index_ready:
            return

        # Probe the embedding dimension from a live call, exactly like
        # upstream: the index schema must match whatever the configured
        # embedding provider actually returns.
        probe_vector = self.embedding.get_embedding("dimension probe")
        self._dimension = len(probe_vector)

        try:
            ft.info(self._client, self.config.index_name)
            self._index_ready = True
            return  # index already exists — idempotent, matches upstream
        except RequestError:
            pass  # does not exist yet — fall through to create it

        schema = [
            TextField(name="content_summary"),
            TagField(name="agent_role"),
            NumericField(name="timestamp"),
            VectorField(
                name="embedding",
                algorithm=VectorAlgorithm.HNSW,
                attributes=VectorFieldAttributesHnsw(
                    dimensions=self._dimension,
                    distance_metric=DistanceMetricType.COSINE,
                    type=VectorType.FLOAT32,
                ),
            ),
        ]
        options = FtCreateOptions(
            data_type=DataType.HASH,
            prefixes=[self.config.key_prefix],
        )
        # No try/except here: FT.CREATE failures propagate to the caller.
        ft.create(self._client, self.config.index_name, schema, options)
        self._index_ready = True

    # -- write -----------------------------------------------------------------
    def update(self, agent_role: str, text: str) -> str:
        """Store a memory item. Returns the generated key.

        Mirrors upstream's update(): embed -> HSET -> separate EXPIRE call.
        """
        self._ensure_index()

        embedding_vec = self.embedding.get_embedding(text)
        embedding_bytes = _pack_embedding(embedding_vec)
        key = f"{self.config.key_prefix}{uuid.uuid4().hex}"

        # Step 1: HSET. This is the atomic, durable write.
        self._client.hset(
            key,
            {
                "content_summary": text,
                "embedding": embedding_bytes,
                "agent_role": sanitize_tag(agent_role),
                "timestamp": str(time.time()),
            },
        )

        # Step 2: EXPIRE — a SEPARATE, non-atomic call, matching upstream.
        # If the process crashes between HSET and EXPIRE, the key persists
        # without a TTL. See cookbook 02 for the transaction/Lua mitigation.
        if self.config.ttl_seconds is not None:
            self._client.expire(key, self.config.ttl_seconds)

        return key

    # -- read --------------------------------------------------------------
    def retrieve(
        self,
        agent_role: Optional[str],
        query_text: str,
        top_k: int = 3,
        similarity_threshold: float = -1.0,
    ) -> list[MemoryItem]:
        """Run a KNN vector search, optionally filtered by agent_role.

        Any negative `similarity_threshold` disables filtering (returns the
        top-k results regardless of score), matching upstream's convention.

        Degrades gracefully: if the index doesn't exist or the query fails
        with a Search-layer error, returns an empty list instead of raising,
        matching upstream's MemoryFactory-created stores.
        """
        try:
            self._ensure_index()
        except RequestError:
            return []

        query_vec = self.embedding.get_embedding(query_text)
        query_bytes = _pack_embedding(query_vec)

        if agent_role:
            pre_filter = f"(@agent_role:{{{sanitize_tag(agent_role)}}})"
        else:
            pre_filter = "*"
        ft_query = f"{pre_filter}=>[KNN {top_k} @embedding $vec AS score]"

        options = FtSearchOptions(params={"vec": query_bytes}, dialect=2)
        try:
            reply = ft.search(self._client, self.config.index_name, ft_query, options)
        except RequestError:
            return []

        return self._parse_search_reply(reply, similarity_threshold)

    def _parse_search_reply(
        self, reply: list, similarity_threshold: float
    ) -> list[MemoryItem]:
        results: list[MemoryItem] = []
        if not reply or len(reply) < 2 or not isinstance(reply[1], dict):
            return results

        for raw_key, raw_fields in reply[1].items():
            fields = {_decode(k): v for k, v in raw_fields.items()}
            distance_raw = fields.get("score")
            similarity = None
            if distance_raw is not None:
                distance = float(_decode(distance_raw))
                similarity = 1.0 - distance

            if similarity_threshold >= 0 and (
                similarity is None or similarity < similarity_threshold
            ):
                continue

            results.append(
                MemoryItem(
                    key=_decode(raw_key),
                    content_summary=_decode(fields.get("content_summary", "")),
                    agent_role=_decode(fields.get("agent_role", "")),
                    timestamp=float(_decode(fields.get("timestamp", "0"))),
                    similarity=similarity,
                )
            )

        # Sort by descending similarity, matching upstream's ranking.
        results.sort(key=lambda item: item.similarity or 0.0, reverse=True)
        return results

    def count_memories(self) -> int:
        """Return the number of stored memory documents.

        Uses FT.INFO's `num_docs` rather than FT.SEARCH: because the schema
        has a mandatory VECTOR field, a bare `*` (non-KNN) query is rejected
        by the Search module with "Invalid: query string syntax" — every
        query against this index must include a KNN clause. `num_docs` is
        the correct, query-free way to count documents.

        Degrades to 0 if the index doesn't exist, matching update()/retrieve().
        """
        try:
            self._ensure_index()
        except RequestError:
            return 0

        try:
            info = ft.info(self._client, self.config.index_name)
        except RequestError:
            return 0

        num_docs = info.get(b"num_docs") or info.get("num_docs")
        try:
            return int(_decode(num_docs))
        except (TypeError, ValueError):
            return 0
