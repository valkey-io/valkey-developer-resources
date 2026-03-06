# General Python Guidelines

## 🚨 CRITICAL WARNINGS - READ FIRST

### Vector Search / FT Module

1. **DO NOT INFER FROM REDIS-PY**: This is Valkey GLIDE, NOT Redis-py. Redis-py patterns DO NOT apply here.
2. **NO CLIENT METHODS**: `client.ft_search()`, `client.ft_create()`, `client.ft()` DO NOT EXIST in GLIDE.
3. **ONLY SOURCE OF TRUTH**: [python-ft-api.md](python-ft-api.md) is the ONLY documentation for vector search. Do not infer usage from any other source.
4. **MODULE-LEVEL FUNCTIONS ONLY**: All FT functions are `ft.function(client, ...)` NOT `client.ft_function(...)`

**If you need to use vector search, you MUST read [python-ft-api.md](python-ft-api.md) first.
Once more, DO NOT use Redis-py as a guide, I repeat DO NOT use Redis-py as a guide.**

---

## External Resources

### FT Module API
- **[python-ft-api.md](python-ft-api.md)** - Complete FT (Search) module API reference (READ THIS for vector search)

### Code Snippets
- [python-package-selection.md](python-package-selection.md) - Selecting appropriate packages for GLIDE integration
- [python-parse-valkey-urls.md](python-parse-valkey-urls.md) - Parsing Valkey URLs into host and port
- [python-decode-docs.md](python-decode-docs.md) - Decoding bytes to strings for JSON deserialization
- [python-config.py](../assets/python-config.py) - Optimized templates for production web applications
- [https://glide.valkey.io/languages/python/api/glide_async/core/](https://glide.valkey.io/languages/python/api/glide_async/core/) - Python Async API Reference
- [https://glide.valkey.io/languages/python/api/glide_sync/core/](https://glide.valkey.io/languages/python/api/glide_sync/core/) - Python Sync API Reference

### Additional Anti-Patterns
- [python-anti-patterns.md](python-anti-patterns.md) - Additional anti-patterns including test mocking patterns, performance patterns (Hash vs JSON), code design patterns, and more

---

## Core Principles

1. Use Valkey GLIDE clients (`valkey-glide-sync` or `valkey-glide`), NOT the `valkey` package (Redis fork).
2. Use batching / pipelining when suitable to group operations for efficiency.

---

### Package Selection

**❌ NEVER use the Redis fork:**
```python
# NEVER use these imports
from valkey import Valkey
from valkey.commands.search import Search
```

**✅ ALWAYS use GLIDE:**
```python
from glide_sync import GlideClient, GlideClusterClient, ft
# or
from glide import GlideClient, GlideClusterClient, ft
```

**Why:** GLIDE is the official AWS-recommended client with better performance and active development.

### Binary Data Handling

**❌ WRONG - Not decoding bytes from search results:**
```python
results = ft.search(client, index_name, query)
print(results[1].keys())  # b'doc:1' instead of 'doc:1'
```

**✅ CORRECT - Decode bytes to strings:**
```python
for key, fields in results[1].items():
    str_key = key.decode() if isinstance(key, bytes) else key
    # See references/python-decode-docs.md for complete implementation
```

**Why:** GLIDE returns bytes for search results. Must decode to strings, but skip binary fields like embeddings. See [python-decode-docs.md](python-decode-docs.md) for details.

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

### Authentication and TLS

**Password Authentication:**
```python
from glide import GlideClientConfiguration, NodeAddress, ServerCredentials

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    credentials=ServerCredentials("password"),  # Password only
    # Or with username
    credentials=ServerCredentials("password", "username"),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

**TLS/SSL Configuration:**

For production with CA-signed certificates:
```python
from glide import AdvancedGlideClientConfiguration
from glide_shared.config import TlsAdvancedConfiguration

# Load CA certificate
with open('ca.crt', 'rb') as f:
    ca_cert = f.read()

tls_config = TlsAdvancedConfiguration(root_pem_cacerts=ca_cert)

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    use_tls=True,
    credentials=ServerCredentials("password"),
    advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

For testing with self-signed certificates (⚠️ not for production):
```python
from glide import AdvancedGlideClientConfiguration
from glide_shared.config import TlsAdvancedConfiguration

# ⚠️ WARNING: Disables certificate verification
tls_config = TlsAdvancedConfiguration(use_insecure_tls=True)

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    use_tls=True,
    credentials=ServerCredentials("password"),
    advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

**AWS ElastiCache IAM Authentication (GLIDE 2.2+):**
```python
from glide import IamAuthConfig, ServiceType

iam_config = IamAuthConfig(
    cluster_name="my-cluster",
    service=ServiceType.ELASTICACHE,  # or ServiceType.MEMORYDB
    region="us-east-1"
)

config = GlideClientConfiguration(
    addresses=[NodeAddress("my-cluster.cache.amazonaws.com", 6379)],
    use_tls=True,  # IAM auth requires TLS
    credentials=ServerCredentials(username="myUser", iam_config=iam_config),
    request_timeout=5000
)
client = await GlideClient.create(config)
```

**Note:** IAM authentication requires GLIDE 2.2 or later. Install with `pip install --upgrade valkey-glide`.

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

**❌ WRONG - Using positional arguments:**
```python
results = ft.search(client, index_name, query, options=FtSearchOptions(...))
```

**✅ CORRECT - Using keyword arguments:**
```python
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
```

**✅ CORRECT - Import FtCreateOptions directly:**
```python
from glide_sync import ft
from glide_shared.commands.server_modules.ft_options.ft_create_options import (
    FtCreateOptions
)
ft.create(client, index_name, schema, FtCreateOptions(prefixes=["doc:"]))
```

---

## FT.SEARCH Command Pattern

### Vector Similarity Search
Return value is a two-element array / list, first element being the number of documents, the second element
being a dictionary of those documents.  See the [python-decode-docs.md](python-decode-docs.md) code snippet for an example.

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

### Index Creation
⚠️ **CRITICAL**: Do NOT use `client.ft_create()` to create an index.  See [../assets/python-create-index.py](../assets/python-create-index.py) code template for correct usage.

**Key Points:**
- Use `ft.create()` function, not a method
- Import `FtCreateOptions` from ft_create_options
- Use typed field objects (VectorField, TagField, NumericField)
- Pass `FtCreateOptions` (not `ft.FtCreateOptions`) as 4th argument

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

## Best Practices

## Common Pitfalls

**Critical constraints (package selection, binary data, vector search) are in the "CRITICAL CONSTRAINTS" section above. See [python-anti-patterns.md](python-anti-patterns.md) for detailed ❌/✅ examples.**

| Description | Problem | Solution |
|-------------|---------|----------|
| Using Redis Fork Instead of GLIDE | Importing from `valkey` package instead of `glide_sync` or `glide` | Always use `valkey-glide-sync` (sync) or `valkey-glide` (async) packages |
| Incorrect Function Call Pattern | Calling `client.ft.search()` instead of `ft.search(client, ...)` | GLIDE uses module-level functions, not client methods |
| Using client.ft_search() Method | Calling `client.ft_search()` or `client.ft_create()` | Use module-level functions: `ft.search(client, ...)` or `ft.create(client, ...)` |
| Using client.ft_create() Method | Calling `client.ft_create()` for index creation | Use `ft.create(client, index_name, schema, options)` |
| Missing Keyword Arguments | Using positional arguments for `ft.search(client, index, query, options)` | Use keyword arguments: `ft.search(client=client, index_name=index, query=query, options=options)` |
| Wrong FtCreateOptions Import | Using `ft.FtCreateOptions(...)` instead of `FtCreateOptions(...)` | Import `FtCreateOptions` from `ft_create_options` and use directly |
| Missing FtSearchOptions | Passing params directly to `ft.search()` | Wrap params in `FtSearchOptions(params={...})` |
| Wrong Mock Location | Mocking `glide_sync.GlideClient` or `glide.GlideClient` instead of where it's imported | Mock at the usage location (e.g., `your_module.GlideClient`) |
| Adding .sort_by() to KNN Queries | Trying to sort KNN results manually | KNN results are pre-sorted by score, don't add sorting |
| Not Decoding Bytes in Results | GLIDE returns bytes for keys and values, causing JSON serialization errors | Decode bytes to strings: `key.decode() if isinstance(key, bytes) else key` |
| Expecting ping() to Return Bool | Assuming `client.ping()` returns `True` for success | `ping()` returns `b'PONG'` (bytes), not a boolean. Check with `== b'PONG'` |
| Using Integer Cursor with scan() | Passing integer cursor to `scan()`: `cursor = 0` | `scan()` requires string cursor: `cursor = "0"` |

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

## Client Lifecycle Management

**Async (FastAPI lifespan):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = await GlideClient.create(config)
    yield
    await _client.close()
```

**Sync:**
```python
_client = GlideClient.create(config)
atexit.register(lambda: _client.close())
```

---
# Pipelining and Batching GLIDE Patterns

Language-specific implementation details for Valkey GLIDE Python clients.

## Batch Commands (Python)

### Sync Client

See [../assets/python-batch-sync.py](../assets/python-batch-sync.py) code template

### Async Client

See [../assets/python-batch-async.py](../assets/python-batch-async.py) code template

### Error Handling

See [../assets/python-error-handling.py](../assets/python-error-handling.py) code template

### Key Points

- Use `raise_on_error` parameter (Python uses snake_case)
- Import `BatchRetryStrategy` from `glide_shared.commands.server_modules.batch_options`
- Async client requires `await` on `exec()`
- Errors are `RequestError` exceptions from `glide_shared.exceptions`
- See SKILL.md for retry strategy decision matrix

### Retry Strategies (Cluster Only)
See [python-retry-strategies.md](python-retry-strategies.md) for decision matrix code templates

---

# Performance Optimization

Config templates: [`assets/python-config.py`](../assets/python-config.py)

## AZ Affinity

```python
from glide import GlideClusterClient, GlideClusterClientConfiguration, NodeAddress, ReadFrom

config = GlideClusterClientConfiguration(
    addresses=[NodeAddress("cluster.endpoint.cache.amazonaws.com", 6379)],
    read_from=ReadFrom.AZ_AFFINITY,
    client_az="us-east-1a",
    request_timeout=500,
)
client = await GlideClusterClient.create(config)
```

## Throughput Tuning

```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    inflight_requests_limit=2000,  # Default: 1000
    request_timeout=500,
)
```

## Serverless / Lambda

```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    lazy_connect=True,  # Defer connection until first command
    request_timeout=500,
)
client = await GlideClient.create(config)
```

## Dedicated Blocking Client

```python
blocking_client = await GlideClient.create(GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=30000,
    client_name="queue-worker",
))
item = await blocking_client.blpop(["queue"], 30)
```

## Hash vs JSON for Structured Data

## Context Manager Pattern

```python
# Async
async with await GlideClient.create(config) as client:
    result = await client.get("key")

# Sync
with GlideClient.create(config) as client:
    result = client.get("key")
```

## Monitoring

### OpenTelemetry

```python
from glide import OpenTelemetry, OpenTelemetryConfig, OpenTelemetryTracesConfig, OpenTelemetryMetricsConfig

OpenTelemetry.init(OpenTelemetryConfig(
    traces=OpenTelemetryTracesConfig(
        endpoint="http://localhost:4318/v1/traces",
        sample_percentage=1,  # 1% for production
    ),
    metrics=OpenTelemetryMetricsConfig(
        endpoint="http://localhost:4318/v1/metrics",
    ),
))
```

### Logging

```python
from glide import Logger

Logger.set_logger_config("warn", "glide.log")   # Production
Logger.set_logger_config("error")                # Max performance
```

## Concurrent Operations (Async)

```python
# When operations are truly independent and on different keys:
user, posts, comments = await asyncio.gather(
    client.get("user:123"),
    client.lrange("posts:123", 0, -1),
    client.lrange("comments:123", 0, -1),
)
```

Server-side config: [`references/server-configuration-guide.md`](server-configuration-guide.md)
