# Python GLIDE FT (Search) Module API Reference

## ⚠️ CRITICAL - READ BEFORE USING FT MODULE

1. **NO CLIENT METHODS EXIST**: `client.ft_search()`, `client.ft_create()`, `client.ft()` DO NOT EXIST
2. **ALL FUNCTIONS ARE MODULE-LEVEL**: Import `ft` and call `ft.function(client, ...)`
3. **DO NOT INFER FROM REDIS-PY**: This is NOT Redis-py. Redis-py patterns DO NOT apply.
4. **THIS IS THE ONLY DOCUMENTATION**: Vector search API is not documented elsewhere. Do not infer usage from other sources.

## Import Pattern

```python
# Sync
from glide_sync import ft, GlideClient

# Async  
from glide import ft, GlideClient

# WRONG - These do not exist:
# from glide_sync import FT  # NO
# client.ft  # NO
# client.ft_search  # NO
```

## Core Functions

### ft.create()

**Creates a search index.**

```python
ft.create(
    client: GlideClient,
    index_name: str,
    schema: List[Field],
    options: Optional[FtCreateOptions] = None
) -> str  # Returns "OK"
```

**Parameters:**
- `client`: GlideClient instance (first parameter, always required)
- `index_name`: Name for the index
- `schema`: List of Field objects (TextField, VectorField, etc.)
- `options`: FtCreateOptions with prefixes, data type, etc.

**Complete Example:**
```python
from glide_sync import ft, GlideClient
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions,
    TextField,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    DistanceMetricType,
    VectorType,
    DataType
)

# Define schema
schema = [
    TextField("title"),
    VectorField(
        "embedding",
        VectorAlgorithm.FLAT,
        VectorFieldAttributesFlat(
            dimensions=768,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32
        )
    )
]

# Create index - NOTE: ft.create(client, ...) NOT client.ft_create(...)
result = ft.create(
    client=client,
    index_name="products_idx",
    schema=schema,
    options=FtCreateOptions(data_type=DataType.HASH, prefixes=["product:"])
)
# Returns: "OK"
```

**Common Mistakes:**
```python
# ❌ WRONG - Method does not exist
await client.ft_create("idx", schema)

# ❌ WRONG - No ft attribute on client
client.ft.create("idx", schema)

# ✅ CORRECT - Module-level function
ft.create(client, "idx", schema)
```

### ft.search()

**Searches an index using a query.**

```python
ft.search(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtSearchOptions] = None
) -> FtSearchResponse  # [count, {key: {field: value}}]
```

**Parameters:**
- `client`: GlideClient instance (first parameter, always required)
- `index_name`: Name of the index to search
- `query`: Search query string (e.g., "*", "hello", "*=>[KNN 5 @vec $query]")
- `options`: FtSearchOptions with params, return fields, etc.

**Return Format:**
```python
# Returns: [count, {key: {field: value}}]
# Example: [2, {b'doc:1': {b'title': b'Hello'}, b'doc:2': {b'title': b'World'}}]
```

**Basic Search Example:**
```python
from glide_sync import ft, GlideClient

# Simple search - NOTE: ft.search(client, ...) NOT client.ft_search(...)
results = ft.search(
    client=client,
    index_name="products_idx",
    query="*",
    options=None
)

count = results[0]  # Number of results
docs = results[1]   # Dict of documents
```

**Vector Search Example:**
```python
from glide_sync import ft, GlideClient
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions
)
import struct

# Convert embedding to bytes
query_embedding = [0.1, 0.2, 0.3, ...]  # Your embedding
embedding_bytes = b''.join(struct.pack('f', x) for x in query_embedding)

# Vector search - NOTE: ft.search(client, ...) NOT client.ft_search(...)
results = ft.search(
    client=client,
    index_name="products_idx",
    query="*=>[KNN 5 @embedding $vec]",
    options=FtSearchOptions(params={"vec": embedding_bytes})
)

# Decode results (they are bytes)
for key, fields in results[1].items():
    str_key = key.decode() if isinstance(key, bytes) else key
    # See the section on 'Binary Data Handling' for complete decoding
```

