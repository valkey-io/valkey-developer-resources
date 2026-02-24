# Python GLIDE Performance Patterns

Language-specific optimization patterns for Python implementations using `valkey-glide` (async and sync clients).

## Quick Wins

### 1. Client Reuse Pattern

**❌ Anti-Pattern: Per-Request Client Creation**
```python
# NEVER do this - creates new connection per request
async def handle_request(request):
    client = await GlideClient.create(
        GlideClientConfiguration(addresses=[NodeAddress("localhost", 6379)])
    )
    data = await client.get("key")
    await client.close()
    return data
```

**✅ Correct: Singleton Client (Async)**
```python
from glide import GlideClient, GlideClientConfiguration, NodeAddress

# Create once at application startup
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
    client_name="my-app-client",
)

client = await GlideClient.create(config)

# Reuse in request handlers
async def handle_request(request):
    data = await client.get("key")
    return data

# Graceful shutdown
async def shutdown():
    await client.close()
```

**✅ Correct: Singleton Client (Sync)**
```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

# Create once at application startup
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
    client_name="my-app-client",
)

client = GlideClient.create(config)

# Reuse in request handlers
def handle_request(request):
    data = client.get("key")
    return data

# Graceful shutdown
def shutdown():
    client.close()
```

### 2. Request Timeout Configuration

**Production-Ready Configuration:**

For a complete production-ready configuration example with all recommended settings (timeouts, retry strategies, throughput tuning, AZ affinity), see `assets/config-templates/python-config.py`.

**✅ Always Configure Timeouts**
```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,  # milliseconds
)
```

**Timeout Guidelines**:
- Real-time apps (sub-10ms): 20-50ms
- Web APIs: 200-500ms
- Background jobs: 1000-5000ms

## Batching Patterns

### Pipeline (Non-Atomic) - Async

**❌ Sequential Operations**
```python
# 3 network roundtrips (~15ms)
user1 = await client.get("user:1")
user2 = await client.get("user:2")
user3 = await client.get("user:3")
```

**✅ Pipeline Batch**
```python
from glide import Batch

# 1 network roundtrip (~5ms)
batch = Batch(is_atomic=False)  # False = pipeline (non-atomic)
batch.get("user:1")
batch.get("user:2")
batch.get("user:3")
results = await client.exec(batch, raise_on_error=True)
user1, user2, user3 = results
```

### Transaction (Atomic) - Async

**✅ Atomic Operations**
```python
transaction = Batch(is_atomic=True)  # True = transaction (atomic)
transaction.set("balance:user:123", "100")
transaction.incr("transaction:count")
transaction.set("last_update", str(int(time.time())))

results = await client.exec(transaction, raise_on_error=True)
# All commands succeed or all fail
```

### Batch Size Guidelines

```python
# Optimal: 10-100 commands
batch = Batch(is_atomic=False)
for i in range(50):
    batch.get(f"key:{i}")
results = await client.exec(batch, raise_on_error=True)

# Avoid: >1000 commands (split into smaller batches)
keys = [f"key:{i}" for i in range(5000)]
batch_size = 100

for i in range(0, len(keys), batch_size):
    batch = Batch(is_atomic=False)
    for key in keys[i:i + batch_size]:
        batch.get(key)
    results = await client.exec(batch, raise_on_error=True)
    # Process results
```

## Concurrent Operations (Async)

### asyncio.gather() Pattern

**✅ Concurrent Independent Operations**
```python
import asyncio

# Execute concurrently (wall-clock time = max latency)
user, posts, comments = await asyncio.gather(
    client.get("user:123"),
    client.lrange("posts:123", 0, -1),
    client.lrange("comments:123", 0, -1),
)
```

**Note**: Batching is usually more efficient than asyncio.gather() for multiple operations.

### asyncio.gather() with Error Handling

**✅ Handle Partial Failures**
```python
results = await asyncio.gather(
    client.get("key1"),
    client.get("key2"),
    client.get("key3"),
    return_exceptions=True,
)

for i, result in enumerate(results):
    if isinstance(result, Exception):
        print(f"key{i + 1} failed: {result}")
    else:
        print(f"key{i + 1}: {result}")
```

## Cluster Patterns

### Hash Tags for Co-location

**❌ Keys on Different Slots**
```python
# Multiple roundtrips to different shards
await client.mget(["user:123:name", "user:123:email", "user:123:age"])
```

**✅ Hash Tags for Same Slot**
```python
# Single roundtrip - all keys on same shard
await client.mget(["{user:123}:name", "{user:123}:email", "{user:123}:age"])

# Set related data
await client.mset({
    "{user:123}:name": "John",
    "{user:123}:email": "john@example.com",
    "{user:123}:preferences": json.dumps({"theme": "dark"}),
})
```

### Cluster Scan

