# Vector Search with OpenAI + Valkey

> Add HNSW indexing and a safe TAG pre-filter to a Valkey vector search.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers who need scoped vector retrieval and want to understand the tradeoff between exact FLAT search and approximate HNSW search.

## What You'll Build

The [getting started](01-getting-started.md) cookbook ran a basic KNN search over a FLAT index. This cookbook goes deeper:

* **Hybrid search** — combine a TAG pre-filter with KNN vector search in a single query
* **HNSW indexing** — approximate nearest-neighbour search for larger datasets
* **Choosing an algorithm** — when to use FLAT vs HNSW

It assumes you already have Valkey running with the search module (see [01 - Getting Started](01-getting-started.md)). The sample uses deterministic local vectors unless `OPENAI_API_KEY` is set.

> **Security:** These local examples use no authentication or TLS. Bind local services to localhost only. For any non-localhost deployment, enable authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 1: Create an HNSW Index

FLAT search compares the query against every vector — exact, but linear in the
number of documents. HNSW (Hierarchical Navigable Small World) builds a
navigable graph that finds approximate nearest neighbours much faster.

| Algorithm | Recall | Speed | Best for |
| --- | --- | --- | --- |
| **FLAT** | Exact | Linear scan | Smaller collections |
| **HNSW** | Approximate | Lower search work for larger collections | Larger collections |

> The handful of demo documents below would be better served by FLAT in
> production — we use HNSW here only to demonstrate the API and its tuning
> parameters. Choose the algorithm based on your real corpus size.

Define the schema with `VectorFieldAttributesHnsw`. We add a `genre` TAG so we can filter on it later:

```python
from glide import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DataType, DistanceMetricType, FtCreateOptions, TagField,
    VectorAlgorithm, VectorField, VectorFieldAttributesHnsw, VectorType,
)
from glide_shared.exceptions import RequestError

INDEX_NAME = "openai-vector-search"
PREFIX = "article:"
EMBED_DIM = 1536  # text-embedding-3-small output dimension

# `client` is the connected GlideClient. Drop any stale index first so re-runs
# start clean. Valkey 9.1.0 reports a missing index with "not found in
# database"; preserve every other error.
try:
    await ft.dropindex(client, INDEX_NAME)
except RequestError as exc:
    if "not found in database" not in str(exc).lower():
        raise

schema = [
    TagField("$.genre", alias="genre"),
    TagField("$.title", alias="title"),
    TagField("$.text", alias="text"),
    VectorField(
        name="$.content_vector",
        alias="content_vector",
        algorithm=VectorAlgorithm.HNSW,
        attributes=VectorFieldAttributesHnsw(
            dimensions=EMBED_DIM,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
            number_of_edges=16,                   # M: graph connectivity, typical 16–64
            vectors_examined_on_construction=200,  # ef_construction: higher = better recall, slower build
        ),
    ),
]
options = FtCreateOptions(data_type=DataType.JSON, prefixes=[PREFIX])
await ft.create(client, INDEX_NAME, schema, options)
```

The two HNSW tuning values are optional (Valkey applies sensible defaults).
`number_of_edges` controls how connected the graph is, and
`vectors_examined_on_construction` trades build time for recall.

## Step 2: Embed and Store Documents

Same pattern as the getting-started cookbook — embed each document's text and store it as JSON. The OpenAI client is created **once** and reused:

```python
import json
import numpy as np
import os
from dotenv import load_dotenv
from openai import OpenAI
from glide import glide_json

load_dotenv()
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.environ.get("OPENAI_EMBEDDING_DIM", "1536"))
openai_client = OpenAI(timeout=10.0, max_retries=1)

def embed(texts):
    response = openai_client.embeddings.create(
        input=texts,
        model=EMBED_MODEL,
        dimensions=EMBED_DIM,
    )
    return [item.embedding for item in response.data]

documents = [
    {"id": "1", "genre": "music", "title": "Jazz",
     "text": "Jazz is a music genre that originated in New Orleans."},
    {"id": "2", "genre": "music", "title": "Mozart",
     "text": "Wolfgang Amadeus Mozart was a prolific classical composer."},
    {"id": "3", "genre": "tech", "title": "Valkey",
     "text": "Valkey is a high-performance open-source key-value datastore."},
]

vectors = embed([doc["text"] for doc in documents])
# Demo loop; batch with the client's pipeline API for large corpora.
for doc, vector in zip(documents, vectors):
    record = {**doc, "content_vector": vector}
    await glide_json.set(client, f"{PREFIX}{doc['id']}", "$", json.dumps(record))
```

