"""OpenAI + Valkey getting started — embed text, index it, run a KNN vector search.

Corresponds to cookbook: 01-getting-started.md

Flow:
  1. Connect to Valkey (valkey-glide async client)
  2. Create a JSON vector index (FLAT) over OpenAI embeddings
  3. Store a handful of documents as JSON
  4. Embed a natural-language query with OpenAI and run KNN vector search
"""

from __future__ import annotations

import asyncio
import json
import os

# Third-party imports are guarded so the most common new-user failure
# (missing dependency) prints an actionable hint instead of a raw traceback.
try:
    import numpy as np
    from dotenv import load_dotenv
    from openai import OpenAI
    from glide import (
        GlideClient,
        GlideClientConfiguration,
        NodeAddress,
        ft,
        glide_json,
    )
    from glide_shared.commands.server_modules.ft_options.ft_create_options import (
        DataType,
        DistanceMetricType,
        FtCreateOptions,
        TagField,
        VectorAlgorithm,
        VectorField,
        VectorFieldAttributesFlat,
        VectorType,
    )
    from glide_shared.commands.server_modules.ft_options.ft_search_options import (
        FtSearchOptions,
        ReturnField,
    )
    from glide_shared.exceptions import RequestError
except ImportError as exc:  # pragma: no cover - dependency hint
    raise SystemExit(
        f"Missing dependency: {exc.name}\n"
        "Install requirements first:\n"
        "    pip install -r requirements.txt"
    )

# Load OPENAI_API_KEY (and optional VALKEY_* overrides) from a local .env file.
load_dotenv()

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

INDEX_NAME = "openai-getting-started"
PREFIX = "doc:"                          # all indexed keys start with this prefix
EMBED_MODEL = "text-embedding-3-small"   # 1536-dimensional embeddings
EMBED_DIM = 1536                         # must match the model's output dimension

# A small, self-contained corpus. In a real app these come from your data source.
DOCUMENTS = [
    {"id": "1", "title": "Valkey", "url": "https://valkey.io",
     "text": "Valkey is an open-source, high-performance key-value datastore."},
    {"id": "2", "title": "Vector Search", "url": "https://valkey.io/topics/search/",
     "text": "Valkey Search adds native vector similarity search and secondary indexing."},
    {"id": "3", "title": "Embeddings", "url": "https://platform.openai.com/docs/guides/embeddings",
     "text": "OpenAI embeddings turn text into dense vectors that capture meaning."},
    {"id": "4", "title": "Caching", "url": "https://valkey.io",
     "text": "Valkey is widely used as an in-memory cache to reduce database load."},
    {"id": "5", "title": "Jazz", "url": "https://simple.wikipedia.org/wiki/Jazz",
     "text": "Jazz is a music genre that originated in the African-American communities."},
]

# The OpenAI client is created once and reused — never re-instantiate per call.
openai_client = OpenAI()


def embed(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input string using OpenAI."""
    response = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in response.data]


def to_blob(vector: list[float]) -> bytes:
    """Pack an embedding into the little-endian float32 bytes Valkey expects."""
    return np.array(vector, dtype=np.float32).tobytes()


async def create_index(client: GlideClient) -> None:
    """Create the JSON vector index, dropping any stale copy first (idempotent)."""
    # dropindex raises RequestError if the index is absent — a safe no-op on a
    # clean first run. Catch only that narrow case so real errors still surface.
    try:
        await ft.dropindex(client, INDEX_NAME)
    except RequestError:
        pass

    schema = [
        TagField("$.title", alias="title"),
        TagField("$.url", alias="url"),
        TagField("$.text", alias="text"),
        VectorField(
            name="$.content_vector",
            alias="content_vector",
            algorithm=VectorAlgorithm.FLAT,  # FLAT = exact search, ideal for <1000 docs
            attributes=VectorFieldAttributesFlat(
                dimensions=EMBED_DIM,
                distance_metric=DistanceMetricType.COSINE,
                type=VectorType.FLOAT32,
            ),
        ),
    ]
    options = FtCreateOptions(data_type=DataType.JSON, prefixes=[PREFIX])
    await ft.create(client, INDEX_NAME, schema, options)
    print(f"Created index: {INDEX_NAME}")


async def index_documents(client: GlideClient, documents: list[dict]) -> None:
    """Embed each document's text and store it as a JSON value in Valkey."""
    vectors = embed([doc["text"] for doc in documents])
    # Demo loop writes one key at a time. For large corpora, batch the writes
    # with the client's Batch/pipeline API to avoid N network round trips.
    for doc, vector in zip(documents, vectors):
        record = {**doc, "content_vector": vector}
        await glide_json.set(client, f"{PREFIX}{doc['id']}", "$", json.dumps(record))
    print(f"Indexed {len(documents)} documents")


async def search(client: GlideClient, query: str, k: int = 3) -> list[dict]:
    """Embed the query and run a KNN vector search against the index."""
    query_blob = to_blob(embed([query])[0])

    # NOTE on query safety: '=>' separates the optional filter from the KNN
    # clause. Never interpolate raw user input into this string. The query
    # vector is passed as a bound parameter ($query_vec), not concatenated.
    knn_query = f"(*)=>[KNN {k} @content_vector $query_vec AS vector_score]"
    options = FtSearchOptions(
        params={"query_vec": query_blob},
        return_fields=[
            ReturnField("title"),
            ReturnField("url"),
            ReturnField("vector_score", alias="score"),
        ],
        dialect=2,  # valkey-search supports only DIALECT 2 for vector queries
    )
    count, docs = await ft.search(client, INDEX_NAME, knn_query, options)

    results = []
    for key, fields in docs.items():
        raw_score = fields.get(b"score")
        # COSINE distance is in [0, 2]; similarity = 1 - distance.
        similarity = 1 - float(raw_score) if raw_score is not None else None
        results.append({
            "key": key.decode(),
            "title": fields.get(b"title", b"").decode(),
            "url": fields.get(b"url", b"").decode(),
            "similarity": similarity,
        })
    return results


async def main() -> None:
    config = GlideClientConfiguration(
        addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
        request_timeout=5000,  # 5s; raise this if your Valkey is not on localhost
    )
    client = await GlideClient.create(config)
    try:
        print(f"Connected to Valkey: {await client.ping()}")

        await create_index(client)
        await index_documents(client, DOCUMENTS)

        query = "open source in-memory database"
        print(f"\nSearching: {query!r}")
        results = await search(client, query, k=3)
        # A query that returns nothing usually means an index/embedding mismatch.
        assert results, "Vector search returned no results"
        for r in results:
            print(f"  {r['key']}: {r['title']} (similarity: {r['similarity']:.3f})")
    except RequestError as exc:
        print(f"Valkey error: {exc}. Ensure Valkey is running with the search module.")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
