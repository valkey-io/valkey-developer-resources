"""OpenAI + Valkey getting started: embed text, index it, and run KNN search.

Corresponds to cookbook: 01-getting-started.md.

The default path uses deterministic local embeddings so this sample runs
without credentials. Set OPENAI_API_KEY to use the optional OpenAI embedder.
"""

from __future__ import annotations

import asyncio
import json

import numpy as np
from glide import ft, glide_json
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

INDEX_NAME = "openai-getting-started"
PREFIX = "doc:"

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


async def create_index(client) -> None:
    """Create a JSON FLAT index whose dimension matches the selected embedder."""
    await drop_index(client, INDEX_NAME)
    schema = [
        TagField("$.title", alias="title"),
        TagField("$.url", alias="url"),
        TagField("$.text", alias="text"),
        VectorField(
            name="$.content_vector",
            alias="content_vector",
            algorithm=VectorAlgorithm.FLAT,  # exact search for smaller collections
            attributes=VectorFieldAttributesFlat(
                dimensions=embedding_dimension(),
                distance_metric=DistanceMetricType.COSINE,
                type=VectorType.FLOAT32,
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
    """Embed and store the documents through GLIDE's JSON API."""
    vectors = embed([doc["text"] for doc in documents])
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


async def search(client, query: str, k: int = 3) -> list[dict]:
    """Run a KNN search with a bound vector parameter."""
    query_blob = np.array(embed([query])[0], dtype=np.float32).tobytes()
    _, docs = await ft.search(
        client,
        INDEX_NAME,
        f"(*)=>[KNN {k} @content_vector $query_vec AS vector_score]",
        FtSearchOptions(
            params={"query_vec": query_blob},
            return_fields=[
                ReturnField("title"),
                ReturnField("url"),
                ReturnField("vector_score"),
            ],
            dialect=2,
        ),
    )
    return [
        {
            "key": key.decode() if isinstance(key, bytes) else str(key),
            "title": field_text(fields, "title"),
            "url": field_text(fields, "url"),
            "similarity": vector_similarity(fields),
        }
        for key, fields in docs.items()
    ]


async def run_demo() -> list[dict]:
    """Run one complete, idempotent demo and clean up on every exit path."""
    client = await create_client()
    keys: list[str] = []
    try:
        assert await client.ping()
        await create_index(client)
        await index_documents(client, DOCUMENTS, keys)
        results = await search(client, "open source in-memory database")
        assert results, "Vector search returned no results"
        assert any(result["title"] == "Valkey" for result in results)
        return results
    finally:
        try:
            await cleanup(client, INDEX_NAME, keys)
        finally:
            try:
                close_embedder()
            finally:
                await client.close()


async def main() -> None:
    results = await run_demo()
    for result in results:
        print(
            f"{result['key']}: {result['title']} "
            f"(similarity: {result['similarity']:.3f})"
        )


if __name__ == "__main__":
    asyncio.run(main())