**✅ Iterate All Keys in Cluster**
```python
from glide import ClusterScanCursor

cursor = ClusterScanCursor()
all_keys = []

while True:
    cursor, keys = await cluster_client.scan(
        cursor, 
        match="user:*", 
        count=100
    )
    all_keys.extend(keys)
    if cursor.is_finished():
        break

print(f"Found {len(all_keys)} keys")
```

## AZ Affinity Configuration

**✅ Enable for Read-Heavy Workloads**
```python
from glide import GlideClusterClient, GlideClusterClientConfiguration, NodeAddress, ReadFrom

config = GlideClusterClientConfiguration(
    addresses=[NodeAddress("cluster.endpoint.cache.amazonaws.com", 6379)],
    read_from=ReadFrom.AZ_AFFINITY,
    client_az="us-east-1a",  # Your application's AZ
    request_timeout=500,
)

client = await GlideClusterClient.create(config)
```

**Requirements**:
- Valkey 8.0+ or ElastiCache for Valkey 7.2+
- Cluster mode with replicas
- Read-heavy workload (>80% reads)

## Error Handling

### Typed Error Handling (Async)

**✅ Handle Specific Error Types**
```python
from glide import ConnectionError, TimeoutError, RequestError

try:
    result = await client.get("key")
except TimeoutError as e:
    # Retry with exponential backoff
    print(f"Request timed out: {e}")
except ConnectionError as e:
    # Circuit breaker pattern
    print(f"Connection failed: {e}")
except RequestError as e:
    # Server error - check command syntax
    print(f"Request error: {e}")
except Exception as e:
    # Unknown error
    print(f"Unexpected error: {e}")
```

### Retry Strategy Configuration

**✅ Configure Reconnect Strategy**
```python
from glide import BackoffStrategy

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    reconnect_strategy=BackoffStrategy(
        num_of_retries=10,
        factor=500,        # Base delay in ms
        exponent_base=2,   # Exponential backoff (500ms, 1s, 2s, 4s, ...)
    ),
    request_timeout=500,
)
```

## Advanced Patterns

### Serverless/Lambda Optimization

**✅ Lazy Connection**
```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    lazy_connect=True,  # Don't connect until first command
    request_timeout=500,
)

client = await GlideClient.create(config)

# Connection established on first command
data = await client.get("key")
```

### Blocking Commands

**✅ Dedicated Client for Blocking Operations**
```python
# Separate client for blocking commands
blocking_config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=30000,  # 30 seconds
    client_name="queue-worker",
)
blocking_client = await GlideClient.create(blocking_config)

# Use for BLPOP, BRPOP, etc.
item = await blocking_client.blpop(["queue"], 30)

# Regular client for other operations
regular_config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
    client_name="app-client",
)
regular_client = await GlideClient.create(regular_config)
```

### Throughput Tuning

GLIDE uses a single multiplexed connection, not a traditional connection pool. Tune throughput via `inflight_requests_limit`.

**✅ High-Throughput Configuration**
```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    inflight_requests_limit=2000,  # Default: 1000
    request_timeout=500,
)
```

## Data Structures

### Hash vs JSON

**❌ Large JSON Strings**
```python
import json

# Inefficient - must fetch/parse entire object
user = {"name": "John", "email": "john@example.com", "age": 30}
await client.set("user:123", json.dumps(user))

data = await client.get("user:123")
parsed = json.loads(data)
print(parsed["name"])  # Had to fetch everything
```

**✅ Hash Data Structure**
```python
# Efficient - fetch only needed fields
await client.hset("user:123", {
    "name": "John",
    "email": "john@example.com",
    "age": "30",
})

# Retrieve single field
name = await client.hget("user:123", "name")

# Retrieve multiple fields
name, email = await client.hmget("user:123", ["name", "email"])

# Retrieve all fields
all_fields = await client.hgetall("user:123")
```

## Monitoring

### OpenTelemetry Integration

**✅ Enable Tracing**
```python
from glide import (
    OpenTelemetry,
    OpenTelemetryConfig,
    OpenTelemetryTracesConfig,
    OpenTelemetryMetricsConfig,
)

# Initialize once at application startup
OpenTelemetry.init(OpenTelemetryConfig(
    traces=OpenTelemetryTracesConfig(
        endpoint="http://localhost:4318/v1/traces",
        sample_percentage=1,  # 1% sampling for production
    ),
    metrics=OpenTelemetryMetricsConfig(
        endpoint="http://localhost:4318/v1/metrics",
    ),
))
```

### Logging Configuration

**✅ Production Logging**
```python
from glide import Logger

# Production: minimal logging
Logger.set_logger_config("warn", "glide.log")

# Development: verbose logging
Logger.set_logger_config("info")

# Maximum performance: errors only
Logger.set_logger_config("error")
```

