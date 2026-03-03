# General Python Guidelines

## External Resources

### Code Snippets
- [parse_valkey_urls.md](snippets/parse_valkey_urls.md) - Parsing Valkey URLs into host and port
- [decode_docs.md](snippets/decode_docs.md) - Decoding bytes to strings for JSON deserialization
- [https://glide.valkey.io/languages/python/api/glide_async/core/](https://glide.valkey.io/languages/python/api/glide_async/core/) - Python Async API Reference
- [https://glide.valkey.io/languages/python/api/glide_sync/core/](https://glide.valkey.io/languages/python/api/glide_sync/core/) - Python Sync API Reference

---

## Core Principles

1. Use Valkey GLIDE clients (`valkey-glide-sync` or `valkey-glide`), NOT the `valkey` package (Redis fork).
2. Use batching / pipelining when suitable to group operations for efficiency.

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

### ✅ CORRECT: Status-Based Returns
```python
async def fetch_data(key: str) -> dict:
    value = await client.get(key)
    if value is None:
        return {"status": "error", "msg": "Not found"}
    return {"status": "ok", "data": value}
```

### ❌ INCORRECT: Exceptions as Control Flow
```python
async def fetch_data(key: str) -> str:
    value = await client.get(key)
    if value is None:
        raise ValueError("Not found")  # Don't use exceptions for normal logic
    return value
```

**Why:** Exceptions are expensive and make code hard to read. Use status returns for predictable logic.

---

### ✅ CORRECT: Module-Level Functions
```python
async def get_user(client, user_id: str) -> str:
    return await client.get(f"user:{user_id}")
```

### ❌ INCORRECT: Static Method-Only Classes
```python
class CacheUtils:
    @staticmethod
    async def get_user(client, user_id: str) -> str:
        return await client.get(f"user:{user_id}")
```

**Why:** Python has modules for namespacing. Static-only classes add unnecessary boilerplate.

---

### ✅ CORRECT: Protocol-Based Abstraction
```python
from typing import Protocol

class CacheClient(Protocol):
    async def get(self, key: str) -> str: ...
    async def set(self, key: str, value: str): ...

class UserService:
    def __init__(self, cache: CacheClient):
        self.cache = cache
```

### ❌ INCORRECT: Tight Coupling
```python
class UserService:
    def __init__(self, host: str, port: int):
        self.config = GlideClientConfiguration([NodeAddress(host, port)])
        self.client = await GlideClient.create(self.config)
```

**Why:** Tight coupling makes testing difficult and prevents swapping implementations.

---

### ✅ CORRECT: Explicit Imports
```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress
```

### ❌ INCORRECT: Wildcard Imports
```python
from glide import *  # Namespace pollution
```

**Why:** Wildcard imports pollute namespace, cause name collisions, and break static analysis.

**See also:** [Anti-Pattern Demonstrations](ANTI_PATTERNS.md) for working examples proving these patterns.

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
- [ ] **Use status returns instead of exceptions for control flow**
- [ ] **Use module-level functions instead of static-only classes**
- [ ] **Use Protocols for abstraction, not concrete classes**
- [ ] **Use explicit imports, never wildcard imports**


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
- See SKILL.md for retry strategy decision matrix

### Retry Strategies (Cluster Only)

**Retry on server errors:**
```python
from glide_shared.commands.batch_options import BatchRetryStrategy

options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=True,
        retry_connection_error=False,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**Retry on connection errors:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=False,
        retry_connection_error=True,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**Retry on both:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=True,
        retry_connection_error=True,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**No retries:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=False,
        retry_connection_error=False,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

---

# Performance Optimization

Config templates: [`performance/config-templates/python-config.py`](../performance/config-templates/python-config.py)

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

```python
# ❌ Inefficient — must fetch/parse entire object
await client.set("user:123", json.dumps(user))
data = json.loads(await client.get("user:123"))

# ✅ Efficient — fetch only needed fields
await client.hset("user:123", {"name": "John", "email": "john@example.com", "age": "30"})
name = await client.hget("user:123", "name")
```

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

Server-side config: [`performance/server-configuration-guide.md`](../performance/server-configuration-guide.md)
