# Vector Search with OpenAI + Valkey

**Intermediate** · Python · ~20 min

## What You'll Build

The [getting started](01-getting-started.md) cookbook ran a basic KNN search over a FLAT index. This cookbook goes deeper:

* **Hybrid search** — combine a TAG pre-filter with KNN vector search in a single query
* **HNSW indexing** — fast approximate nearest-neighbour search for larger datasets
* **Choosing an algorithm** — when to use FLAT vs HNSW

It assumes you already have Valkey running with the search module and your `OPENAI_API_KEY` set (see [01 - Getting Started](01-getting-started.md)).

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

## Step 1: Create an HNSW Index

FLAT search compares the query against every vector — exact, but linear in the number of documents. HNSW (Hierarchical Navigable Small World) builds a navigable graph that finds approximate nearest neighbours much faster.

| Algorithm | Recall | Speed | Best for |
|-----------|--------|-------|----------|
| **FLAT** | Exact (100%) | Linear scan | < 1000 documents |
| **HNSW** | Approximate (99%+) | Sub-linear | > 1000 documents |

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
# start clean; dropindex raises RequestError when absent (safe no-op on a clean
# first run), so catch only that narrow case.
try:
    await ft.dropindex(client, INDEX_NAME)
except RequestError:
    pass

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

The two HNSW tuning values are optional (Valkey applies sensible defaults). `number_of_edges` controls how connected the graph is, and `vectors_examined_on_construction` trades build time for recall.

## Step 2: Embed and Store Documents

Same pattern as the getting-started cookbook — embed each document's text and store it as JSON. The OpenAI client is created **once** and reused:

```python
import json
import numpy as np
from openai import OpenAI
from glide import glide_json

EMBED_MODEL = "text-embedding-3-small"
openai_client = OpenAI()

def embed(texts):
    response = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
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

A hybrid query narrows the candidate set with a TAG filter, then ranks the survivors by vector similarity. Build the filter carefully — an empty TAG brace (`@genre:{}`) silently matches **zero** documents, so guard the empty case:

```python
from glide import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions, ReturnField,
)

# `embed` and `client` come from the steps above.
def search(query, k=3, genre=""):
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
            ReturnField("vector_score", alias="score"),
        ],
    )
    return ft.search(client, INDEX_NAME, knn_query, options)  # await this call

# Only "tech" documents are ranked, then ordered by similarity to the query.
count, docs = await search("in-memory database", k=3, genre="tech")
for key, fields in docs.items():
    similarity = 1 - float(fields[b"score"])  # COSINE: similarity = 1 - distance
    print(f"{key.decode()}: {fields[b'title'].decode()} "
          f"[{fields[b'genre'].decode()}] (similarity: {similarity:.3f})")
```

Passing `genre=""` runs an unfiltered search across the whole index; passing `genre="tech"` restricts results to documents tagged `tech` before ranking by vector similarity.

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| Create HNSW index | `FT.CREATE ... SCHEMA ... VECTOR HNSW ...` | Build a graph index for approximate search |
| Hybrid search | `FT.SEARCH idx "(@genre:{tech})=>[KNN k @content_vector $query_vec]"` | Filter by TAG, then rank by vector similarity |
| Unfiltered search | `FT.SEARCH idx "(*)=>[KNN k @content_vector $query_vec]"` | Rank the whole index by vector similarity |

The `(filter)=>[KNN ...]` syntax is what makes hybrid search a single round trip: the filter runs first to shrink the candidate set, then KNN ranks only the survivors.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Hybrid query returns nothing | Check the TAG value exists; an empty brace `@genre:{}` matches zero documents |
| `field not exists` on search | Query an alias/field that's actually in the index schema |
| HNSW results differ slightly from FLAT | Expected — HNSW is approximate; raise `vectors_examined_on_construction` for higher recall |
| Slow index build | Lower `vectors_examined_on_construction` or `number_of_edges` |

[← Back: 01 Getting Started](01-getting-started.md)
