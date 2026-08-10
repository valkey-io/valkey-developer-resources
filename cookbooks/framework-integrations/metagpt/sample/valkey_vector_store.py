"""Standalone reimplementation of MetaGPT's ``ValkeyVectorStore``.

This module reproduces the verified store/query/delete/lifecycle behavior of
FoundationAgents/MetaGPT's ``ValkeyVectorStore`` RAG backend (see upstream pull
request https://github.com/FoundationAgents/MetaGPT/pull/2063, open/unmerged
at the time of writing) using the real ``valkey-glide-sync`` (``glide_sync``)
API directly. It does NOT import ``metagpt`` — the Valkey RAG backend is not
yet part of a published ``metagpt`` release, and per this repository's
contribution guidelines a sample must never require building unreleased
software. This module is independently runnable and depends only on
``valkey-glide-sync`` and ``llama-index-core`` (for the ``TextNode`` /
``VectorStoreQuery`` / ``BaseNode`` shapes MetaGPT's RAG module already uses).

Reproduced behavior (verified against upstream's
``metagpt/rag/vector_stores/valkey.py`` at the PR head):
    - Connection: a single synchronous ``GlideClient``, created lazily on
      first use. ``client_name`` defaults to ``"metagpt_rag_client"``.
    - Index schema: ``FT.CREATE <index_name> ON JSON PREFIX 1 <prefix>
      SCHEMA $.text AS text TEXT $.doc_id AS doc_id TEXT $.ref_doc_id AS
      ref_doc_id TEXT $.metadata AS metadata TEXT $.vector AS vector VECTOR
      <HNSW|FLAT> ...`` — built over JSON documents, not Hashes.
    - Keys: ``f"{prefix}{doc_id}"``, one JSON document per node. Keys carry
      NO hash tag, so a single atomic batch write only holds together in
      Valkey standalone mode (see the cluster-mode caveat below).
    - Writes: ``add()`` batches nodes in groups of up to 100 (``_BATCH_SIZE``)
      and writes each group as a single ``glide_sync.Batch(is_atomic=True)``
      transaction — one round trip, all-or-nothing per batch — via
      ``json_batch.set()`` + ``client.exec(batch, raise_on_error=True)``.
      On failure the raised error reports how many documents were durably
      written before the failing batch, so callers can retry without
      re-inserting duplicates.
    - Deletes: ``delete(ref_doc_id)`` scans every key under the prefix (via
      ``SCAN``, never the blocking ``KEYS``), reads each back with
      ``JSON.GET``, and matches on ``ref_doc_id`` OR ``doc_id`` before
      issuing a single ``DEL`` for the matched keys. Falls back to deleting
      ``f"{prefix}{ref_doc_id}"`` directly if nothing matched.
    - Query: ``query()`` runs ``FT.SEARCH`` with a KNN clause
      (``*=>[KNN <k> @vector $query_vec AS score]``), passing the query
      vector as a bound parameter (``$query_vec``, packed with
      ``struct.pack``), never interpolated into the query string. For
      ``COSINE`` the raw distance is converted to similarity as
      ``1.0 - score``; for ``L2``/``IP`` it is negated (``-score``) to
      preserve ranking order without claiming a calibrated probability.
    - Lifecycle: ``drop_index()`` checks ``FT._LIST`` first (via
      ``ft.list()``) and skips ``FT.DROPINDEX`` when the index is absent,
      then always cleans up orphaned prefixed keys via bounded ``SCAN`` +
      ``DEL``. This makes it a safe, idempotent reset to call at the top of
      a script, even on the very first run.

Cluster-mode caveat (preserved from the upstream design): the atomic batch
write in ``add()`` only works in Valkey standalone mode. In Valkey Cluster,
every key in a transaction must hash to the same slot, but these document
keys carry no hash tags and will scatter across slots. Run Valkey standalone
for this integration unless you extend the key format with a shared hash tag.

Query injection caveat: never interpolate unsanitized user input into an
``FT.SEARCH`` query string. The KNN clause here is safe because the filter
portion is always the hardcoded wildcard ``*`` and the vector is passed as a
bound parameter (``$query_vec``) — but the ``=>`` token separates the filter
expression from the KNN clause, so a filter built from unsanitized input
(e.g. ``@category:{user_input}=>[KNN ...]``) is exploitable for injection.
"""

from __future__ import annotations

import json
import logging
import struct
from typing import Any, List, Literal, Optional

from glide_sync import (
    Batch,
    DataType,
    DistanceMetricType,
    FtCreateOptions,
    FtSearchOptions,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ReturnField,
    RequestError,
    ServerCredentials,
    TextField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesFlat,
    VectorFieldAttributesHnsw,
    VectorType,
    ft,
    glide_json,
    json_batch,
)
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.vector_stores.types import VectorStoreQuery, VectorStoreQueryResult

