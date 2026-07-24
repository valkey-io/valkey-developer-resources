# Vector Search & Persistence with LocalAI + Valkey

> Run KNN similarity search over your stored embeddings, understand LocalAI's cosine-similarity convention and index back-fill, and prove the data survives a restart.

**Intermediate** · Python · ~25 min

**Who is this for:** Developers who have the `valkey-store` backend running (see [01](01-getting-started.md)) and now want nearest-neighbour search plus durable storage for a real embedding workload.

[Getting Started](01-getting-started.md) covered Set and exact-match Get. The
reason to reach for a vector store, though, is **similarity search** — "find the
stored vectors closest to this query vector" — and the reason to reach for
*Valkey* specifically is **persistence**. This guide covers both, and the two
behaviours that surprise people: the similarity convention and asynchronous
index back-fill.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md): Valkey running,
  `valkey-store` backend built, LocalAI serving on `127.0.0.1:8080`.
- Python 3.10+ with `requests` (`pip install requests`).

## Step 1: Seed a store with several vectors

We'll reuse the thin client from [01](01-getting-started.md). Store four unit
vectors along the axes so the geometry is obvious:

```python
import requests

SESSION = requests.Session()
BASE_URL = "http://localhost:8080"
BACKEND = "valkey-store"
STORE = "vectors-demo"
TIMEOUT = 5.0  # seconds


def stores_set(keys, values):
    resp = SESSION.post(
        f"{BASE_URL}/stores/set",
        json={"backend": BACKEND, "store": STORE, "keys": keys, "values": values},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


# +X, +Y, +Z, and -X unit vectors.
keys = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]]
values = ["pos-x", "pos-y", "pos-z", "neg-x"]
stores_set(keys, values)
print("seeded", len(keys), "vectors")
```