**Common Mistakes:**
```python
# ❌ WRONG - Method does not exist
results = await client.ft_search("idx", "*")

# ❌ WRONG - No ft attribute on client  
results = client.ft.search("idx", "*")

# ✅ CORRECT - Module-level function
results = ft.search(client, "idx", "*")
```

### ft.dropindex()

**Drops an index.**

```python
ft.dropindex(client: GlideClient, index_name: str) -> str  # Returns "OK"
```

**Example:**
```python
from glide_sync import ft

# NOTE: ft.dropindex(client, ...) NOT client.ft_dropindex(...)
result = ft.dropindex(client, "products_idx")
```

### ft.list()

**Lists all indexes.**

```python
ft.list(client: GlideClient) -> List[bytes]  # Returns list of index names
```

**Example:**
```python
from glide_sync import ft

# NOTE: ft.list(client) NOT client.ft_list()
indexes = ft.list(client)
# Returns: [b'idx1', b'idx2']
```

### ft.info()

**Gets information about an index.**

```python
ft.info(client: GlideClient, index_name: str) -> FtInfoResponse
```

**Example:**
```python
from glide_sync import ft

# NOTE: ft.info(client, ...) NOT client.ft_info(...)
info = ft.info(client, "products_idx")
```

### ft.aggregate()

**Performs aggregation query.**

```python
ft.aggregate(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtAggregateOptions] = None
) -> FtAggregateResponse
```

### ft.profile()

**Profiles a search query.**

```python
ft.profile(
    client: GlideClient,
    index_name: str,
    query: str,
    options: FtProfileOptions
) -> FtProfileResponse
```

## Alias Management

### ft.aliasadd()
```python
ft.aliasadd(client: GlideClient, alias: str, index_name: str) -> str
```

### ft.aliasdel()
```python
ft.aliasdel(client: GlideClient, alias: str) -> str
```

### ft.aliasupdate()
```python
ft.aliasupdate(client: GlideClient, alias: str, index_name: str) -> str
```

### ft.aliaslist()
```python
ft.aliaslist(client: GlideClient) -> Mapping[bytes, bytes]
```

## Query Explanation

### ft.explain()
```python
ft.explain(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtExplainOptions] = None
) -> bytes
```

### ft.explaincli()
```python
ft.explaincli(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtExplainOptions] = None
) -> bytes
```

## Required Imports

### For ft.create():
```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions,
    Field,
    TextField,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    DistanceMetricType,
    VectorType,
    DataType
)
```

### For ft.search():
```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions,
    ReturnField
)
```

## Critical Reminders

### ❌ THESE DO NOT EXIST:
```python
client.ft_create(...)      # NO - Not a method
client.ft_search(...)      # NO - Not a method
client.ft.create(...)      # NO - No ft attribute
client.ft.search(...)      # NO - No ft attribute
ft.FtCreateOptions(...)    # NO - Import from ft_create_options
```

### ✅ CORRECT PATTERNS:
```python
from glide_sync import ft

ft.create(client, ...)     # YES - Module-level function
ft.search(client, ...)     # YES - Module-level function
ft.dropindex(client, ...)  # YES - Module-level function
```

## Common Mistakes

1. **Using client methods**: `client.ft_search()` does not exist - use `ft.search(client, ...)`
2. **Using client.ft attribute**: `client.ft.create()` does not exist - use `ft.create(client, ...)`
3. **Wrong import**: `ft.FtCreateOptions` does not exist - import from `ft_create_options`
4. **Not decoding bytes**: Search results return bytes - must decode to strings
5. **Positional args**: Use keyword arguments for clarity
6. **Inferring from Redis-py**: This is NOT Redis-py - do not use Redis-py patterns

## See Also

- `python.md` - Full Python guide
- `python-anti-patterns.md` - Common mistakes
- `python-decode-docs.md` - Byte decoding implementation
- `../assets/python-create-index.py` - Complete working example
