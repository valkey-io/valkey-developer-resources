# General Python Guidelines

## External Resources

### Code Snippets
- [parse_valkey_urls.md](snippets/parse_valkey_urls.md) - Parsing Valkey URLs into host and port
- [decode_docs.md](snippets/decode_docs.md) - Decoding bytes to strings for JSON deserialization

---

## Core Principles

1.  Use Valkey GLIDE clients (`valkey-glide-sync` or `valkey-glide`), NOT the `valkey` package (Redis fork).
2.  Avoid use of catching general exceptions (`Exception`) when handling GLIDE errors, this is too vague.
3.  Use batching / pipelining when suitable to group operations for efficiency.

---

## Package Selection

### ✅ CORRECT: Use GLIDE

**Synchronous (for sync applications):**
```python
from glide_sync import GlideClient, GlideClusterClient, ft
from glide_sync import GlideClientConfiguration, GlideClusterClientConfiguration, NodeAddress
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DistanceMetricType,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    VectorType,
    TagField,
    NumericField,
)
```
**Package:** `valkey-glide-sync>=2.0.0`

**Asynchronous (for async applications):**
```python
from glide import GlideClient, GlideClusterClient, ft
from glide import GlideClientConfiguration, GlideClusterClientConfiguration, NodeAddress
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DistanceMetricType,
    VectorField,
    VectorFieldAttributesFlat,
    VectorAlgorithm,
    VectorType,
    TagField,
    NumericField,
)
```
**Package:** `valkey-glide>=2.0.0`

**Note:** `glide_shared` is used by both sync and async packages for shared types and options.

### ❌ INCORRECT: Don't use Redis fork
```python
# NEVER use these imports
from valkey import Valkey
from valkey.commands.search import Search
```

**Why:** The `valkey` package is a Redis fork with limited maintenance. GLIDE is the official AWS-recommended client with better performance, proper async support, and active development.

---

## Client Creation Pattern

### Choose Sync vs Async

**Use synchronous client when:**
- Building sync applications (e.g., LangChain VectorStore, Flask apps)
- Integrating with sync-only frameworks
- Simplicity is preferred over concurrency

**Use asynchronous client when:**
- Building async applications (FastAPI, aiohttp)
- Need high concurrency
- Using async/await patterns throughout

### Choose Cluster vs Standalone

**Use cluster client when:**
- Running multiple GLIDE nodes
- Using multiple Valkey clusters

Otherwise, use standalone client.

### General Contract

```python
from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    GlideClusterClient,
    GlideClusterClientConfiguration,
    NodeAddress,
)
from glide_shared.exceptions import ConnectionError, ClosingError, TimeoutError

def get_client(valkey_url: str, **kwargs) -> GlideClient | GlideClusterClient:
    host, port = _parse_valkey_url(valkey_url)
    addresses = [NodeAddress(host, port)]
    config = GlideClientConfiguration(
        addresses=addresses,
        request_timeout=5000,
        **kwargs
    )
    return GlideClient.create(config)
```

**Key Points:**
- Import from `glide` instead of `glide_sync` for the async client
- Use `NodeAddress` for connection configuration
- Add `request_timeout` to prevent hanging
- Use `await` for async client operations
- Async client requires `await` on `.create()`

---

## Distance Metrics Mapping

```python
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    DistanceMetricType,
)

distance_map = {
    "COSINE": DistanceMetricType.COSINE,
    "L2": DistanceMetricType.L2,
    "IP": DistanceMetricType.IP,
}
```

---

## FT.SEARCH Command Pattern

### Vector Similarity Search
Return value is a two-element array / list, first element being the number of documents, the second element
being a dictionary of those documents.  See the [decode_docs.md](snippets/decode_docs.md) code snippet for an example.

