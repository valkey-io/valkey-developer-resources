# Python Vector Search (FT Module)

> **See also:** `python-ft-api.md` for complete FT module API reference (all functions, parameters, return types).

---

## Vector Search Constraints

**❌ WRONG - Adding .sort_by() to KNN queries:**
```python
results = ft.search(...).sort_by("score")  # Causes error
```

**✅ CORRECT - KNN results already sorted:**
```python
results = ft.search(...)  # Already sorted by score
```

**Both positional and keyword arguments work for ft.search():**
```python
# Positional — valid
results = ft.search(client, index_name, query, FtSearchOptions(params={"vector": embedding_buffer}))

# Keyword — also valid, more readable
results = ft.search(
    client=client,
    index_name=index_name,
    query=query,
    options=FtSearchOptions(params={"vector": embedding_buffer}),
)
```

**❌ WRONG - Using ft.FtCreateOptions:**
```python
from glide_sync import ft
ft.create(client, index_name, schema, ft.FtCreateOptions(prefixes=["doc:"]))
# ft.FtCreateOptions does NOT exist — FtCreateOptions is a standalone class
```

**✅ CORRECT - Import FtCreateOptions directly:**
```python
from glide_sync import ft, FtCreateOptions  # top-level import (v2.3+)
ft.create(client, index_name, schema, FtCreateOptions(prefixes=["doc:"]))
```

---

## FT.SEARCH Command Pattern

### Vector Similarity Search
Return value is a two-element array / list, first element being the number of documents, the second element
being a dictionary of those documents.  See the section on *Binary Data Handling* for an example.

```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions

# ⚠️ SECURITY: Sanitize user-supplied filter and vector_field before interpolation.
# The '=>' token delimits filter from KNN clause — if user input contains '=>',
# an attacker can inject a KNN query that bypasses all filters.
if filter and '=>' in filter:
    raise ValueError("filter must not contain '=>'")
if '=>' in vector_field:
    raise ValueError("vector_field must not contain '=>'")

# Build KNN query, using `vector_field` to identify the vector field
base_query = f"*=>[KNN {k} @{vector_field} $vector AS score]"

# With metadata filter
if filter:
    base_query = f"({filter})=>[KNN {k} @{vector_field} $vector AS score]"

# Convert query vector to bytes
embedding_buffer = struct.pack(f"{len(query_vector)}f", *query_vector)

# Execute search
results = ft.search(
    client=client,
    index_name=index_name,
    query=base_query,
    options=FtSearchOptions(params={"vector": embedding_buffer}),
)

# Decode results to strings / dictionaries
docs = _decode_docs(results)
```

**Key Points:**
- Use `ft.search()` function, not a method on client and not `client.ft_search()`
- Use keyword arguments: `client=`, `index_name=`, `query=`, `options=`
- Use `FtSearchOptions` for parameters
- Results format: `[count, {key: {field: value}}]`
- **IMPORTANT:** GLIDE returns bytes - decode to strings for JSON/display
- **Skip binary fields** like vector embeddings (can't decode to UTF-8)

---

## FT.CREATE Command Pattern
Vector fields, tag fields, and numeric fields should be parameterized.
- Tag fields are used for exact matching.
- Numeric fields are used for range matching.

```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DistanceMetricType,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    VectorType,
    TagField,
    NumericField,
    FtCreateOptions,
)

# Build schema
schema = [
    VectorField(
        "content_vector",
        VectorAlgorithm.FLAT,  # or VectorAlgorithm.HNSW
        VectorFieldAttributesFlat(
            dimensions=1536,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        ),
    ),
    TagField("category"),
    NumericField("year"),
]

# Create index
ft.create(
    client,
    index_name,
    schema,
    FtCreateOptions(prefixes=["doc:"]),
)
```

### Index Creation
⚠️ **CRITICAL**: Do NOT use `client.ft_create()` to create an index.

**Key Points:**
- Use `ft.create()` function, not a method
- Import `FtCreateOptions` from ft_create_options
- Use typed field objects (VectorField, TagField, NumericField)
- Pass `FtCreateOptions` (not `ft.FtCreateOptions`) as 4th argument — import from `glide_sync` directly

---

## Add Document Pattern
Documents are stored via `HSET` with vector bytes:

```python
embedding_buffer = struct.pack(f"{len(embedding)}f", *embedding)
fields = {"embedding": embedding_buffer}
if metadata:
    fields.update(metadata)
client.hset(key, fields)
```

---

## Check Index Exists / Drop Index

**⚠️ Use `ft.list()` — not `ft.info()` — to check index existence.** `ft.info()` raises `RequestError` on missing indices, which can crash MCP server transports. `ft.list()` always returns cleanly.

```python
from glide_sync import ft

async def index_exists(client, index_name: str) -> bool:
    """Safe index existence check — never raises."""
    existing = await ft.list(client)
    names = {i.decode() if isinstance(i, bytes) else str(i) for i in (existing or [])}
    return index_name in names
```

**Drop index safely:**
```python
if await index_exists(client, index_name):
    ft.dropindex(client, index_name)
```

**Create index safely:**
```python
if not await index_exists(client, index_name):
    ft.create(client, index_name, schema, options)
```
