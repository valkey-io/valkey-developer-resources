# Getting Started with OpenAI + Valkey

**Beginner** · Python · ~15 min

## What is OpenAI + Valkey?

[OpenAI embeddings](https://platform.openai.com/docs/guides/embeddings) turn text into dense vectors that capture meaning. [Valkey Search](https://valkey.io/topics/search/) is an open-source Valkey module that adds native vector similarity search and secondary indexing to Valkey.

Using Valkey as your vector database for OpenAI embeddings gives you:

* **Single-digit millisecond search** — vector similarity over Valkey Hash and JSON data
* **Exact or approximate search** — FLAT (brute-force) for exact recall, HNSW for speed at scale
* **Hybrid queries** — combine vector similarity with TAG/text filters in one query
* **One datastore** — if you already run Valkey for caching or sessions, reuse it for vectors

This cookbook uses the official high-performance [`valkey-glide`](https://github.com/valkey-io/valkey-glide) client and stores documents as JSON.

## Prerequisites

* Docker or Podman installed
* Python 3.10+
* An [OpenAI API key](https://platform.openai.com/account/api-keys)

## Step 1: Start Valkey with the Search Module

The simplest option is `valkey-bundle`, which includes the search module out of the box:

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should show "search" in the output
```

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

## Step 2: Install Dependencies

```bash
pip install valkey-glide openai numpy python-dotenv
```

Set your OpenAI API key. The sample loads it from a `.env` file via `python-dotenv`:

```bash
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

## Step 3: Connect to Valkey

`valkey-glide` provides an async client. Always wrap operations in `try/finally` so the client is closed even if a step raises:

```python
import asyncio
import os
from glide import GlideClient, GlideClientConfiguration, NodeAddress

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(os.environ.get("VALKEY_HOST", "localhost"),
                               int(os.environ.get("VALKEY_PORT", "6379")))],
        request_timeout=5000,  # 5s; the GLIDE default is 250ms — raise it off localhost
    )
    client = await GlideClient.create(config)
    try:
        print(await client.ping())  # b'PONG'
    finally:
        await client.close()

asyncio.run(main())
```

## Step 4: Create a Vector Index

Define a schema over your JSON documents. Here we index three TAG fields plus a `content_vector` field that will hold the OpenAI embedding. We use the FLAT algorithm (exact, brute-force search — ideal for fewer than ~1000 documents) with COSINE distance:

```python
from glide import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType, DistanceMetricType, FtCreateOptions, TagField,
    VectorAlgorithm, VectorField, VectorFieldAttributesFlat, VectorType,
)
from glide_shared.exceptions import RequestError

INDEX_NAME = "openai-getting-started"
PREFIX = "doc:"      # only keys starting with this prefix are indexed
EMBED_DIM = 1536     # output dimension of text-embedding-3-small

# `client` is the connected GlideClient from Step 3.
# Drop any stale index first so re-runs start clean. dropindex raises
# RequestError when the index is absent — a safe no-op on a first run.
# Catch only that narrow case so real errors still surface.
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
        algorithm=VectorAlgorithm.FLAT,
        attributes=VectorFieldAttributesFlat(
            dimensions=EMBED_DIM,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        ),
    ),
]
options = FtCreateOptions(data_type=DataType.JSON, prefixes=[PREFIX])
await ft.create(client, INDEX_NAME, schema, options)
```

## Step 5: Embed and Store Documents

Create the OpenAI client **once** and reuse it — never re-instantiate it per call. Embed each document's text and store the record as JSON:

```python
import json
import numpy as np
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
openai_client = OpenAI()  # reads OPENAI_API_KEY from the environment

def embed(texts):
    """Return one embedding vector per input string."""
    response = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in response.data]

documents = [
    {"id": "1", "title": "Valkey", "url": "https://valkey.io",
     "text": "Valkey is an open-source, high-performance key-value datastore."},
    {"id": "2", "title": "Vector Search", "url": "https://valkey.io/topics/search/",
     "text": "Valkey Search adds native vector similarity search and secondary indexing."},
]

vectors = embed([doc["text"] for doc in documents])
# Demo loop writes one key at a time. For large corpora, batch the writes with
# the client's Batch/pipeline API to avoid N network round trips.
from glide import glide_json
for doc, vector in zip(documents, vectors):
    record = {**doc, "content_vector": vector}
    await glide_json.set(client, f"{PREFIX}{doc['id']}", "$", json.dumps(record))
```

## Step 6: Run a Vector Search

Embed the query with the same model, pack it into the float32 bytes Valkey expects, and run a KNN search:

```python
from glide import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions, ReturnField,
)

# `embed` and `client` come from the steps above. `k` is the number of
# nearest neighbours to return.
query = "open source in-memory database"
query_blob = np.array(embed([query])[0], dtype=np.float32).tobytes()
k = 3

# '=>' separates the optional filter from the KNN clause. Never interpolate raw
# user input into this string; the query vector is a bound parameter ($query_vec).
knn_query = f"(*)=>[KNN {k} @content_vector $query_vec AS vector_score]"
options = FtSearchOptions(
    params={"query_vec": query_blob},
    return_fields=[ReturnField("title"), ReturnField("vector_score", alias="score")],
)
count, docs = await ft.search(client, INDEX_NAME, knn_query, options)

for key, fields in docs.items():
    # COSINE distance is in [0, 2]; similarity = 1 - distance.
    similarity = 1 - float(fields[b"score"])
    print(f"{key.decode()}: {fields[b'title'].decode()} (similarity: {similarity:.3f})")
```

The top hit will be the Valkey document — it's the closest in meaning to "open source in-memory database", even though it shares no exact words with the query.

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| Create index | `FT.CREATE ... ON JSON PREFIX doc: SCHEMA ...` | One-time index setup |
| Store document | `JSON.SET doc:{id} $ {...}` | Store a JSON record with its embedding |
| Search | `FT.SEARCH idx "(*)=>[KNN k @content_vector $query_vec]"` | Vector similarity search |
| Drop index | `FT.DROPINDEX idx` | Remove the index (keeps the documents) |

`valkey-glide` exposes these through typed helpers — `ft.create`, `glide_json.set`, `ft.search`, `ft.dropindex` — so you don't build raw command strings by hand.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'glide'` | Run `pip install valkey-glide` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:latest` (it includes the search module) |
| `AuthenticationError` from OpenAI | Set `OPENAI_API_KEY` in your `.env` file |
| Empty search results | Verify `EMBED_DIM` matches the embedding model's output dimension |

[Next: 02 Vector Search →](02-vector-search.md)