```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions

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
- Use `ft.search()` function, not a method on client
- Use keyword arguments: `client=`, `index_name=`, `query=`, `options=`
- Use `FtSearchOptions` for parameters
- Results format: `[count, {key: {field: value}}]`
- **IMPORTANT:** GLIDE returns bytes - decode to strings for JSON/display
- **Skip binary fields** like vector embeddings (can't decode to UTF-8)

### ⚠️ CONSTRAINT: No .sort_by() with KNN

**DON'T** add `.sort_by()` to KNN queries - it causes errors. KNN results are already sorted by score.

```python
# ❌ WRONG - causes error
results = ft.search(...).sort_by("score")

# ✅ CORRECT - results already sorted
results = ft.search(...)
```

### ⚠️ CONSTRAINT: Do not use positional arguments
```python
# ❌ WRONG - positional arguments
results = ft.search(
    client,
    index_name,
    query,
    options=FtSearchOptions(params={"vector": embedding_buffer}),
)

# ✅ CORRECT - keyword arguments
results = ft.search(
    client=client,
    index_name=index_name,
    query=query,
    options=FtSearchOptions(params={"vector": embedding_buffer}),
)
```

---

## FT.CREATE Command Pattern
Vector fields, tag fields, and numeric fields should be parameterized.
- Tag fields are used for exact matching.
- Numeric fields are used for range matching.

### Index Creation

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

**Key Points:**
- Use `ft.create()` function, not a method
- Import `FtCreateOptions` from ft_create_options
- Use typed field objects (VectorField, TagField, NumericField)
- Pass `FtCreateOptions` (not `ft.FtCreateOptions`) as 4th argument

### ⚠️ CONSTRAINT: Must import FtCreateOptions directly
```python
# ❌ WRONG - using ft.FtCreateOptions
from glide_sync import ft
ft.create(client, index_name, schema, ft.FtCreateOptions(prefixes=["doc:"]))

# ✅ CORRECT - import and use FtCreateOptions directly
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions
)
ft.create(client, index_name, schema, FtCreateOptions(prefixes=["doc:"]))
```

### ⚠️ CONSTRAINT: **DON'T** add `.sort_by()` to KNN queries
`.sort_by()` causes errors. KNN results are already sorted by score.
```python
# ❌ WRONG - causes error
results = ft.search(...).sort_by("score")

# ✅ CORRECT - results already sorted
results = ft.search(...)
```

---

## Add Document Pattern
Documents can be added using `HSET`, the example implies a vector field named `embedding`.

```python
    # Convert vector to bytes
    embedding_buffer = struct.pack(f"{len(embedding)}f", *embedding)

    # Build field dict
    fields = {"embedding": embedding_buffer}
    if metadata:
        fields.update(metadata)

    # Store document
    client.hset(key, fields)
```

---

## FT.INFO and FT.DROPINDEX

### Check Index Exists

```python
from glide_sync import ft
from glide_shared.exceptions import RequestError

try:
    ft.info(client, index_name)
    index_exists = True
except RequestError:
    index_exists = False
```

### Drop Index

```python
from glide_sync import ft
from glide_shared.exceptions import RequestError

try:
    ft.dropindex(client, index_name)
except RequestError:
    pass  # Index didn't exist
```

**Key Points:**
- `ft.info()` raises `RequestError` when index doesn't exist
- Catch `RequestError` specifically, not broad exceptions
- `RequestError` is the base class for all request-related errors

---

## Type Hints

### Client Type Union

**Synchronous:**
```python
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from glide_sync import GlideClient, GlideClusterClient
    GlideClientType = Union[GlideClient, GlideClusterClient]
    # Or with Python 3.10+
    GlideClientType = GlideClient | GlideClusterClient
```

**Asynchronous:**
```python
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from glide import GlideClient, GlideClusterClient
    GlideClientType = Union[GlideClient, GlideClusterClient]
    # Or with Python 3.10+
    GlideClientType = GlideClient | GlideClusterClient
```

**Why:** Avoid runtime import errors when GLIDE is not installed.

---

## Import Organization

### Conditional Imports

**Synchronous:**
```python
# At module level - for type hints only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glide_sync import GlideClient, GlideClusterClient

