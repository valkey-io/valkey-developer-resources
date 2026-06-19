"""LangBot + Valkey Search vector backend — runnable demo.

Corresponds to cookbooks:
  03-vector-search.md  (index + KNN)
  04-hybrid-and-filtering.md  (full-text, hybrid, file_id filtering, deletion)

Uses a tiny deterministic local embedding (hashing words into a fixed-dim
vector) so the demo needs no API keys or model downloads. This is NOT a real
embedding model — it only illustrates the Valkey Search mechanics.

Run against a local valkey-bundle (search module required):
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    python vector_search.py

Config via environment (defaults shown):
    VALKEY_HOST=localhost
    VALKEY_PORT=6379
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import struct
import sys

try:
    from glide import (
        DataType,
        DistanceMetricType,
        FtCreateOptions,
        FtSearchLimit,
        FtSearchOptions,
        GlideClient,
        GlideClientConfiguration,
        NodeAddress,
        RequestError,
        ReturnField,
        TagField,
        TextField,
        VectorAlgorithm,
        VectorField,
        VectorFieldAttributesHnsw,
        VectorType,
        ft,
    )
except ImportError:
    print("valkey-glide is not installed. Install it with:")
    print("    pip install 'valkey-glide>=2.4.1,<3.0.0'")
    sys.exit(1)


COLLECTION = "langbot_kb_demo"
DIM = 64  # embedding dimension; must match the index and all stored vectors


# --------------------------------------------------------------------------- #
# Tiny deterministic embedding (demo only — not a real model)
# --------------------------------------------------------------------------- #
def embed(text: str, dim: int = DIM) -> list[float]:
    """Hash each word into a fixed-dim bag-of-words vector, L2-normalized.

    Shared words -> overlapping dimensions -> smaller COSINE distance, which is
    enough to show KNN ranking. Real deployments use a proper embedding model.
    """
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0  # avoid divide-by-zero
    return [x / norm for x in vec]


def pack_vector(vec: list[float]) -> bytes:
    # '<' little-endian, 'f' float32 — the exact layout Valkey Search expects.
    return struct.pack(f"<{len(vec)}f", *[float(x) for x in vec])


def _decode(value: object) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


# --------------------------------------------------------------------------- #
# Client + index
# --------------------------------------------------------------------------- #
async def create_client() -> GlideClient:
    config = GlideClientConfiguration(
        addresses=[
            NodeAddress(
                os.environ.get("VALKEY_HOST", "localhost"),
                int(os.environ.get("VALKEY_PORT", "6379")),
            )
        ],
        client_name="langbot_vector_client",
        # GLIDE defaults to 250ms; 5s is a safe cookbook default. Tune for latency.
        request_timeout=5000,
    )
    return await GlideClient.create(config)


def index_name(collection: str) -> str:
    return f"idx:{collection}"


def key_prefix(collection: str) -> str:
    return f"kb:{collection}:"


async def index_exists(client: GlideClient, index: str) -> bool:
    # FT.INFO on a single index is O(1); FT._LIST returns every index name on
    # the server (O(n)). RequestError means the index doesn't exist.
    try:
        await ft.info(client, index)
        return True
    except RequestError:
        return False


async def ensure_index(client: GlideClient, collection: str, dim: int) -> None:
    index = index_name(collection)
    if await index_exists(client, index):
        return  # already exists — no list-then-create TOCTOU window
    attrs = VectorFieldAttributesHnsw(
        dimensions=dim,
        distance_metric=DistanceMetricType.COSINE,  # COSINE | L2 | IP
        type=VectorType.FLOAT32,
    )
    schema = [
        # HNSW mirrors LangBot's configured default. For a demo this tiny
        # (4 docs) FLAT would also be fine — cookbook 03 suggests FLAT below
        # ~10,000 vectors — but we follow the backend's default here.
        VectorField(name="vector", algorithm=VectorAlgorithm.HNSW, attributes=attrs),
        TagField(name="file_id"),
        TextField(name="document"),
    ]
    options = FtCreateOptions(data_type=DataType.HASH, prefixes=[key_prefix(collection)])
    await ft.create(client, index, schema, options)


# --------------------------------------------------------------------------- #
# Write
# --------------------------------------------------------------------------- #
async def add_documents(
    client: GlideClient,
    collection: str,
    ids: list[str],
    documents: list[str],
    file_ids: list[str],
) -> None:
    await ensure_index(client, collection, DIM)
    prefix = key_prefix(collection)
    # One HSET per chunk. Fine for a handful of docs; for hundreds of chunks,
    # batch the writes with the GLIDE Batch/Pipeline API to avoid N round trips.
    for _id, doc, file_id in zip(ids, documents, file_ids):
        metadata = {"file_id": file_id}
        mapping = {
            "vector": pack_vector(embed(doc)),
            "document": doc,
            "file_id": file_id,  # normal id (UUID/slug) -> no encoding needed
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
        }
        await client.hset(prefix + _id, mapping)


# --------------------------------------------------------------------------- #
# Filter / text helpers (escape user-influenced values)
# --------------------------------------------------------------------------- #
_FT_UNSAFE = frozenset("{}*%")


def encode_file_id(value: str) -> str:
    # Percent-encode the chars the TAG parser can't handle even when escaped
    # (plus '%' for reversibility). Normal UUID/hash ids are unchanged (no-op).
    out = []
    for ch in str(value):
        out.append("%{:02X}".format(ord(ch)) if ch in _FT_UNSAFE else ch)
    return "".join(out)


def escape_tag(value: str) -> str:
    out = []
    for ch in str(value):  # escape backslash first
        if ch in '\\,.<>{}[]"\':;!@#$%^&*()-+=~| ':
            out.append("\\")
        out.append(ch)
    return "".join(out)


def file_id_filter(file_id: str) -> str:
    # Mirror the cookbook's safe pattern: percent-encode the TAG-unsafe chars
    # ({ } * %) that backslash-escaping alone can't neutralize, then escape the
    # rest. Plain UUID/slug ids pass through unchanged.
    return f"@file_id:{{{escape_tag(encode_file_id(file_id))}}}"


def escape_text(term: str) -> str:
    out = []
    for ch in str(term):
        if ch in '@!{}[]()|-"~*:\\':
            out.append("\\")
        out.append(ch)
    return "".join(out)


def build_text_clause(text: str) -> str:
    return " ".join(f"@document:{escape_text(w)}" for w in text.split() if w)


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #
def _parse_reply(collection: str, reply: object, has_distance: bool) -> list[dict]:
    results: list[dict] = []
    if not reply or len(reply) < 2 or not isinstance(reply[1], dict):
        return results
    prefix = key_prefix(collection)
    for key, fields in reply[1].items():
        decoded = {_decode(fk): fv for fk, fv in fields.items()} if isinstance(fields, dict) else {}
        key_str = _decode(key)
        # The KNN score comes back under its AS-name (__vec_score).
        score = decoded.get("__vec_score")
        results.append(
            {
                "id": key_str[len(prefix):] if key_str.startswith(prefix) else key_str,
                "distance": float(_decode(score)) if has_distance and score is not None else None,
                "document": _decode(decoded["document"]) if "document" in decoded else None,
            }
        )
    return results


async def knn_search(client: GlideClient, collection: str, pre: str, query_vec: list[float], k: int) -> list[dict]:
    index = index_name(collection)
    # 'AS __vec_score' names the KNN distance so we can request it back.
    query = f"{pre}=>[KNN {k} @vector $BLOB AS __vec_score]"
    options = FtSearchOptions(
        params={"BLOB": pack_vector(query_vec)},
        return_fields=[
            ReturnField(field_identifier="__vec_score"),
            ReturnField(field_identifier="document"),
            ReturnField(field_identifier="metadata_json"),
        ],
        limit=FtSearchLimit(0, k),
        dialect=2,  # required for KNN bound params
    )
    reply = await ft.search(client, index, query, options)
    return _parse_reply(collection, reply, has_distance=True)


async def vector_search(client, collection, query_text, k=5):
    return await knn_search(client, collection, "*", embed(query_text), k)


async def hybrid_search(client, collection, query_text, file_id=None, k=5):
    parts = []
    if file_id:
        parts.append(file_id_filter(file_id))
    if query_text:
        parts.append(build_text_clause(query_text))
    pre = " ".join(p for p in parts if p) or "*"
    return await knn_search(client, collection, pre, embed(query_text), k)


async def full_text_search(client, collection, query_text, k=5):
    index = index_name(collection)
    clause = build_text_clause(query_text)
    if not clause:
        return []
    options = FtSearchOptions(
        return_fields=[ReturnField(field_identifier="document"), ReturnField(field_identifier="metadata_json")],
        limit=FtSearchLimit(0, k),
        dialect=2,
    )
    reply = await ft.search(client, index, clause, options)
    return _parse_reply(collection, reply, has_distance=False)


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #
async def search_keys(client: GlideClient, index: str, query: str, batch: int = 10000) -> list[str]:
    """Enumerate all matching keys (NOCONTENT), paginated, with a bounded loop."""
    keys: list[str] = []
    offset = 0
    max_pages = 1000  # safety cap so the loop can never spin forever
    for _ in range(max_pages):
        options = FtSearchOptions(nocontent=True, limit=FtSearchLimit(offset, batch), dialect=2)
        reply = await ft.search(client, index, query, options)
        if not reply or len(reply) < 2:
            break
        try:
            total = int(reply[0])
        except (TypeError, ValueError):
            total = 0
        docs = reply[1]
        page = [_decode(k) for k in (docs.keys() if isinstance(docs, dict) else docs or [])]
        if not page:
            break
        keys.extend(page)
        offset += len(page)
        if offset >= total or len(page) < batch:
            break
    return keys


async def delete_by_file_id(client: GlideClient, collection: str, file_id: str) -> int:
    index = index_name(collection)
    if not await index_exists(client, index):
        return 0
    keys = await search_keys(client, index, file_id_filter(file_id))
    if keys:
        # Multi-key DEL: safe on standalone Valkey. In cluster mode these
        # kb:{collection}: keys have no common hash tag and scatter across
        # slots (CrossSlotError) — delete per-key or add a hash-tagged prefix.
        await client.delete(keys)
    return len(keys)


async def delete_collection(client: GlideClient, collection: str) -> int:
    index = index_name(collection)
    if await index_exists(client, index):
        try:
            await ft.dropindex(client, index)
        except RequestError:
            pass  # index already gone — anything else (conn/auth) propagates
    prefix = key_prefix(collection)
    cursor: object = b"0"
    deleted = 0
    max_rounds = 1000  # safety cap
    for _ in range(max_rounds):
        cursor, keys = await client.scan(cursor, match=f"{prefix}*", count=500)
        if keys:
            await client.delete(keys)
            deleted += len(keys)
        if cursor in (b"0", "0", 0):
            break
    return deleted


# --------------------------------------------------------------------------- #
# Indexing is async — poll instead of a blind sleep.
# --------------------------------------------------------------------------- #
async def poll_until(coro_factory, predicate, attempts: int = 20, delay: float = 0.25):
    """Retry an async query until `predicate(result)` is true or attempts run out."""
    result = None
    for _ in range(attempts):
        result = await coro_factory()
        if predicate(result):
            return result
        await asyncio.sleep(delay)
    return result


async def main() -> None:
    client = await create_client()
    try:
        # Idempotent: clear any leftovers from a prior interrupted run.
        await delete_collection(client, COLLECTION)

        docs = [
            "Valkey is a high performance in-memory data store",
            "Vector search finds similar embeddings using KNN",
            "LangBot builds agentic instant messaging bots",
            "Rate limiting protects services from request floods",
        ]
        ids = [f"chunk-{i}" for i in range(len(docs))]
        # Two source files: first two chunks from fileA, last two from fileB.
        file_ids = ["fileA", "fileA", "fileB", "fileB"]
        await add_documents(client, COLLECTION, ids, docs, file_ids)

        # 1) Vector search — wait for the async indexer to surface results.
        print("\n=== Vector search: 'similar vector embeddings' ===")
        hits = await poll_until(
            lambda: vector_search(client, COLLECTION, "similar vector embeddings", k=3),
            predicate=lambda r: len(r) > 0,
        )
        for h in hits:
            print(f"  {h['id']}: distance={h['distance']:.4f} :: {h['document']!r}")
        assert hits, "vector search returned no results (indexing lag?)"
        # The embeddings doc shares the most query words -> should rank first.
        assert hits[0]["id"] == "chunk-1", f"unexpected top hit: {hits[0]['id']}"

        # 2) Full-text search.
        print("\n=== Full-text search: 'bots' ===")
        ft_hits = await full_text_search(client, COLLECTION, "bots", k=5)
        for h in ft_hits:
            print(f"  {h['id']} :: {h['document']!r}")
        assert any(h["id"] == "chunk-2" for h in ft_hits), "expected the LangBot doc"

        # 3) Hybrid: filter to fileB, then KNN rank.
        print("\n=== Hybrid: file_id=fileB + KNN ===")
        hy = await hybrid_search(client, COLLECTION, "messaging bots", file_id="fileB", k=5)
        for h in hy:
            print(f"  {h['id']}: distance={h['distance']:.4f} :: {h['document']!r}")
        assert hy, "hybrid search returned no results"
        assert all(h["id"] in ("chunk-2", "chunk-3") for h in hy), "filter leaked outside fileB"

        # 4) Delete one source file and confirm its chunks are gone.
        print("\n=== Delete by file_id: fileA ===")
        removed = await delete_by_file_id(client, COLLECTION, "fileA")
        print(f"  removed {removed} chunk(s)")
        assert removed == 2, f"expected to delete 2 chunks, deleted {removed}"
        remaining = await poll_until(
            lambda: hybrid_search(client, COLLECTION, "data store", file_id="fileA", k=5),
            predicate=lambda r: len(r) == 0,
        )
        assert remaining == [], "fileA chunks still present after delete"

        print("\nAll vector-search demos passed.")
    finally:
        # Clean up the demo collection, then close the connection.
        try:
            await delete_collection(client, COLLECTION)
        finally:
            await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"\nAssertion failed: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — friendly top-level message
        print(f"\nError: {exc}")
        print("Is valkey-bundle running? Try:")
        print("    docker run -d -p 6379:6379 valkey/valkey-bundle:latest")
        sys.exit(1)