> **Note:** The snippets in this guide share one `SESSION`, so we don't close it
> between steps — copy them into a single file and add `SESSION.close()` once at
> the very end (see the [cleanup note](#cleanup) below).

## Step 2: Find the nearest neighbours

`Find` takes a single query vector (`key`) and a `topk`, and returns the `topk`
closest stored vectors ordered **nearest-first**, with a parallel
`similarities` array.

```python
def stores_find(query, topk):
    resp = SESSION.post(
        f"{BASE_URL}/stores/find",
        json={"backend": BACKEND, "store": STORE, "key": query, "topk": topk},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


result = stores_find([1.0, 0.0, 0.0], topk=4)
# Assert, don't just print (Rule 27): a query returning 0 rows would mean the
# index never back-filled or the dimension is wrong — fail loudly.
assert len(result["keys"]) == 4, f"expected 4 results, got {result}"
for key, value, sim in zip(result["keys"], result["values"], result["similarities"]):
    print(f"{value:>6}  sim={sim:+.3f}  {key}")
```

Querying with `[1, 0, 0]` you'll see, nearest-first:

```text
 pos-x  sim=+1.000  [1.0, 0.0, 0.0]   # identical direction
 pos-y  sim=+0.000  [0.0, 1.0, 0.0]   # orthogonal
 pos-z  sim=+0.000  [0.0, 0.0, 1.0]   # orthogonal
 neg-x  sim=-1.000  [-1.0, 0.0, 0.0]  # opposite direction
```

> **Use a real query direction.** A meaningful cosine query needs a vector with
> an actual direction. Querying with a uniform vector like `[0.5, 0.5, 0.5]`
> against axis-aligned data is a valid call, but a constant/zero query carries no
> semantic direction and the ranking is meaningless — always query with an
> embedding produced the same way as your stored vectors.

## Step 3: Understand the similarity convention

For `COSINE` (the default), LocalAI reports similarity on the same scale as the
in-memory `local-store`:

| Similarity | Meaning |
|------------|---------|
| `+1.0` | identical direction |
| `0.0` | orthogonal (unrelated) |
| `-1.0` | opposite direction |

Valkey Search internally returns cosine *distance* (`0` = identical, `2` =
opposite). The backend converts it with **`similarity = 1 - distance`** so your
results match `local-store` exactly. For the alternative metrics:

| `distance_metric` | What `similarities` contains | Ordering |
|-------------------|------------------------------|----------|
| `COSINE` (default) | `1 - distance`, range `[-1, 1]` | higher = closer |
| `L2` | raw squared-L2 distance | **lower = closer** |
| `IP` | raw inner product | higher = closer |

Results are always returned nearest-first regardless of metric; the
`similarities` values just differ in scale and direction. Metric selection is a
per-store config option covered in [03](03-production.md).

## Step 4: Handle asynchronous index back-fill

Valkey Search updates its vector index **asynchronously** after a write. A
`Find` issued immediately after `Set` may not see the new vectors yet. `Get` and
`Delete` are synchronous and unaffected — this only touches `Find`.

Don't sleep a fixed amount; **poll `Find` with a bounded retry** until the
expected count appears:

```python
import time


def find_when_ready(query, topk, expect, attempts=20, delay=0.25):
    """Poll Find until at least `expect` results appear.

    attempts * delay caps the total wait (here 20 * 0.25s = 5s) so a genuinely
    empty or misconfigured store fails loudly instead of hanging forever.
    """
    for _ in range(attempts):  # bounded: never loop unboundedly (Rule 37)
        result = stores_find(query, topk)
        if len(result["keys"]) >= expect:
            return result
        time.sleep(delay)
    raise AssertionError(f"only {len(result['keys'])}/{expect} results after back-fill wait")


ready = find_when_ready([1.0, 0.0, 0.0], topk=4, expect=4)
print("index back-filled:", len(ready["keys"]), "results")
```

## Step 5: Prove persistence across a restart

This is the capability the in-memory `local-store` cannot offer. Stop LocalAI,
leave **Valkey running**, start LocalAI again, and the vectors are still there —
because they live in Valkey, not the backend process.

```bash
# 1. Stop the LocalAI server (Ctrl-C, or kill the process). Leave Valkey up.
# 2. Start LocalAI again exactly as in guide 01.
# 3. Get a vector you stored before the restart:
curl -sS -X POST http://localhost:8080/stores/get \
  -H "Content-Type: application/json" \
  -d '{"backend":"valkey-store","store":"vectors-demo","keys":[[1.0,0.0,0.0]]}'
# => {"keys":[[1.0,0.0,0.0]],"values":["pos-x"]}
```

On restart the backend issues a single `FT.INFO` for the store's index; a
successful reply means the persisted index (and its vector dimension) is
recovered, so `Find` works before this fresh process has issued its first `Set`.

> **Durability depends on Valkey's persistence settings.** "Survives a LocalAI
> restart" is guaranteed because the data is in Valkey. Surviving a *Valkey*
> restart depends on Valkey's own RDB/AOF configuration — see
> [Valkey persistence](https://valkey.io/topics/persistence/). The
> `valkey/valkey-bundle` image enables RDB snapshots by default.

## How It Works

Under the hood, the four operations map to Valkey commands like this:

| Operation | Valkey command(s) |
|-----------|-------------------|
| `Set` | `FT.CREATE` once (lazily, at first write), then one `HSET` per vector |
| `Get` | `HGET` per key (exact vector match) |
| `Delete` | `DEL` per key |
| `Find` | `FT.SEARCH <idx> "*=>[KNN <topk> @vec $q AS __score]" ... DIALECT 2` |

Each vector is a HASH with a `vec` field (raw little-endian float32 bytes,
indexed) and a `val` field (your opaque value). The key is a per-store
prefix + the hex of the vector bytes, so storing the same vector twice is an
idempotent upsert.

> **Note on the query string:** the KNN query is built only from compile-time
> constants and the integer `topk`; the query vector is passed as a bound
> parameter (`$q`), never string-interpolated. When you build `FT.SEARCH`
> queries yourself, never interpolate unsanitised user input — the `=>` token
> separates the filter from the KNN clause, so an injected `=>` could rewrite
> your query.

## Configuration Reference

`Find`-related request fields:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `key` | ✓ | — | Query vector; must match the store's dimension. |
| `topk` | ✓ | — | Number of nearest neighbours to return (≥ 1). |
| `store` | ✓ | — | Store namespace. |
| `backend` | — | `local-store` | `valkey-store` to route to Valkey. |

## Cleanup

If you assembled the snippets above into one script, close the shared HTTP
session once, after the last request:

```python
SESSION.close()
```

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Configuration →](03-production.md)
