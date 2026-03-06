# Python GLIDE FT (Search) Module API Reference

**CRITICAL: All functions are module-level. Import as `from glide_sync import ft` or `from glide import ft`**

## Core Functions

### ft.create()
```python
ft.create(
    client: GlideClient,
    index_name: str,
    schema: List[Field],
    options: Optional[FtCreateOptions] = None
) -> str  # Returns "OK"
```

**Example:**
```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions, Field, TextField
)

schema = [TextField("title")]
ft.create(client, "my_idx", schema, FtCreateOptions(prefixes=["doc:"]))
```

### ft.search()
```python
ft.search(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtSearchOptions] = None
) -> FtSearchResponse  # [count, {key: {field: value}}]
```

**Example:**
```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions
)

# Basic search
results = ft.search(client, "idx", "*", options=None)
# results = [1, {b'doc:1': {b'title': b'Hello'}}]

# Vector search with params
results = ft.search(
    client=client,
    index_name="idx",
    query="*=>[KNN 5 @embedding $vec]",
    options=FtSearchOptions(params={"vec": embedding_bytes})
)
```

**IMPORTANT:** Results are bytes. Must decode:
```python
for key, fields in results[1].items():
    str_key = key.decode() if isinstance(key, bytes) else key
    # See references/python-decode-docs.md for full implementation
```

### ft.dropindex()
```python
ft.dropindex(client: GlideClient, index_name: str) -> str  # Returns "OK"
```

### ft.list()
```python
ft.list(client: GlideClient) -> List[bytes]  # Returns list of index names
```

### ft.info()
```python
ft.info(client: GlideClient, index_name: str) -> FtInfoResponse
```

### ft.aggregate()
```python
ft.aggregate(
    client: GlideClient,
    index_name: str,
    query: str,
    options: Optional[FtAggregateOptions] = None
) -> FtAggregateResponse
```

### ft.profile()
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

## Key Patterns

### ❌ WRONG - These methods DO NOT exist:
```python
client.ft_create(...)  # NO!
client.ft_search(...)  # NO!
client.ft.create(...)  # NO!
client.ft.search(...)  # NO!
```

### ✅ CORRECT - Module-level functions:
```python
from glide_sync import ft

ft.create(client, ...)   # YES
ft.search(client, ...)   # YES
```

### Import Pattern:
```python
# Sync
from glide_sync import ft, GlideClient

# Async
from glide import ft, GlideClient
```

### Options Import Pattern:
```python
# FtCreateOptions
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions,
    Field,
    TextField,
    VectorField,
    DistanceMetricType
)

# FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_search_options import (
    FtSearchOptions,
    ReturnField
)
```

## Common Mistakes

1. **Using client methods**: `client.ft_search()` does not exist
2. **Wrong import**: `ft.FtCreateOptions` does not exist, import from `ft_create_options`
3. **Not decoding bytes**: Search results return bytes, must decode to strings
4. **Positional args**: Use keyword arguments for clarity
5. **Adding .sort_by()**: KNN results are already sorted

## See Also

- [python.md](python.md) - Full Python guide
- [python-anti-patterns.md](python-anti-patterns.md) - Common mistakes
- [python-decode-docs.md](python-decode-docs.md) - Byte decoding implementation