# In functions - for runtime use
def some_function():
    try:
        from glide_sync import ft
        from glide_shared.commands.server_modules.ft_options.ft_search_options import (
            FtSearchOptions,
        )
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide-sync python package. "
            "Please install it with `pip install valkey-glide-sync>=2.0.0`."
        )
```

**Asynchronous:**
```python
# At module level - for type hints only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glide import GlideClient, GlideClusterClient

# In functions - for runtime use
async def some_function():
    try:
        from glide import ft
        from glide_shared.commands.server_modules.ft_options.ft_search_options import (
            FtSearchOptions,
        )
    except ImportError:
        raise ImportError(
            "Could not import valkey-glide python package. "
            "Please install it with `pip install valkey-glide>=2.0.0`."
        )
```

**Key Points:**
- Use `TYPE_CHECKING` for type hints to avoid runtime imports
- Import GLIDE modules inside functions for lazy loading
- Provide helpful error messages with installation instructions

---

## Testing Patterns

### Mocking GLIDE Clients

```python
from unittest.mock import MagicMock, patch

# ✅ CORRECT: Mock at the import location
@patch("langchain_aws.utilities.valkey.GlideClient")
@patch("langchain_aws.utilities.valkey.GlideClusterClient")
def test_something(mock_cluster, mock_client):
    # Mock the create() class method
    mock_client.create.return_value = MagicMock()
    ...

# ❌ WRONG: Mocking at glide_sync module
@patch("glide_sync.GlideClient")  # Won't work if already imported elsewhere
```

**Lesson Learned:** Mock at the location where the object is used, not where it's defined.

---

## Common Pitfalls

### 1. Using Redis Fork Instead of GLIDE
**Problem:** Importing from `valkey` package instead of `glide_sync` or `glide`
**Solution:** Always use `valkey-glide-sync` (sync) or `valkey-glide` (async) packages

### 2. Incorrect Function Call Pattern
**Problem:** Calling `client.ft.search()` instead of `ft.search(client, ...)`
**Solution:** GLIDE uses module-level functions, not client methods

### 3. Missing Keyword Arguments
**Problem:** Using positional arguments for `ft.search(client, index, query, options)`
**Solution:** Use keyword arguments: `ft.search(client=client, index_name=index, query=query, options=options)`

### 4. Wrong FtCreateOptions Import
**Problem:** Using `ft.FtCreateOptions(...)` instead of `FtCreateOptions(...)`
**Solution:** Import `FtCreateOptions` from `ft_create_options` and use directly

### 5. Missing FtSearchOptions
**Problem:** Passing params directly to `ft.search()`
**Solution:** Wrap params in `FtSearchOptions(params={...})`

### 6. Wrong Mock Location
**Problem:** Mocking `glide_sync.GlideClient` or `glide.GlideClient` instead of where it's imported
**Solution:** Mock at the usage location (e.g., `your_module.GlideClient`)

### 7. Adding .sort_by() to KNN Queries
**Problem:** Trying to sort KNN results manually
**Solution:** KNN results are pre-sorted by score, don't add sorting

### 8. Not Decoding Bytes in Results
**Problem:** GLIDE returns bytes for keys and values, causing JSON serialization errors
**Solution:** Decode bytes to strings: `key.decode() if isinstance(key, bytes) else key`

---

## Dependencies

### Package Installation

**Synchronous applications:**
```toml
[project.optional-dependencies]
valkey = ["valkey-glide-sync>=2.0.0"]
```

**Asynchronous applications:**
```toml
[project.optional-dependencies]
valkey = ["valkey-glide>=2.0.0"]
```

**Why optional:** Keeps base package lightweight, users install only what they need.

---

## Summary Checklist

When implementing Valkey functionality with GLIDE:

- [ ] Choose sync (`valkey-glide-sync`) or async (`valkey-glide`) based on application needs
- [ ] Import from `glide_sync`/`glide` and `glide_shared`, NOT `valkey` package
- [ ] Use module-level functions: `ft.search(client=..., ...)`, not `client.ft.search(...)`
- [ ] Use keyword arguments for `ft.search()` and `ft.create()`
- [ ] Import `FtCreateOptions` and `FtSearchOptions` directly (not `ft.FtCreateOptions`)
- [ ] Wrap search params in `FtSearchOptions(params={...})`
- [ ] Use typed field objects for schema creation
- [ ] Catch `RequestError` for index operations (not broad exceptions)
- [ ] Decode bytes to strings for JSON serialization (skip binary fields)
- [ ] Don't add `.sort_by()` to KNN queries
- [ ] Mock at import location, not definition location
- [ ] Use `TYPE_CHECKING` for type hints
- [ ] Provide helpful ImportError messages
- [ ] Support both cluster and standalone modes
- [ ] Use `await` for async client operations

---

## References

- [Valkey GLIDE Documentation](https://glide.valkey.io/)
- [GLIDE Python Client](https://github.com/valkey-io/valkey-glide/tree/main/python)
- [Valkey FT.SEARCH](https://valkey.io/commands/ft.search/)

---
# Pipelining and Batching GLIDE Patterns

Language-specific implementation details for Valkey GLIDE Python clients.

## Batch Commands (Python)

### Sync Client

```python
from glide_sync import Batch, ClusterBatch, BatchOptions, ClusterBatchOptions
from glide_shared.commands.server_modules.batch_options import BatchRetryStrategy

