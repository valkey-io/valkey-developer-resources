# Hybrid Search & Metadata Filtering

**Advanced** · Python · ~20 min

## What You'll Build

Cookbook 03 covered pure vector search. Here you'll add the other two search modes LangBot's `valkey_search` backend supports — **full-text** and **hybrid** — plus metadata filtering by `file_id`, source-document deletion, and the safety rules that keep all of it injection-proof.

You'll also learn the one important caveat: this backend does **not** honor `vector_weight`.

## Prerequisites

- Completed [03 - Vector Search](03-vector-search.md) (index created, embeddings stored)
- Python 3.10+
- `valkey-glide>=2.4.1,<3.0.0`

## Search Modes at a Glance

| Mode | What it does |
|------|--------------|
| `vector` | Pure KNN over the embedding field (cookbook 03) |
| `full_text` | Term match over the indexed `document` TEXT field |
| `hybrid` | A filter/text clause **pre-selects** candidates, then KNN ranks them |

## Step 1: Full-Text Search

Each whitespace-delimited word becomes a field-scoped term against the `document` field, and the terms are AND-ed. Special characters in each term are escaped so user input can't alter the query structure.

```python
def escape_text(term: str) -> str:
    # Neutralize FT full-text operators so a search word is treated as literal text.
    out = []
    for ch in str(term):
        if ch in '@!{}[]()|-"~*:\\':
            out.append("\\")
        out.append(ch)
    return "".join(out)


def build_text_clause(text: str) -> str:
    words = [w for w in str(text).split() if w]
    # AND the per-word terms, each scoped to the @document field.
    return " ".join(f"@document:{escape_text(w)}" for w in words)
```

```python
from glide import FtSearchLimit, FtSearchOptions, ReturnField, ft


async def full_text_search(client, collection: str, query_text: str, k: int = 5):
    index = f"idx:{collection}"
    clause = build_text_clause(query_text)
    if not clause:
        return []  # no searchable words -> no results
    options = FtSearchOptions(
        return_fields=[ReturnField(field_identifier="document"),
                       ReturnField(field_identifier="metadata_json")],
        limit=FtSearchLimit(0, k),  # offset 0, up to k rows
        dialect=2,
    )
    reply = await ft.search(client, index, clause, options)
    return reply  # parse reply[1] dict as in cookbook 03
```

## Step 2: Filter by `file_id` (TAG)

Only **indexed** fields are filterable. The backend promotes `file_id` to a TAG field; all other metadata round-trips inside `metadata_json` but is not filterable (the same pragmatism Milvus and pgvector use).

The canonical filter operators map to FT TAG syntax:

| Operator | FT fragment | Meaning |
|----------|-------------|---------|
| `$eq` | `@file_id:{value}` | equals |
| `$ne` | `-@file_id:{value}` | not equals |
| `$in` | `@file_id:{a\|b\|c}` | any of |
| `$nin` | `-@file_id:{a\|b\|c}` | none of |

TAG values must be escaped — and a few characters (`{`, `}`, `*`) can't be used in a TAG query even when backslash-escaped, so they're percent-encoded first:

```python
_FT_UNSAFE = frozenset("{}*%")


def encode_file_id(value: str) -> str:
    # Percent-encode the chars the TAG parser can't handle even when escaped
    # (plus '%' for reversibility). Normal UUID/hash ids are unchanged (no-op).
    out = []
    for ch in str(value):
        out.append("%{:02X}".format(ord(ch)) if ch in _FT_UNSAFE else ch)
    return "".join(out)


def escape_tag(value: str) -> str:
    # Escape backslash FIRST so it can't consume a following escape, then the
    # rest of the TAG special characters.
    out = []
    for ch in str(value):
        if ch in '\\,.<>{}[]"\':;!@#$%^&*()-+=~| ':
            out.append("\\")
        out.append(ch)
    return "".join(out)


def file_id_filter(file_id: str) -> str:
    return f"@file_id:{{{escape_tag(encode_file_id(file_id))}}}"
```

## Step 3: Hybrid Search (filter-then-KNN)

Hybrid joins a pre-filter and the KNN clause with `=>`. The filter (a `file_id` TAG match, a text clause, or both) narrows the candidate set; KNN then ranks the survivors by vector distance.

```python
async def hybrid_search(client, collection: str, query_vec: list[float],
                        query_text: str = "", file_id: str | None = None, k: int = 5):
    index = f"idx:{collection}"
    parts = []
    if file_id:
        parts.append(file_id_filter(file_id))   # Step 2
    if query_text:
        parts.append(build_text_clause(query_text))  # Step 1
    pre = " ".join(p for p in parts if p) or "*"  # '*' = match all when no filter
    query = f"{pre}=>[KNN {k} @vector $BLOB AS __vec_score]"
    options = FtSearchOptions(
        params={"BLOB": pack_vector(query_vec)},  # pack_vector from cookbook 03
        return_fields=[ReturnField(field_identifier="__vec_score"),  # KNN distance
                       ReturnField(field_identifier="document"),
                       ReturnField(field_identifier="metadata_json")],
        limit=FtSearchLimit(0, k),
        dialect=2,
    )
    return await ft.search(client, index, query, options)
```

