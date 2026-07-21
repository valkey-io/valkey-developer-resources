"""OpenAI + Valkey vector search: hybrid filtering and the HNSW index.

Corresponds to cookbook: 02-vector-search.md.

The default path uses deterministic local embeddings so this sample runs
without credentials. Set OPENAI_API_KEY to use the optional OpenAI embedder.
"""

from __future__ import annotations

import asyncio
import json
import re

import numpy as np
from glide import ft, glide_json
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

from common import (
    cleanup,
    close_embedder,
    create_client,
    drop_index,
    embed,
    embedding_dimension,
    field_text,
    vector_similarity,
)

INDEX_NAME = "openai-vector-search"
PREFIX = "article:"

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


async def create_hnsw_index(client) -> None:
    await drop_index(client, INDEX_NAME)
    schema = [
        TagField("$.genre", alias="genre"),
        TagField("$.title", alias="title"),
        TagField("$.text", alias="text"),
        VectorField(
            name="$.content_vector",
            alias="content_vector",
            algorithm=VectorAlgorithm.HNSW,
            attributes=VectorFieldAttributesHnsw(
                dimensions=embedding_dimension(),
                distance_metric=DistanceMetricType.COSINE,
                type=VectorType.FLOAT32,
                number_of_edges=16,                   # M: graph connectivity
                vectors_examined_on_construction=200,  # ef_construction: build quality
            ),
        ),
    ]
    await ft.create(
        client,
        INDEX_NAME,
        schema,
        FtCreateOptions(data_type=DataType.JSON, prefixes=[PREFIX]),
    )


async def index_documents(
    client, documents: list[dict], tracked_keys: list[str] | None = None
) -> list[str]:
    vectors = embed([doc["text"] for doc in documents])
    # Demo loop; batch with the client's pipeline API for large corpora.
    keys = tracked_keys if tracked_keys is not None else []
    for doc, vector in zip(documents, vectors):
        key = f"{PREFIX}{doc['id']}"
        keys.append(key)
        await glide_json.set(
            client,
            key,
            "$",
            json.dumps({**doc, "content_vector": vector}),
        )
    return keys


def validate_genre(genre: str) -> str:
    """Allow only simple TAG values before placing them in query syntax."""
    if genre and not re.fullmatch(r"[A-Za-z0-9_-]+", genre):
        raise ValueError("genre must contain only letters, digits, '_' or '-'")
    return genre


def validate_k(k: int) -> int:
    """Bound KNN result size before placing it in query syntax."""
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 1000:
        raise ValueError("k must be an integer between 1 and 1000")
    return k


async def search(client, query: str, k: int = 3, genre: str = "") -> list[dict]:
    genre = validate_genre(genre)
    k = validate_k(k)
    query_blob = np.array(embed([query])[0], dtype=np.float32).tobytes()
    filter_expr = f"@genre:{{{genre}}}" if genre else "*"
    _, docs = await ft.search(
        client,
        INDEX_NAME,
        f"({filter_expr})=>[KNN {k} @content_vector $query_vec AS vector_score]",
        FtSearchOptions(
            params={"query_vec": query_blob},
            return_fields=[
                ReturnField("title"),
                ReturnField("genre"),
                ReturnField("vector_score"),
            ],
            dialect=2,
        ),
    )
    return [
        {
            "key": key.decode() if isinstance(key, bytes) else str(key),
            "title": field_text(fields, "title"),
            "genre": field_text(fields, "genre"),
            "similarity": vector_similarity(fields),
        }
        for key, fields in docs.items()
    ]


async def run_demo() -> tuple[list[dict], list[dict]]:
    client = await create_client()
    keys: list[str] = []
    try:
        assert await client.ping()
        await create_hnsw_index(client)
        await index_documents(client, DOCUMENTS, keys)
        unfiltered = await search(client, "classical composer")
        filtered = await search(client, "in-memory database", genre="tech")
        assert unfiltered, "Vector search returned no results"
        assert filtered, "Hybrid search returned no results"
        assert all(result["genre"] == "tech" for result in filtered)
        return unfiltered, filtered
    finally:
        try:
            await cleanup(client, INDEX_NAME, keys)
        finally:
            try:
                close_embedder()
            finally:
                await client.close()


async def main() -> None:
    unfiltered, filtered = await run_demo()
    print("Unfiltered results:")
    for result in unfiltered:
        print(f"  {result['title']} [{result['genre']}]")
    print("Filtered results:")
    for result in filtered:
        print(f"  {result['title']} [{result['genre']}]")


if __name__ == "__main__":
    asyncio.run(main())
