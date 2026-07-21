# Getting Started with OpenAI + Valkey

> Create a JSON vector index, store documents, and run a KNN search with a credential-free local sample or OpenAI embeddings.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building a first Valkey-backed semantic search flow and learning where embeddings meet vector indexing.

## What is OpenAI + Valkey?

[OpenAI embeddings](https://platform.openai.com/docs/guides/embeddings) turn
text into dense vectors that capture meaning. [Valkey
Search](https://valkey.io/topics/search/) is an open-source Valkey module that
adds native vector similarity search and secondary indexing to Valkey.

Using Valkey as your vector database for OpenAI embeddings gives you:

* **Vector search** — compare embedding vectors stored in Valkey JSON documents
* **Exact or approximate search** — FLAT (brute-force) for exact recall, HNSW for speed at scale
* **Hybrid queries** — combine vector similarity with TAG/text filters in one query
* **One datastore** — if you already run Valkey for caching or sessions, reuse it for vectors

This cookbook uses the official high-performance [`valkey-glide`](https://github.com/valkey-io/valkey-glide) client and stores documents as JSON.

## Prerequisites

* Docker or Podman installed
* Python 3.10+
* No credentials for the default sample path
* An OpenAI API key only for the optional provider path

## Step 1: Start Valkey with the Search Module

The simplest option is `valkey-bundle`, which includes the search module out of the box:

```bash
# Docker
docker run -d --name valkey-openai -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0

# Podman
podman run -d --name valkey-openai -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

The remaining shell commands use Docker. Replace `docker` with `podman` if
you chose Podman.

```bash
# Ensures Valkey is running
attempts=0
until [ "$(docker exec valkey-openai valkey-cli ping 2>/dev/null)" = "PONG" ]; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
        echo "Valkey did not become ready after 30 seconds" >&2
        exit 1
    fi
    sleep 1
done
```

Verify the search module is loaded:

```bash
docker exec valkey-openai valkey-cli MODULE LIST
# Should show "search" in the output
```

> **Security:** These local examples use no authentication or TLS. Bind local services to localhost only. For any non-localhost deployment, enable authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 2: Install Dependencies

```bash
cd sample
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The runnable sample uses deterministic local embeddings by default. To use OpenAI, copy the example environment file and set `OPENAI_API_KEY`:

```bash
cp sample/.env.example sample/.env
```

Run the default sample and its tests:

```bash
cd sample
.venv/bin/python getting_started.py
.venv/bin/python -m pytest -q
```

The code blocks below are API fragments that build on the connected client from
the preceding step. The complete, failure-safe flow is in
[`sample/getting_started.py`](sample/getting_started.py). The sample reuses and
closes its optional OpenAI client in the run's cleanup path.

## Step 3: Connect to Valkey

`valkey-glide` provides an async client. Always wrap operations in `try/finally` so the client is closed even if a step raises:

```python
import asyncio
import os
from glide import (
    AdvancedGlideClientConfiguration,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

async def main():
    config = GlideClientConfiguration(
        addresses=[NodeAddress(os.environ.get("VALKEY_HOST", "localhost"),
                               int(os.environ.get("VALKEY_PORT", "6379")))],
        request_timeout=5000,  # 5s; the GLIDE default is 250ms — raise it off localhost
        advanced_config=AdvancedGlideClientConfiguration(
            connection_timeout=5000,
        ),
    )
    client = await GlideClient.create(config)
    try:
        print(await client.ping())  # b'PONG'
    finally:
        await client.close()

asyncio.run(main())
```

## Step 4: Create a Vector Index

Define a schema over your JSON documents. Here we index three TAG fields plus a
`content_vector` field that will hold the OpenAI embedding. We use the FLAT
algorithm (exact, brute-force search — ideal for fewer than ~1000 documents)
with COSINE distance:

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
# Drop any stale index first so re-runs start clean. Valkey 9.1.0 reports a
# missing index with "not found in database"; preserve every other error.
try:
    await ft.dropindex(client, INDEX_NAME)
except RequestError as exc:
    if "not found in database" not in str(exc).lower():
        raise

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
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.environ.get("OPENAI_EMBEDDING_DIM", "1536"))
openai_client = OpenAI(timeout=10.0, max_retries=1)  # reads OPENAI_API_KEY

def embed(texts):
    """Return one embedding vector per input string."""
    response = openai_client.embeddings.create(
        input=texts,
        model=EMBED_MODEL,
        dimensions=EMBED_DIM,
    )
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
    return_fields=[ReturnField("title"), ReturnField("vector_score")],
    dialect=2,  # valkey-search supports only DIALECT 2 for vector queries
)
count, docs = await ft.search(client, INDEX_NAME, knn_query, options)

for key, fields in docs.items():
    # COSINE distance is in [0, 2]; similarity = 1 - distance.
    similarity = 1 - float(fields[b"vector_score"])
    print(f"{key.decode()}: {fields[b'title'].decode()} (similarity: {similarity:.3f})")
```

The top hit will be the Valkey document — it's the closest in meaning to "open source in-memory database", even though it shares no exact words with the query.

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
| --- | --- | --- |
| Create index | `FT.CREATE ... ON JSON PREFIX doc: SCHEMA ...` | One-time index setup |
| Store document | `JSON.SET doc:{id} $ {...}` | Store a JSON record with its embedding |
| Search | `FT.SEARCH idx "(*)=>[KNN k @content_vector $query_vec]"` | Vector similarity search |
| Drop index | `FT.DROPINDEX idx` | Remove the index (keeps the documents) |

`valkey-glide` exposes these through typed helpers — `ft.create`, `glide_json.set`, `ft.search`, `ft.dropindex` — so you don't build raw command strings by hand.

## Troubleshooting

| Issue | Solution |
| --- | --- |
| `ModuleNotFoundError: No module named 'glide'` | Run `pip install valkey-glide` |
| `Connection refused on port 6379` | Ensure Valkey is running: `docker ps` |
| `Unknown command 'FT.CREATE'` | Use `valkey/valkey-bundle:9.1.0` (it includes the search module) |
| `AuthenticationError` from OpenAI | Set `OPENAI_API_KEY` in your `.env` file |
| Empty search results | Verify `OPENAI_EMBEDDING_DIM` matches the embedding model's output dimension |

## Configuration Reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | No | `6379` | Valkey server port |
| `OPENAI_API_KEY` | No | unset | Enables the OpenAI embedding path when set |
| `EMBED_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `OPENAI_EMBEDDING_DIM` | No | `1536` | Dimension requested from OpenAI and used by the JSON vector index |
| `EMBED_DIM` | Internal | `16` local, `1536` OpenAI | Vector dimension selected from the active embedding configuration |

## Teardown

The sample drops its index and deletes its `doc:` keys in a `finally` block. Stop the local service after the run:

```bash
docker rm -f valkey-openai
```

Replace `docker` with `podman` when using Podman.

---

[Next: 02 Vector Search →](02-vector-search.md)
