"""OpenAI + Valkey vector search — hybrid filtering and the HNSW index.

Corresponds to cookbook: 02-vector-search.md

Builds on getting_started.py and shows:
  1. An HNSW index for fast approximate search on larger corpora
  2. Hybrid search: a TAG pre-filter combined with KNN vector search
"""

from __future__ import annotations

import asyncio
import json
import os

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
        VectorFieldAttributesHnsw,
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

load_dotenv()

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))

INDEX_NAME = "openai-vector-search"
PREFIX = "article:"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

DOCUMENTS = [
    {"id": "1", "genre": "music", "title": "Jazz",
     "text": "Jazz is a music genre that originated in New Orleans."},
    {"id": "2", "genre": "music", "title": "Mozart",
     "text": "Wolfgang Amadeus Mozart was a prolific classical composer."},
    {"id": "3", "genre": "tech", "title": "Valkey",
     "text": "Valkey is a high-performance open-source key-value datastore."},
    {"id": "4", "genre": "tech", "title": "Embeddings",
     "text": "Embeddings map text into vectors that capture semantic meaning."},
    {"id": "5", "genre": "aviation", "title": "Cessna",
     "text": "Cessna manufactures small general-aviation aircraft."},
]

openai_client = OpenAI()


def embed(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in response.data]


def to_blob(vector: list[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()


async def create_hnsw_index(client: GlideClient) -> None:
    """Create an HNSW JSON vector index, dropping any stale copy first."""
    try:
        await ft.dropindex(client, INDEX_NAME)
    except RequestError:
        pass  # no-op when the index does not yet exist (clean first run)

    schema = [
        TagField("$.genre", alias="genre"),
        TagField("$.title", alias="title"),
        TagField("$.text", alias="text"),
        VectorField(
            name="$.content_vector",
            alias="content_vector",
            algorithm=VectorAlgorithm.HNSW,  # HNSW = approximate; faster for >1000 docs
            attributes=VectorFieldAttributesHnsw(
                dimensions=EMBED_DIM,
                distance_metric=DistanceMetricType.COSINE,
                type=VectorType.FLOAT32,
                number_of_edges=16,                  # M: graph connectivity (typical 16)
                vectors_examined_on_construction=200,  # ef_construction: build quality
            ),
        ),
    ]
    options = FtCreateOptions(data_type=DataType.JSON, prefixes=[PREFIX])
    await ft.create(client, INDEX_NAME, schema, options)
    print(f"Created HNSW index: {INDEX_NAME}")


async def index_documents(client: GlideClient, documents: list[dict]) -> None:
    vectors = embed([doc["text"] for doc in documents])
    # Demo loop; batch with the client's pipeline API for large corpora.
    for doc, vector in zip(documents, vectors):
        record = {**doc, "content_vector": vector}
        await glide_json.set(client, f"{PREFIX}{doc['id']}", "$", json.dumps(record))
    print(f"Indexed {len(documents)} documents")


async def search(client: GlideClient, query: str, k: int = 3, genre: str = "") -> list[dict]:
    """KNN vector search, optionally pre-filtered to a single genre TAG."""
    query_blob = to_blob(embed([query])[0])

    # Guard the variable-built TAG filter: an empty brace '@genre:{}' silently
    # matches zero documents, so fall back to '*' (match everything) when no
    # genre is supplied. Never interpolate raw user input — '=>' separates the
    # filter from the KNN clause and the vector is a bound parameter.
    filter_expr = f"@genre:{{{genre}}}" if genre else "*"
    knn_query = f"({filter_expr})=>[KNN {k} @content_vector $query_vec AS vector_score]"
    options = FtSearchOptions(
        params={"query_vec": query_blob},
        return_fields=[
            ReturnField("title"),
            ReturnField("genre"),
            ReturnField("vector_score", alias="score"),
        ],
    )
    count, docs = await ft.search(client, INDEX_NAME, knn_query, options)

    results = []
    for key, fields in docs.items():
        raw_score = fields.get(b"score")
        similarity = 1 - float(raw_score) if raw_score is not None else None  # COSINE: sim = 1 - dist
        results.append({
            "key": key.decode(),
            "title": fields.get(b"title", b"").decode(),
            "genre": fields.get(b"genre", b"").decode(),
            "similarity": similarity,
        })
    return results


async def main() -> None:
    config = GlideClientConfiguration(
        addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
        request_timeout=5000,  # 5s; raise for non-localhost network latency
    )
    client = await GlideClient.create(config)
    try:
        print(f"Connected to Valkey: {await client.ping()}")

        await create_hnsw_index(client)
        await index_documents(client, DOCUMENTS)

        print("\nUnfiltered search: 'classical composer'")
        results = await search(client, "classical composer", k=3)
        assert results, "Vector search returned no results"
        for r in results:
            print(f"  {r['key']}: {r['title']} [{r['genre']}] (similarity: {r['similarity']:.3f})")

        print("\nHybrid search (genre=tech): 'in-memory database'")
        filtered = await search(client, "in-memory database", k=3, genre="tech")
        assert filtered, "Hybrid search returned no results"
        assert all(r["genre"] == "tech" for r in filtered), "Filter leaked non-tech docs"
        for r in filtered:
            print(f"  {r['key']}: {r['title']} [{r['genre']}] (similarity: {r['similarity']:.3f})")
    except RequestError as exc:
        print(f"Valkey error: {exc}. Ensure Valkey is running with the search module.")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