logger = logging.getLogger(__name__)

_MAX_SCAN_ITERATIONS = 10000
_BATCH_SIZE = 100


class ValkeyVectorStore:
    """Valkey-based vector store using the sync valkey-glide client and Valkey Search module.

    This is a standalone reimplementation, not a subclass of llama-index's
    ``BasePydanticVectorStore`` (which upstream's real ``ValkeyVectorStore``
    extends so it can plug into MetaGPT's RAG engine). It exposes the same
    methods with the same behavior against real Valkey, so the cookbook's
    code examples are runnable without installing MetaGPT.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        use_tls: bool = False,
        request_timeout: int = 5000,
        index_name: str = "metagpt_rag",
        prefix: str = "metagpt:rag:",
        vector_dimensions: int = 1536,
        distance_metric: Literal["COSINE", "L2", "IP"] = "COSINE",
        vector_algorithm: Literal["HNSW", "FLAT"] = "HNSW",
        client_name: str = "metagpt_rag_client",
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.use_tls = use_tls
        self.request_timeout = request_timeout
        self.index_name = index_name
        self.prefix = prefix
        self.vector_dimensions = vector_dimensions
        self.distance_metric = distance_metric
        self.vector_algorithm = vector_algorithm
        self.client_name = client_name

        self._client: Optional[Any] = None

    def __repr__(self) -> str:
        """Redact the password so it never leaks into reprs / tracebacks / logs."""
        return (
            "ValkeyVectorStore("
            f"host={self.host!r}, port={self.port!r}, "
            f"password={'***' if self.password else None!r}, "
            f"use_tls={self.use_tls!r}, index_name={self.index_name!r}, "
            f"prefix={self.prefix!r}, vector_dimensions={self.vector_dimensions!r}, "
            f"distance_metric={self.distance_metric!r}, vector_algorithm={self.vector_algorithm!r})"
        )

    @property
    def client(self) -> Any:
        """Get the underlying Valkey client."""
        return self._client

    def _connect(self) -> None:
        """Create a synchronous GlideClient connection to Valkey."""
        if self.password and not self.use_tls:
            logger.warning(
                "Valkey password is configured but TLS is disabled — credentials will be sent "
                "in cleartext. Set use_tls=True for any non-local deployment."
            )

        addresses = [NodeAddress(host=self.host, port=self.port)]
        config_kwargs: dict[str, Any] = {
            "addresses": addresses,
            "client_name": self.client_name,
            "use_tls": self.use_tls,
            "request_timeout": self.request_timeout,
        }

        if self.password:
            config_kwargs["credentials"] = ServerCredentials(password=self.password)

        config = GlideClientConfiguration(**config_kwargs)
        self._client = GlideClient.create(config)

        logger.info("Connected to Valkey at %s:%s", self.host, self.port)

    def _index_exists(self) -> bool:
        """Return True if the configured index already exists, using FT._LIST.

        Uses ft.list() rather than try/except + error-string matching, which is
        fragile against server-version message changes and can swallow unrelated errors.
        """
        existing = ft.list(self._client)
        names = {i.decode() if isinstance(i, (bytes, bytearray)) else str(i) for i in (existing or [])}
        return self.index_name in names

    def ensure_index(self) -> None:
        """Create the FT.SEARCH index if it does not already exist.

        Guards its own connection so callers cannot misuse it before _connect().
        """
        if self._client is None:
            self._connect()

        if self._index_exists():
            logger.debug("Index %s already exists, skipping creation", self.index_name)
            return

        distance_map = {
            "COSINE": DistanceMetricType.COSINE,
            "L2": DistanceMetricType.L2,
            "IP": DistanceMetricType.IP,
        }
        algorithm_map = {
            "HNSW": VectorAlgorithm.HNSW,
            "FLAT": VectorAlgorithm.FLAT,
        }

        distance = distance_map[self.distance_metric.upper()]
        algorithm = algorithm_map[self.vector_algorithm.upper()]

        # Select the attribute class that matches the chosen algorithm so that
        # FLAT indexes are not incorrectly created with HNSW parameters.
        if algorithm == VectorAlgorithm.FLAT:
            attributes = VectorFieldAttributesFlat(
                dimensions=self.vector_dimensions,
                distance_metric=distance,
                type=VectorType.FLOAT32,
            )
        else:
            attributes = VectorFieldAttributesHnsw(
                dimensions=self.vector_dimensions,
                distance_metric=distance,
                type=VectorType.FLOAT32,
            )

        schema = [
            TextField("$.text", "text"),
            TextField("$.doc_id", "doc_id"),
            TextField("$.ref_doc_id", "ref_doc_id"),
            TextField("$.metadata", "metadata"),
            VectorField(
                name="$.vector",
                alias="vector",
                algorithm=algorithm,
                attributes=attributes,
            ),
        ]

        options = FtCreateOptions(data_type=DataType.JSON, prefixes=[self.prefix])
        ft.create(self._client, self.index_name, schema, options)
        logger.info("Created Valkey search index: %s", self.index_name)

    def add(self, nodes: List[BaseNode], **add_kwargs: Any) -> List[str]:
        """Add nodes to the vector store.

        Each chunk of up to ``_BATCH_SIZE`` JSON.SET writes is sent as a single
        atomic GLIDE ``Batch`` (one round-trip, all-or-nothing). On failure the
        raised error reports how many documents were durably written, so callers
        can retry without re-inserting duplicates.
        """
        if self._client is None:
            self._connect()
            self.ensure_index()

        ids: List[str] = []
        written = 0
        for i in range(0, len(nodes), _BATCH_SIZE):
            chunk = nodes[i : i + _BATCH_SIZE]
            batch = Batch(is_atomic=True)
            chunk_ids: List[str] = []
            for node in chunk:
                doc_id = node.node_id
                embedding = node.get_embedding()
                text = node.get_content(metadata_mode=MetadataMode.NONE) or ""
                metadata = node.metadata or {}

                doc_data = {
                    "doc_id": doc_id,
                    "ref_doc_id": node.ref_doc_id or doc_id,
                    "text": text,
                    "metadata": json.dumps(metadata),
                    "vector": list(embedding),
                }

                key = f"{self.prefix}{doc_id}"
                json_batch.set(batch, key, "$", json.dumps(doc_data))
                chunk_ids.append(doc_id)

            try:
                self._client.exec(batch, raise_on_error=True)
            except Exception as e:
                raise RuntimeError(
                    f"Valkey batch insert failed after {written} document(s) were written "
                    f"(failing chunk offset {i}, size {len(chunk)}): {e}"
                ) from e

            written += len(chunk_ids)
            ids.extend(chunk_ids)

        logger.info("Added %s documents to Valkey index %s", len(ids), self.index_name)
        return ids

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """Delete all nodes belonging to a source document.

        In llama-index, ``ref_doc_id`` is the source-document id and a single
        source may be chunked into many nodes. This deletes every stored key
        whose ``ref_doc_id`` (or ``doc_id``) matches, so no orphaned chunks remain.
        """
        if self._client is None:
            self._connect()

        keys_to_delete: List[str] = []
        for batch in self._iter_prefix_keys():
            for key in batch:
                raw = glide_json.get(self._client, key, "$")
                if raw is None:
                    continue
                raw_str = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                try:
                    docs = json.loads(raw_str)
                    doc = docs[0] if isinstance(docs, list) else docs
                except (json.JSONDecodeError, TypeError, IndexError):
                    continue
                if doc.get("ref_doc_id") == ref_doc_id or doc.get("doc_id") == ref_doc_id:
                    keys_to_delete.append(key)

        # Fall back to direct key deletion if nothing matched (e.g. legacy docs
        # without a stored ref_doc_id field).
        if not keys_to_delete:
            keys_to_delete = [f"{self.prefix}{ref_doc_id}"]

        deleted = self._client.delete(keys_to_delete)
        logger.debug("Deleted %s key(s) for ref_doc_id %s from Valkey", deleted, ref_doc_id)

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """Query the vector store with a KNN vector search."""
        if self._client is None:
            self._connect()
            self.ensure_index()

        top_k = query.similarity_top_k or 5
        query_embedding = query.query_embedding or []

        if len(query_embedding) != self.vector_dimensions:
            raise ValueError(
                f"Query embedding dimension {len(query_embedding)} does not match "
                f"index dimension {self.vector_dimensions}."
            )

        vector_bytes = struct.pack(f"{len(query_embedding)}f", *query_embedding)

        # KNN query using FT.SEARCH. The filter portion is always the hardcoded
        # wildcard "*" — never build this string from unsanitized user input.
        ft_query = f"*=>[KNN {top_k} @vector $query_vec AS score]"
        options = FtSearchOptions(
            return_fields=[
                ReturnField("text"),
                ReturnField("metadata"),
                ReturnField("doc_id"),
                ReturnField("score"),
            ],
            params={"query_vec": vector_bytes},
        )

        results = ft.search(self._client, self.index_name, ft_query, options)

        nodes: List[Any] = []
        similarities: List[float] = []
        ids: List[str] = []

        # FT.SEARCH returns exactly two elements: [count, {key: {field: value}}].
        if not (isinstance(results, (list, tuple)) and len(results) >= 2):
            if results and (not isinstance(results, (list, tuple)) or len(results) != 1):
                logger.warning(
                    "Unexpected FT.SEARCH response shape for index %s: %r",
                    self.index_name,
                    results,
                )
            return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

        if not isinstance(results[0], int):
            logger.warning(
                "FT.SEARCH first element is not an int count for index %s: %r",
                self.index_name,
                results[0],
            )

        docs_dict = results[1]
        if not isinstance(docs_dict, dict):
            logger.warning(
                "FT.SEARCH payload is not a mapping for index %s: %r",
                self.index_name,
                docs_dict,
            )
            return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

        # Imported lazily to keep this module's top-level imports minimal and
        # mirror upstream's own usage of TextNode only inside query().
        from llama_index.core.schema import TextNode

        for key, field_dict in docs_dict.items():
            if not isinstance(field_dict, dict):
                continue

            decoded = {}
            for fk, fv in field_dict.items():
                k_str = fk.decode("utf-8") if isinstance(fk, (bytes, bytearray)) else str(fk)
                v_str = fv.decode("utf-8") if isinstance(fv, (bytes, bytearray)) else str(fv)
                decoded[k_str] = v_str

            doc_id = decoded.get("doc_id", "")
            text = decoded.get("text", "")
            metadata_str = decoded.get("metadata", "{}")
            score_str = decoded.get("score", "0")

            metadata = self._parse_metadata(metadata_str, doc_id)
            similarity = self._parse_similarity(score_str, doc_id)

            nodes.append(TextNode(id_=doc_id, text=text, metadata=metadata))
            similarities.append(similarity)
            ids.append(doc_id)

        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

    def _parse_metadata(self, metadata_str: str, doc_id: str) -> dict:
        """Parse stored metadata JSON, logging (not silently swallowing) corruption."""
        try:
            return json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            # Handle escaped JSON that can come back from JSON-path retrieval.
            try:
                return json.loads(metadata_str.replace('\\"', '"'))
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Failed to parse metadata for doc %s, raw: %s",
                    doc_id,
                    str(metadata_str)[:200],
                )
                return {}

    def _parse_similarity(self, score_str: str, doc_id: str) -> float:
        """Convert a FT.SEARCH distance score into a similarity, logging parse failures."""
        try:
            score = float(score_str)
        except (ValueError, TypeError):
            logger.warning(
                "Failed to parse score for doc %s, raw: %s",
                doc_id,
                str(score_str)[:200],
            )
            return 0.0
        if self.distance_metric.upper() == "COSINE":
            return 1.0 - score
        return -score

    def check_connection(self) -> bool:
        """Check if the Valkey connection is alive."""
        try:
            if self._client is None:
                self._connect()
            self._client.ping()
            return True
        except (OSError, RequestError) as e:
            logger.error("Valkey connection check failed: %s", e)
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Disconnect from Valkey."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def drop_index(self) -> None:
        """Drop the search index and clean up all associated keys."""
        if self._client is None:
            self._connect()

        if self._index_exists():
            ft.dropindex(self._client, self.index_name)
            logger.info("Dropped Valkey search index: %s", self.index_name)
        else:
            logger.debug("Index %s not found, proceeding to clean orphaned keys", self.index_name)

        # Always clean up orphaned keys with prefix
        self._cleanup_prefix_keys()

    def _iter_prefix_keys(self, max_keys: Optional[int] = None):
        """Yield batches of keys matching the configured prefix via SCAN.

        Bounded by _MAX_SCAN_ITERATIONS to guard against unbounded keyspaces.
        Stops early once max_keys keys have been yielded in total.
        """
        cursor = "0"
        iterations = 0
        yielded = 0

        while iterations < _MAX_SCAN_ITERATIONS:
            cursor_val, found_keys = self._client.scan(cursor, match=f"{self.prefix}*", count=100)
            cursor = cursor_val.decode("utf-8") if isinstance(cursor_val, (bytes, bytearray)) else str(cursor_val)

            if found_keys:
                batch = [k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k) for k in found_keys]
                if max_keys is not None and yielded + len(batch) >= max_keys:
                    yield batch[: max_keys - yielded]
                    return
                yielded += len(batch)
                yield batch

            if cursor == "0":
                break

            iterations += 1

    def _cleanup_prefix_keys(self) -> None:
        """Remove all keys with the configured prefix using SCAN with a safety limit."""
        total_deleted = 0

        for batch in self._iter_prefix_keys():
            if batch:
                self._client.delete(batch)
                total_deleted += len(batch)

        if total_deleted > 0:
            logger.info("Cleaned up %s orphaned keys with prefix %s", total_deleted, self.prefix)

    def scan_all_docs(self, max_keys: Optional[int] = None) -> List[str]:
        """Scan all document keys with the configured prefix.

        Terminates early once max_keys are collected or _MAX_SCAN_ITERATIONS reached.
        """
        keys: List[str] = []
        for batch in self._iter_prefix_keys(max_keys=max_keys):
            keys.extend(batch)
        return keys