## Async vs Sync Client

### When to Use Async

**✅ Use Async for:**
- Web frameworks (FastAPI, aiohttp, Sanic)
- High-concurrency applications
- I/O-bound workloads
- Modern async Python codebases

```python
from glide import GlideClient, GlideClientConfiguration

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
)

client = await GlideClient.create(config)
result = await client.get("key")
```

### When to Use Sync

**✅ Use Sync for:**
- Legacy codebases
- Simple scripts
- Synchronous frameworks (Flask, Django without async)
- CPU-bound workloads

```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=500,
)

client = GlideClient.create(config)
result = client.get("key")
```

## Context Manager Pattern

### Async Context Manager

**✅ Automatic Cleanup**
```python
async with await GlideClient.create(config) as client:
    result = await client.get("key")
    # Client automatically closed on exit
```

### Sync Context Manager

**✅ Automatic Cleanup**
```python
with GlideClient.create(config) as client:
    result = client.get("key")
    # Client automatically closed on exit
```

## SCAN vs Valkey-Search

### SCAN for Key Discovery (Scalability Concern)

**❌ SCAN Loop for Pattern-Based Key Lookup**
```python
# O(N) full keyspace iteration — degrades as dataset grows
matched = []
cursor = "0"
while True:
    cursor, keys = await client.scan(cursor, match=pattern, count=100)
    matched.extend(keys)
    if cursor == "0":
        break

# Then individually fetching each matched key compounds the problem
for key in matched:
    val = await client.get(key)
    # ...
```

**✅ Valkey-Search Index for Efficient Queries**
```python
# Create index once at startup
await client.ft_create(
    "idx:content",
    prefix=["content:"],
    schema=[
        {"name": "title", "type": "TEXT"},
        {"name": "tags", "type": "TAG"},
    ],
)

# O(K) where K = result count, independent of total keyspace size
results = await client.ft_search("idx:content", f"@title:{search_term}")
```

**Note**: SCAN is appropriate for one-time migrations or admin tasks. For application-level search or filtering, Valkey-Search (`FT.*`) scales independently of keyspace size.

## Common Pitfalls

### 1. Mixing Async and Sync

**❌ Wrong: Calling async from sync**
```python
def sync_function():
    result = await client.get("key")  # SyntaxError!
```

**✅ Correct: Use sync client in sync code**
```python
def sync_function():
    from glide_sync import GlideClient
    sync_client = GlideClient.create(config)
    result = sync_client.get("key")
```

### 2. Not Awaiting Async Operations

**❌ Missing await**
```python
result = client.get("key")  # Returns coroutine, not value!
print(result)  # Prints <coroutine object>
```

**✅ Proper await**
```python
result = await client.get("key")
print(result)  # Prints actual value
```

### 3. Creating Client in Loop

**❌ Client per iteration**
```python
for item in items:
    client = await GlideClient.create(config)  # NEVER!
    await client.set(item.key, item.value)
    await client.close()
```

**✅ Reuse client**
```python
client = await GlideClient.create(config)
for item in items:
    await client.set(item.key, item.value)
await client.close()
```

### 4. Blocking Operations on Shared Client

**❌ Blocking on shared client**
```python
client = await GlideClient.create(config)
await client.blpop(["queue"], 30)  # Blocks all other operations!
await client.get("key")  # Will timeout
```

**✅ Separate clients**
```python
regular_client = await GlideClient.create(config)
blocking_client = await GlideClient.create(config)

await blocking_client.blpop(["queue"], 30)
await regular_client.get("key")  # Works fine
```

## Type Hints Best Practices

### Type-Safe Configuration

**✅ Use Type Hints**
```python
from typing import Optional, List, Dict
from glide import GlideClient, GlideClientConfiguration, NodeAddress

async def create_client(
    host: str,
    port: int,
    timeout: int = 500
) -> GlideClient:
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        request_timeout=timeout,
    )
    return await GlideClient.create(config)

async def get_user(client: GlideClient, user_id: str) -> Optional[str]:
    return await client.get(f"user:{user_id}")
```

## Performance Checklist

- [ ] Client created once at startup, not per request
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching used for bulk operations (10-100 commands)
- [ ] asyncio.gather() for concurrent independent operations (async)
- [ ] Hash tags for related keys in cluster
- [ ] AZ affinity enabled for read-heavy workloads
- [ ] Error handling with typed exceptions
- [ ] Connection backoff configured
- [ ] Dedicated client for blocking commands
- [ ] Hash data structures for structured data
- [ ] OpenTelemetry enabled for monitoring
- [ ] Logging set to warn/error for production
- [ ] lazy_connect for serverless/Lambda
- [ ] Async client for async frameworks, sync for sync frameworks
- [ ] Context managers for automatic cleanup