## Step 3: Hybrid Search (Filter + Vector)

A hybrid query narrows the candidate set with a TAG filter, then ranks the
survivors by vector similarity. Build the filter carefully — an empty TAG brace
(`@genre:{}`) silently matches **zero** documents, so guard the empty case:

```python
from glide import ft
import re
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions, ReturnField,
)

# `embed` and `client` come from the steps above.
def validate_genre(genre):
    if genre and not re.fullmatch(r"[A-Za-z0-9_-]+", genre):
        raise ValueError("genre must contain only letters, digits, '_' or '-'")
    return genre

def validate_k(k):
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 1000:
        raise ValueError("k must be an integer between 1 and 1000")
    return k

async def search(query, k=3, genre=""):
    genre = validate_genre(genre)
    k = validate_k(k)
    query_blob = np.array(embed([query])[0], dtype=np.float32).tobytes()

    # Guard the variable-built TAG filter: fall back to '*' (match everything)
    # when no genre is supplied. Never interpolate raw user input — '=>'
    # separates the filter from the KNN clause, and the vector is a bound
    # parameter ($query_vec), not concatenated into the string.
    filter_expr = f"@genre:{{{genre}}}" if genre else "*"
    knn_query = f"({filter_expr})=>[KNN {k} @content_vector $query_vec AS vector_score]"

    options = FtSearchOptions(
        params={"query_vec": query_blob},
        return_fields=[
            ReturnField("title"),
            ReturnField("genre"),
            ReturnField("vector_score"),
        ],
        dialect=2,  # valkey-search supports only DIALECT 2 for vector queries
    )
    return await ft.search(client, INDEX_NAME, knn_query, options)

# Only "tech" documents are ranked, then ordered by similarity to the query.
count, docs = await search("in-memory database", k=3, genre="tech")
for key, fields in docs.items():
    similarity = 1 - float(fields[b"vector_score"])  # COSINE: similarity = 1 - distance
    print(f"{key.decode()}: {fields[b'title'].decode()} "
          f"[{fields[b'genre'].decode()}] (similarity: {similarity:.3f})")
```

Passing `genre=""` runs an unfiltered search across the whole index; passing `genre="tech"` restricts results to documents tagged `tech` before ranking by vector similarity.

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
| --- | --- | --- |
| Create HNSW index | `FT.CREATE ... SCHEMA ... VECTOR HNSW ...` | Build a graph index for approximate search |
| Hybrid search | `FT.SEARCH idx "(@genre:{tech})=>[KNN k @content_vector $query_vec]"` | Filter by TAG, then rank by vector similarity |
| Unfiltered search | `FT.SEARCH idx "(*)=>[KNN k @content_vector $query_vec]"` | Rank the whole index by vector similarity |

The `(filter)=>[KNN ...]` syntax combines the filter and vector query. The Search module ranks the documents that satisfy the filter.

## Troubleshooting

| Issue | Solution |
| --- | --- |
| Hybrid query returns nothing | Check the TAG value exists; an empty brace `@genre:{}` matches zero documents |
| `field not exists` on search | Query an alias/field that's actually in the index schema |
| HNSW results differ slightly from FLAT | Expected — HNSW is approximate; raise `vectors_examined_on_construction` for higher recall |
| Slow index build | Lower `vectors_examined_on_construction` or `number_of_edges` |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | No | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | No | `6379` | Valkey server port |
| `OPENAI_API_KEY` | No | unset | Enables OpenAI embeddings when set |
| `EMBED_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `OPENAI_EMBEDDING_DIM` | No | `1536` | Dimension requested from OpenAI and used by the JSON vector index |
| `genre` | No | empty | Validated TAG filter; empty searches all indexed documents |
| `k` | No | `3` | Maximum number of nearest neighbors returned; must be 1-1000 |

## Teardown

The runnable sample removes its HNSW index and `article:` keys in a `finally`
block. Cached or indexed data should have an explicit retention or deletion
policy; this sample deletes all demonstration data after each run.

---

[← Back: 01 Getting Started](01-getting-started.md)