### ⚠️ Query-injection safety

The `=>` token separates the filter expression from the KNN clause. If you interpolated raw user input into the pre-filter, a crafted value containing `=>`, `{`, or `}` could break out of the filter and rewrite the query. Two rules keep this safe:

1. **Never string-interpolate the query vector** — pass it as the bound `$BLOB` parameter, as shown.
2. **Always escape/encode values that go into the filter** — `file_id` values go through `encode_file_id` + `escape_tag`, and full-text words through `escape_text`. The demonstrated query uses a hardcoded filter shape with only escaped values, so it is safe. Real `file_id`s are UUIDs/hashes and need no encoding, but the escaping fails *closed* (the query errors) rather than widening for any adversarial value.

## Step 4: The `vector_weight` Caveat

LangBot's `search()` ABC accepts a `vector_weight` for weighted hybrid ranking. Valkey Search is **filter-then-KNN with no native score-fusion knob**, so this backend **accepts but does not honor** `vector_weight` — passing different weights does not change result ordering. It logs a one-time warning the first time a non-default weight is supplied.

If you need weighted fusion, run vector and full-text search separately and blend the scores application-side. That is intentionally out of scope for this backend.

## Step 5: Delete by Source Document — Safely

When a knowledge-base file is removed, every chunk from it must go. `delete_by_file_id` searches for the matching keys (paginating the full result set so nothing is truncated) and deletes them. The `search_keys` helper enumerates matching keys with `NOCONTENT` (ids only) over fixed-size pages in a bounded loop — see the runnable [sample](sample/) for its full definition:

```python
async def delete_by_file_id(client, collection: str, file_id: str) -> int:
    index = f"idx:{collection}"
    query = file_id_filter(file_id)  # Step 2 — escaped/encoded
    keys = await search_keys(client, index, query)  # NOCONTENT, paginated (see sample/)
    if keys:
        # Multi-key DEL. Safe on a standalone client; in Valkey Cluster these
        # kb:{collection}: keys have no common hash tag and would scatter
        # across slots (CrossSlot) — delete per-slot or add a hash tag there.
        await client.delete(keys)  # typed delete, not a KEYS scan
    return len(keys)
```

> **Mass-deletion guard**: `delete_by_file_id` never falls back to match-all when a non-empty filter maps only to non-indexed fields — it returns 0 instead of wiping the collection. Deletes also paginate the full result set in fixed-size pages with a bounded loop, so a file with thousands of chunks is fully removed without orphaning vectors.

To drop a whole collection, drop the index and `SCAN`+`DELETE` the underlying hashes (the search module's `FT.DROPINDEX` removes only the index, not the data):

```python
async def delete_collection(client, collection: str) -> int:
    index = f"idx:{collection}"
    try:
        await ft.dropindex(client, index)  # no-op-safe if already gone
    except Exception:
        pass
    # SCAN (never KEYS) — non-blocking cursor iteration over the prefix.
    prefix = f"kb:{collection}:"
    cursor, deleted = b"0", 0
    while True:
        cursor, keys = await client.scan(cursor, match=f"{prefix}*", count=500)
        if keys:
            await client.delete(keys)
            deleted += len(keys)
        if cursor in (b"0", "0", 0):  # cursor returns to 0 when iteration completes
            break
    return deleted
```

## How It Works Under the Hood

| Operation | Valkey command | Notes |
|-----------|----------------|-------|
| Full-text | `FT.SEARCH @document:term ...` | Terms AND-ed, escaped |
| Hybrid | `FT.SEARCH <filter>=>[KNN k @vector $BLOB]` | Filter-then-KNN; no score fusion |
| Filter | `@file_id:{value}` TAG match | Only indexed fields filterable |
| Delete by file | `FT.SEARCH` (NOCONTENT) + `DEL` | Paginated; bounded loop |
| Drop collection | `FT.DROPINDEX` + `SCAN` + `DEL` | DROPINDEX leaves data; SCAN cleans it |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Filter on a non-`file_id` field returns everything | Only indexed fields are filterable; other keys live in `metadata_json` and are dropped from filters with a warning |
| Hybrid ranking ignores `vector_weight` | Expected — this backend is filter-then-KNN with no fusion (Step 4) |
| Query errors on an unusual `file_id` | The TAG encoding fails closed for `{`/`}`/`*`; real ids are UUIDs and unaffected |
| Some chunks survive a delete | Ensure deletion paginates the full result set; a single page can truncate large files |

---

That wraps the LangBot + Valkey series. The [runnable sample](sample/) exercises both the rate limiter and all three search modes against a local Valkey.

[← Back: 03 Vector Search](03-vector-search.md)
