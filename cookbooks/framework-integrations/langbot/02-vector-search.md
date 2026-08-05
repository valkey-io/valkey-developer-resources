# Vector Search for the Knowledge Base

> Create a Valkey Search HNSW index, store embeddings as HASH keys, and run KNN similarity queries with valkey-glide's typed `ft` API.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers building a RAG knowledge base who need vector similarity search backed by Valkey, and want to
understand the exact commands LangBot's `ValkeySearchVectorDatabase` issues under the hood.

## What You'll Build

LangBot's knowledge base (RAG) stores document chunks as embeddings and retrieves the most relevant ones at query time. The
`valkey_search` backend implements that store on top of the **Valkey Search** module, using `valkey-glide`'s typed `ft` (search) API.

In this cookbook you'll create a vector index, store embeddings as Valkey HASH keys, and run K-nearest-neighbor (KNN) similarity queries — the same operations LangBot's `ValkeySearchVectorDatabase` performs.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Valkey **bundle** running, `valkey-glide` installed)
- Python 3.10+
- `valkey-glide==2.5.0` (the typed `ft` builders used below are available from 2.4.1)

## How Storage Is Modeled

Each chunk becomes one Valkey HASH key under a per-collection prefix:

```text
kb:{collection}:{id}
```

with these fields:

| Field | Type | Purpose |
|-------|------|---------|
| `vector` | FLOAT32 blob | The embedding, packed little-endian |
| `document` | TEXT | Raw chunk text (indexed for full-text/hybrid in cookbook 03) |
| `file_id` | TAG | Source file id, promoted to a filterable index field |
| `metadata_json` | JSON string | Full metadata dict, preserved verbatim |

One `FT.CREATE` index per collection points at the `kb:{collection}:` prefix and indexes those fields.

## Step 1: Pack Embeddings as Float32

Valkey Search stores and queries vectors as **little-endian FLOAT32** blobs. Pack a Python float list with `struct`:

```python
import struct


def pack_vector(vec: list[float]) -> bytes:
    # '<' = little-endian, 'f' = 32-bit float, one per element.
    # Valkey Search requires this exact byte layout for vector fields.
    return struct.pack(f"<{len(vec)}f", *[float(x) for x in vec])
```

The same packing is used both when storing a document and when passing the query vector — a mismatch (wrong endianness or float64) yields zero or garbage results, not an error.

## Step 2: Create the Index

The index declares the vector field's dimension, algorithm, and distance metric. Pick the metric that matches how your embeddings were trained (`COSINE` is the common default for normalized text embeddings).

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

```python
import asyncio
import os

from glide import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    RequestError,
    ft,
    DataType,
    DistanceMetricType,
    FtCreateOptions,
    TagField,
    TextField,
    VectorAlgorithm,
    VectorField,
    VectorFieldAttributesHnsw,
    VectorType,
)

COLLECTION = "kb_demo"
DIM = 64  # embedding dimension; must match your embedding model's output size


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


async def ensure_index(client: GlideClient, collection: str, dim: int) -> None:
    index = f"idx:{collection}"
    # FT.INFO on a single index is O(1) and raises RequestError when the index
    # is absent. (FT._LIST returns every index name on the server — O(n) — and
    # leaves a TOCTOU gap between the check and the create below.)
    try:
        await ft.info(client, index)
        return  # already exists
    except RequestError:
        pass  # doesn't exist — create it below

    vector_attrs = VectorFieldAttributesHnsw(
        dimensions=dim,
        distance_metric=DistanceMetricType.COSINE,  # COSINE | L2 | IP
        type=VectorType.FLOAT32,
    )
    schema = [
        VectorField(name="vector", algorithm=VectorAlgorithm.HNSW, attributes=vector_attrs),
        TagField(name="file_id"),
        TextField(name="document"),
    ]
    options = FtCreateOptions(data_type=DataType.HASH, prefixes=[f"kb:{collection}:"])
    await ft.create(client, index, schema, options)
```

### HNSW vs FLAT

| Algorithm | How it searches | Use when |
|-----------|-----------------|----------|
| `FLAT` | Exact brute-force scan | Small collections (roughly **< 10,000** vectors) where perfect recall matters |
| `HNSW` | Approximate graph navigation | Larger collections where low-latency retrieval matters more than exact recall |

Swap `VectorFieldAttributesHnsw` for `VectorFieldAttributesFlat` (and `VectorAlgorithm.FLAT`) to build an exact index. LangBot picks this from the `index_algorithm` config value.

## Step 3: Add Embeddings

Store each chunk as a HASH. The `file_id` field is what makes deletions and filters by source document possible (cookbook 03).

