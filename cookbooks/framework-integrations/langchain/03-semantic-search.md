# Semantic Search with LangChain + Valkey

> Store documents in Valkey and retrieve related values with `ValkeyStore`.

**Intermediate** · Python · ~20 min

**Who is this for:** Python developers adding namespace-scoped similarity
search to a LangChain application.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start from the sample directory.
- Python 3.10 or newer with the pinned requirements installed
- A local Valkey Bundle running on `127.0.0.1:6379`

## Why Semantic Search?

"How do I reset my password?" and "I forgot my password, help!" mean the same thing. Exact-match caching misses this. `ValkeyStore` uses vector similarity to match by meaning:

- **HNSW index** - approximate nearest-neighbor search
- **Low-latency retrieval** - search runs in Valkey
- **Real-time updates** - new vectors are searchable immediately, no rebuild needed

The default example uses the deterministic local embedding class in
[`sample/main.py`](sample/main.py). A compatible provider embedding can be
substituted when an application needs one.

## Step 1: Configure ValkeyStore

Run this example from the sample directory:

```python
from langgraph_checkpoint_aws import ValkeyStore
from main import DeterministicEmbeddings
from valkey import Valkey

client = Valkey.from_url(
    "valkey://127.0.0.1:6379",
    decode_responses=False,
)
embeddings = DeterministicEmbeddings()

# ValkeyStore with HNSW vector index
store = ValkeyStore(
    client=client,
    index={
        "collection_name": "semantic_cache",
        "dims": embeddings.dimensions,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "distance_metric": "COSINE",
    },
    ttl={"default_ttl": 60.0},
)
store.setup()  # Creates the FT index
```

## Step 2: Store Documents

```python
# Store a document - embedding is generated automatically
store.put(
    ("help-desk", "passwords"),  # namespace
    "q1",                          # key
    {
        "text": "How do I reset my password?",
        "answer": "Go to the password reset page.",
    },
)

store.put(
    ("help-desk", "vpn"),
    "q2",
    {
        "text": "How do I connect to the VPN?",
        "answer": "Download the VPN client from the IT portal.",
    },
)
```

## Step 3: Search by Meaning

```python
# Search with a paraphrased query
results = store.search(
    ("help-desk",),  # namespace prefix
    query="I forgot my password, help!",
    limit=3,
)

for result in results:
    print(f"Score: {result.score:.3f} - {result.value['text']}")
```

Search results are scoped by the namespace prefix. Use a separate top-level
namespace for each tenant or application boundary.

**Valkey Commands Fired:**

```text
# Index creation (once)
FT.CREATE semantic_cache_idx ON JSON PREFIX 1 "store:semantic_cache:"
  SCHEMA $.text AS text TAG
         $.embedding AS embedding VECTOR HNSW 6
           TYPE FLOAT32 DIM 4 DISTANCE_METRIC COSINE

# Store document
JSON.SET store:semantic_cache:help-desk:passwords:q1 $ '{...}'
EXPIRE store:semantic_cache:help-desk:passwords:q1 3600

# Vector search
FT.SEARCH semantic_cache_idx
  "(*)==>[KNN 3 @embedding $vec AS score]"
  PARAMS 2 vec <binary_vector>
  LIMIT 0 3
```

## Step 4: HNSW Tuning

Tune the index for your speed/accuracy tradeoff:

Parameter| Default| Higher =| Lower =
---|---|---|---
`hnsw_m`| 16| Better recall, more memory| Faster, less memory
`hnsw_ef_construction`| 200| Better index quality| Faster build
`hnsw_ef_runtime`| 10| Better search accuracy| Faster queries

```python
# High-accuracy configuration
store = ValkeyStore(
    client=client,
    index={
        "collection_name": "precise_search",
        "dims": embeddings.dimensions,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "hnsw_m": 32,
        "hnsw_ef_construction": 400,
        "hnsw_ef_runtime": 50,
    },
)
store.setup()
```

## Configuration Reference

Option | Default | Description
--- | --- | ---
`collection_name` | `semantic_cache` | Name of the Valkey Search collection.
`dims` | `4` for the local sample | Embedding vector dimensions.
`index_type` | `hnsw` | Vector index type.
`distance_metric` | `COSINE` | Similarity metric used for search.
`default_ttl` | `60.0` | Default document retention setting.

## Teardown

Close the client used by the direct examples:

```python
client.close()
```

## Next Steps

Now you have all three components: `ValkeySaver` (checkpoints), `ValkeyCache` (exact caching), and `ValkeyStore` (semantic search). Time to wire them all together.

---

[Previous: 02 LLM Caching ←](02-llm-caching.md) |
[Next: 04 Full Agent - All Three Components →](04-full-agent.md)
