# Agent Skill: Valkey GLIDE Client Development

**Type:** AI Coding Assistant Skill
**Purpose:** Guide correct usage of Valkey GLIDE clients based on real-world implementation experience
**Audience:** AI agents (Claude, ChatGPT, etc.) and human developers

## External Resources

### Working Examples
- [Flask Demo](flask_demo/) - Complete Flask app demonstrating sync client patterns
- [Code Snippets](snippets/) - Reusable functions for common operations

### Code Snippets
- [client_creation_sync.py](snippets/client_creation_sync.py) - Sync client creation with cluster fallback
- [client_creation_async.py](snippets/client_creation_async.py) - Async client creation with cluster fallback
- [index_management_sync.py](snippets/index_management_sync.py) - Index creation and management
- [vector_search_sync.py](snippets/vector_search_sync.py) - Sync vector search and document operations
- [vector_search_async.py](snippets/vector_search_async.py) - Async vector search and document operations

---

## Overview

This skill provides patterns and constraints for implementing Valkey client operations using the GLIDE library. It captures lessons learned from production implementations to prevent common pitfalls.

---

## Core Principle

**Use Valkey GLIDE clients (`valkey-glide-sync` or `valkey-glide-async`), NOT the `valkey` package (Redis fork).**

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
**Package:** `valkey-glide-async>=2.0.0`

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

### Synchronous Client

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
    """Create GLIDE client with automatic cluster detection."""
    host, port = _parse_valkey_url(valkey_url)
    addresses = [NodeAddress(host, port)]
    
    # Try standalone first (more common for local dev)
    try:
        config = GlideClientConfiguration(
            addresses=addresses, 
            request_timeout=5000,
            **kwargs
        )
        return GlideClient.create(config)
    except (ConnectionError, ClosingError, TimeoutError) as e:
        # If standalone fails, try cluster
        try:
            config = GlideClusterClientConfiguration(
                addresses=addresses,
                request_timeout=5000,
                **kwargs
            )
            return GlideClusterClient.create(config)
        except (ConnectionError, ClosingError, TimeoutError) as cluster_error:
            raise RuntimeError(
                f"Failed to connect to Valkey at {valkey_url}. "
                f"Standalone error: {e}. Cluster error: {cluster_error}. "
                "Make sure Valkey is running."
            )
```

### Asynchronous Client

```python
from glide import (
    GlideClient,
    GlideClientConfiguration,
    GlideClusterClient,
    GlideClusterClientConfiguration,
    NodeAddress,
)
from glide_shared.exceptions import ConnectionError, ClosingError, TimeoutError

async def get_client(valkey_url: str, **kwargs) -> GlideClient | GlideClusterClient:
    """Create async GLIDE client with automatic cluster detection."""
    host, port = _parse_valkey_url(valkey_url)
    addresses = [NodeAddress(host, port)]
    
    # Try standalone first (more common for local dev)
    try:
        config = GlideClientConfiguration(
            addresses=addresses,
            request_timeout=5000,
            **kwargs
        )
        return await GlideClient.create(config)
    except (ConnectionError, ClosingError, TimeoutError) as e:
        # If standalone fails, try cluster
        try:
            config = GlideClusterClientConfiguration(
                addresses=addresses,
                request_timeout=5000,
                **kwargs
            )
            return await GlideClusterClient.create(config)
        except (ConnectionError, ClosingError, TimeoutError) as cluster_error:
            raise RuntimeError(
                f"Failed to connect to Valkey at {valkey_url}. "
                f"Standalone error: {e}. Cluster error: {cluster_error}. "
                "Make sure Valkey is running."
            )
```

**Key Points:**
- Use `NodeAddress` for connection configuration
- Try standalone mode first (more common for local development)
- Catch specific GLIDE exceptions: `ConnectionError`, `ClosingError`, `TimeoutError`
- Add `request_timeout` to prevent hanging
- Use `await` for async client operations
- Async client requires `await` on `.create()`

---

## FT.SEARCH Command Pattern

### Vector Similarity Search

```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_search_options import FtSearchOptions

# Build KNN query
base_query = f"*=>[KNN {k} @{vector_field} $vector AS score]"

# With metadata filter
if filter:
    base_query = f"({filter})=>[KNN {k} @{vector_field} $vector AS score]"

# Execute search
results = ft.search(
    client=client,
    index_name=index_name,
    query=base_query,
    options=FtSearchOptions(params={"vector": embedding_buffer}),
)

# Decode bytes to strings (GLIDE returns bytes)
count = results[0]
docs = []
if count > 0 and len(results) > 1:
    for key, fields in results[1].items():
        str_key = key.decode() if isinstance(key, bytes) else key
        str_fields = {}
        for field_key, field_value in fields.items():
            str_field_key = field_key.decode() if isinstance(field_key, bytes) else field_key
            # Skip binary fields (like vector embeddings)
            if str_field_key == "embedding":
                continue
            try:
                str_field_value = field_value.decode() if isinstance(field_value, bytes) else field_value
                str_fields[str_field_key] = str_field_value
            except (UnicodeDecodeError, AttributeError):
                pass  # Skip binary fields
        docs.append({"key": str_key, **str_fields})
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

---

## FT.CREATE Command Pattern

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
```

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
            "Could not import valkey-glide-async python package. "
            "Please install it with `pip install valkey-glide-async>=2.0.0`."
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

## Common Pitfalls

### 1. Using Redis Fork Instead of GLIDE
**Problem:** Importing from `valkey` package instead of `glide_sync` or `glide`
**Solution:** Always use `valkey-glide-sync` (sync) or `valkey-glide-async` (async) packages

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
valkey = ["valkey-glide-async>=2.0.0"]
```

**Why optional:** Keeps base package lightweight, users install only what they need.

---

## Summary Checklist

When implementing Valkey functionality with GLIDE:

- [ ] Choose sync (`valkey-glide-sync`) or async (`valkey-glide-async`) based on application needs
- [ ] Import from `glide_sync`/`glide` and `glide_shared`, NOT `valkey` package
- [ ] Use module-level functions: `ft.search(client=..., ...)`, not `client.ft.search(...)`
- [ ] Use keyword arguments for `ft.search()` and `ft.create()`
- [ ] Import `FtCreateOptions` and `FtSearchOptions` directly (not `ft.FtCreateOptions`)
- [ ] Wrap search params in `FtSearchOptions(params={...})`
- [ ] Use typed field objects for schema creation
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

## Usage as AI Agent Skill

### For Claude (Anthropic)

Add to system prompt or project knowledge:
```
Use the Valkey GLIDE Agent Skill when implementing Valkey client operations.
Key constraints: Use valkey-glide-sync or valkey-glide-async, never the valkey package.
```

### For ChatGPT (OpenAI)

Add to custom instructions or GPT configuration:
```
When working with Valkey: Use GLIDE clients (valkey-glide-sync/async), not valkey package.
Follow module-level function pattern: ft.search(client, ...) not client.ft.search(...)
```

### For GitHub Copilot

Reference in code comments:
```python
# Following Valkey GLIDE Agent Skill patterns
# Using valkey-glide-sync for synchronous operations
```

---

**Version:** 1.0
**Last Updated:** 2026-02-13
**Source:** Production implementation experience