# Standalone atomic batch (transaction)
batch = Batch(True)
batch.set("key", "value")
batch.get("key")
result = client.exec(batch, raise_on_error=True)

# Standalone pipeline
batch = Batch(False)
batch.set("key1", "value1")
batch.set("key2", "value2")
result = client.exec(batch, raise_on_error=False)

# Cluster pipeline with options
batch = ClusterBatch(False)
batch.set("{user}:1", "data1")
batch.set("{user}:2", "data2")

retry_strategy = BatchRetryStrategy(
    retry_server_error=True,
    retry_connection_error=False
)
options = ClusterBatchOptions(
    timeout=2000,
    retry_strategy=retry_strategy
)
result = client.exec(batch, raise_on_error=False, options=options)
```

### Async Client

```python
from glide import Batch, ClusterBatch, BatchOptions, ClusterBatchOptions
from glide_shared.commands.server_modules.batch_options import BatchRetryStrategy

# Standalone atomic batch (transaction)
batch = Batch(True)
batch.set("key", "value")
batch.get("key")
result = await client.exec(batch, raise_on_error=True)

# Cluster pipeline with retry strategy
batch = ClusterBatch(False)
batch.set("{user}:1", "data1")
batch.get("{user}:1")

retry_strategy = BatchRetryStrategy(
    retry_server_error=True,
    retry_connection_error=False
)
options = ClusterBatchOptions(
    timeout=2000,
    retry_strategy=retry_strategy
)
result = await client.exec(batch, raise_on_error=False, options=options)
```

### Error Handling

```python
# raise_on_error=False - errors in result array
batch = ClusterBatch(False)
batch.set("key", "hello")
batch.lpop("key")  # WRONGTYPE error
batch.delete(["key"])

result = client.exec(batch, raise_on_error=False)
# Result: ['OK', RequestError('WRONGTYPE...'), 1]

# raise_on_error=True - raises first error
batch = Batch(True)
batch.set("key", "hello")
batch.lpop("key")  # WRONGTYPE error

try:
    result = client.exec(batch, raise_on_error=True)
except RequestError as e:
    print(f"Batch failed: {e}")
```

### Key Points

- Use `raise_on_error` parameter (Python uses snake_case)
- Import `BatchRetryStrategy` from `glide_shared.commands.server_modules.batch_options`
- Async client requires `await` on `exec()`
- Errors are `RequestError` exceptions from `glide_shared.exceptions`

---

**Version:** 1.0
**Last Updated:** 2026-02-13
**Source:** Production implementation experience