```python
import json


async def add_documents(client: GlideClient, collection: str,
                        ids: list[str], vectors: list[list[float]],
                        documents: list[str], metadatas: list[dict]) -> None:
    await ensure_index(client, collection, len(vectors[0]))
    prefix = f"kb:{collection}:"
    # One HSET per chunk. Fine for a handful of docs; for hundreds of chunks,
    # batch the writes with the GLIDE Batch/Pipeline API to avoid N round trips.
    for i, _id in enumerate(ids):
        meta = metadatas[i]
        mapping = {
            "vector": pack_vector(vectors[i]),          # pack_vector from Step 1
            "document": documents[i],
            "metadata_json": json.dumps(meta, ensure_ascii=False),
        }
        if meta.get("file_id") is not None:
            # Cookbook 03 introduces filtering by file_id and shows why this
            # value must go through encode_file_id() at write time too, not
            # only at query time — the runnable sample already does this.
            mapping["file_id"] = str(meta["file_id"])
        await client.hset(prefix + str(_id), mapping)
```

> **Indexing is asynchronous.** The search module indexes new keys in the background, so a query issued immediately after `hset` may
> return fewer results than expected. Poll/retry briefly rather than calling `time.sleep` blindly — the runnable
> [sample](sample/) includes a `poll_until` helper.

## Step 4: Run a KNN Query

A vector query has two parts joined by `=>`: a pre-filter (use `*` to match all) and the KNN clause. The query vector is passed as a bound parameter (`$BLOB`), not interpolated into the string.

```python
from glide import FtSearchLimit, FtSearchOptions, ReturnField


async def vector_search(client: GlideClient, collection: str,
                        query_vec: list[float], k: int = 5) -> list[dict]:
    index = f"idx:{collection}"
    # '*' = match all candidates; KNN ranks them. 'AS __vec_score' aliases the
    # distance so we can return it. Lower distance = more similar (COSINE/L2).
    query = f"*=>[KNN {k} @vector $BLOB AS __vec_score]"
    options = FtSearchOptions(
        params={"BLOB": pack_vector(query_vec)},  # bound param — never string-interpolated
        return_fields=[
            ReturnField(field_identifier="__vec_score"),  # the KNN distance, named by AS
            ReturnField(field_identifier="document"),
            ReturnField(field_identifier="metadata_json"),
        ],
        limit=FtSearchLimit(0, k),  # offset 0, return up to k rows
        dialect=2,                  # query dialect 2 is required for KNN params
    )
    reply = await ft.search(client, index, query, options)

    # ft.search returns [total, {key: {field: value}, ...}].
    results: list[dict] = []
    docs = reply[1] if reply and len(reply) >= 2 and isinstance(reply[1], dict) else {}
    prefix = f"kb:{collection}:"
    for key, fields in docs.items():
        decoded = {
            (k.decode() if isinstance(k, (bytes, bytearray)) else k):
            (v.decode() if isinstance(v, (bytes, bytearray)) else v)
            for k, v in fields.items()
        }
        key_str = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
        results.append({
            "id": key_str[len(prefix):] if key_str.startswith(prefix) else key_str,
            # The distance comes back under its AS-name, not a return-field alias.
            "distance": float(decoded.get("__vec_score", 0.0)),
            "document": decoded.get("document"),
            "metadata": json.loads(decoded["metadata_json"]) if "metadata_json" in decoded else {},
        })
    return results
```

Putting it together with proper cleanup:

```python
async def main() -> None:
    client = await create_client()
    try:
        # ... call add_documents(...) then vector_search(...) ...
        # Embed the query with the SAME model used for the documents. `embed`
        # here stands in for your embedding model (see the runnable sample for a
        # tiny demo implementation). Avoid a uniform vector like [0.1]*DIM: it's
        # a scalar multiple of [1.0]*DIM, so under COSINE it has no semantic
        # direction and can't rank results meaningfully.
        query_vec = embed("similar vector embeddings")  # -> list[float] of length DIM
        hits = await vector_search(client, COLLECTION, query_vec=query_vec, k=3)
        for h in hits:
            print(f"{h['id']}: distance={h['distance']:.4f} :: {h['document']!r}")
    finally:
        await client.close()  # always release the connection


if __name__ == "__main__":
    asyncio.run(main())
```

## How It Works Under the Hood

| Operation | Valkey command | Notes |
|-----------|----------------|-------|
| Create index | `FT.CREATE` | One index per collection, scoped to the `kb:{collection}:` prefix |
| Store chunk | `HSET` | Vector blob + document + file_id + metadata_json |
| KNN query | `FT.SEARCH ... =>[KNN k @vector $BLOB]` | Bound `$BLOB` param; `dialect=2` required |
| List indexes | `FT.INFO` (via `ft.info`) | O(1) existence check before create; raises if the index is absent |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `unknown command 'FT.CREATE'` | Use the `valkey/valkey-bundle:9.1.0` image (search module) |
| Empty results right after insert | Indexing is async — poll/retry briefly before asserting results |
| All distances are 0 or results look random | Vector packing mismatch — ensure both stored and query vectors are little-endian FLOAT32 of the same dimension |
| `dimensions mismatch` error | The query/stored vector length must equal the index `dimensions` |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Hybrid Search & Filtering →](03-hybrid-and-filtering.md)
