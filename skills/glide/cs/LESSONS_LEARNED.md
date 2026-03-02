# C# GLIDE Lessons Learned

## Import Patterns

### Core Imports
```csharp
using Valkey.Glide;
using Valkey.Glide.Pipeline;
using static Valkey.Glide.ConnectionConfiguration;
```

**Key Finding:** Use `static` import for `ConnectionConfiguration` to access builders directly

### Command Interfaces
```csharp
using Valkey.Glide.Commands;
using Valkey.Glide.Commands.Options;
```

**Key Finding:** Command interfaces are in separate namespace, but typically not needed for basic usage

## Client Creation

### Standalone Client
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithRequestTimeout(TimeSpan.FromSeconds(10))
    .Build();

await using var client = await GlideClient.CreateClient(config);
```

**Key Findings:**
- Builder pattern with fluent API
- `await using` for automatic async disposal
- `CreateClient` is async, returns `Task<GlideClient>`
- Use `TimeSpan` for timeout configuration

### Cluster Client
```csharp
var config = new ClusterClientConfigurationBuilder()
    .WithAddress("localhost", 7000)
    .WithAddress("localhost", 7001)
    .WithAddress("localhost", 7002)
    .Build();

await using var client = await GlideClusterClient.CreateClient(config);
```

**Key Finding:** Multiple addresses added with chained `.WithAddress()` calls

## Batch/Pipeline API

### Constructor Pattern
```csharp
var pipeline = new Batch(atomic: false);     // Non-atomic (pipeline)
var transaction = new Batch(atomic: true);   // Atomic (transaction)
```

**Key Finding:** Named parameter `atomic:` for clarity (C# best practice)

### Execution
```csharp
var results = await client.Exec(batch, raiseOnError: true);
// results is object?[]?
```

**Key Findings:**
- Returns `Task<object?[]?>` - nullable array of nullable objects
- `raiseOnError` parameter controls exception behavior
- Results need casting for specific types

## Error Handling

### Exception Types
```csharp
using Valkey.Glide;

try
{
    await client.StringGetAsync("key");
}
catch (ConnectionException ex)
{
    Console.WriteLine($"Connection error: {ex.Message}");
}
catch (TimeoutException ex)
{
    Console.WriteLine($"Timeout: {ex.Message}");
}
catch (ValkeyException ex)
{
    Console.WriteLine($"Valkey error: {ex.Message}");
}
```

**Key Findings:**
- Specific exception types in `Valkey.Glide` namespace
- No wrapping like Java's `ExecutionException` - direct exception access
- Standard C# exception hierarchy

## Type System

### GlideString for Binary Data
```csharp
using gs = Valkey.Glide.GlideString;

// Binary-safe operations
gs binaryKey = new gs(new byte[] { 0x01, 0x02, 0x03 });
await client.StringSetAsync(binaryKey, "value");
```

**Key Finding:** `GlideString` (alias `gs`) for binary-safe keys/values

### ValkeyValue for Responses
```csharp
ValkeyValue value = await client.StringGetAsync("key");
string str = value.ToString();
```

**Key Finding:** `ValkeyValue` is response type, converts to string/bytes

### Nullable Reference Types
```csharp
#nullable enable

ValkeyValue? value = await client.StringGetAsync("nonexistent");
if (value != null)
{
    Console.WriteLine(value.ToString());
}
```

**Key Finding:** C# 8.0+ nullable reference types enabled in project

## Async Patterns

### Task-Based Async
```csharp
// All operations return Task<T>
Task<ValkeyValue> task = client.StringGetAsync("key");

// Await for result
ValkeyValue value = await task;

// Multiple concurrent operations
var task1 = client.StringGetAsync("key1");
var task2 = client.StringGetAsync("key2");
await Task.WhenAll(task1, task2);
```

**Key Finding:** C# uses `Task<T>` and `async/await`, simpler than Java's `CompletableFuture`

## Node.js vs C# Comparison

| Aspect | Node.js | C# |
|--------|---------|-----|
| Client creation | `await GlideClient.createClient(config)` | `await GlideClient.CreateClient(config)` |
| Batch constructor | `new Batch(false)` | `new Batch(atomic: false)` |
| Batch execution | `await client.exec(batch, true)` | `await client.Exec(batch, raiseOnError: true)` |
| Naming convention | camelCase | PascalCase (methods) |
| Exception handling | Direct exception | Direct exception |
| Imports | `require()` or `import` | `using` statements |
| Async model | Promises | Task<T> |
| Resource cleanup | `client.close()` | `await using` |

## Java vs C# Comparison

| Aspect | Java | C# |
|--------|------|-----|
| Client creation | `GlideClient.createClient(config).get()` | `await GlideClient.CreateClient(config)` |
| Batch constructor | `new Batch(false)` | `new Batch(atomic: false)` |
| Exception handling | Wrapped in `ExecutionException` | Direct exception |
| Async model | `CompletableFuture` | `Task<T>` |
| Resource cleanup | `try-with-resources` | `await using` |
| Naming | camelCase | PascalCase |

## Common Pitfalls

### 1. Forgetting await
**Problem:** Operations return `Task<T>`, not values
**Solution:** Always `await` async operations

### 2. Not Using await using
**Problem:** Client not disposed properly
**Solution:** Use `await using var client = ...` for automatic disposal

### 3. Wrong Naming Convention
**Problem:** Using camelCase for method names
**Solution:** C# uses PascalCase: `StringSetAsync`, not `stringSetAsync`

### 4. Synchronous Blocking
**Problem:** Using `.Result` or `.Wait()` can cause deadlocks
**Solution:** Use `await` throughout async call chain

### 5. Null Reference Warnings
**Problem:** Nullable reference type warnings
**Solution:** Enable nullable context and handle null cases

## Cluster Operations

### Client Types
```csharp
// Standalone
using Valkey.Glide;
var client = await GlideClient.CreateClient(config);

// Cluster
using Valkey.Glide;
var client = await GlideClusterClient.CreateClient(config);
```

### Hash Tags for Same Slot
```csharp
// Cluster mode: use hash tags for same slot
var batch = new ClusterBatch(atomic: true);
batch.StringSet("{user}:1", "Alice");  // Same slot
batch.StringSet("{user}:2", "Bob");    // Same slot
await client.Exec(batch, raiseOnError: true);
```

### Multi-Slot Operations
```csharp
// Non-atomic batch can span slots
var pipeline = new ClusterBatch(atomic: false);
pipeline.StringSet("key1", "value1");  // Slot A
pipeline.StringSet("key2", "value2");  // Slot B
await client.Exec(pipeline, raiseOnError: true);  // Success
```

**Key Finding:** Same CROSSSLOT constraints as Java - atomic batches require same slot, non-atomic can span slots

## Vector Search Patterns

### Using CustomCommand
```csharp
// C# GLIDE doesn't have FT module yet - use CustomCommand
await client.CustomCommand([
    "FT.CREATE", "idx",
    "ON", "HASH",
    "PREFIX", "1", "doc:",
    "SCHEMA",
    "embedding", "VECTOR", "HNSW", "6",
    "TYPE", "FLOAT32",
    "DIM", "3",
    "DISTANCE_METRIC", "L2"
]);
```

**Key Finding:** No `GlideFt` class yet - use `CustomCommand` for FT operations

### Binary Vector Encoding
```csharp
static byte[] ToBytes(float[] vector)
{
    var bytes = new byte[vector.Length * sizeof(float)];
    Buffer.BlockCopy(vector, 0, bytes, 0, bytes.Length);
    return bytes;
}

var vector = ToBytes([1.0f, 2.0f, 3.0f]);
await client.HashSetAsync("doc:1", new Dictionary<string, GlideString>
{
    ["embedding"] = vector
});
```

**Key Finding:** Use `Buffer.BlockCopy` for efficient float-to-byte conversion

### Vector Search
```csharp
var queryVector = ToBytes([1.5f, 2.5f, 3.5f]);
var results = await client.CustomCommand([
    "FT.SEARCH", "idx",
    "*=>[KNN 2 @embedding $vec]",
    "PARAMS", "2", "vec", queryVector,
    "DIALECT", "2"
]);
```

**Key Finding:** CustomCommand accepts `GlideString[]` for binary data

## StackExchange.Redis Compatibility

### ConnectionMultiplexer Pattern
```csharp
var connection = await ConnectionMultiplexer.ConnectAsync("localhost:6379");
var db = connection.GetDatabase();

await db.StringSetAsync("key", "value");
var value = await db.StringGetAsync("key");
```

**Key Finding:** C# GLIDE provides `ConnectionMultiplexer` and `IDatabase` interfaces for StackExchange.Redis compatibility

### Migration Path
```csharp
// Old: StackExchange.Redis
using StackExchange.Redis;
var redis = ConnectionMultiplexer.Connect("localhost");

// New: Valkey.Glide (compatible API)
using Valkey.Glide;
var connection = await ConnectionMultiplexer.ConnectAsync("localhost:6379");
```

**Key Finding:** Drop-in replacement for many StackExchange.Redis use cases

## Configuration Options

### Authentication
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithAuthentication("username", "password")
    .Build();
```

### TLS
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithTls()  // or WithTls(true)
    .Build();
```

### IAM Authentication (AWS ElastiCache)
```csharp
var iamAuthConfig = new IamAuthConfig("cluster-name", ServiceType.ElastiCache, "us-east-1");
var config = new ClusterClientConfigurationBuilder()
    .WithAddress("host", 6379)
    .WithAuthentication("username", iamAuthConfig)
    .WithTls(true)
    .Build();
```

**Key Finding:** IAM support requires Valkey.Glide 2.0+ (not available in current NuGet v0.9.0)

### Database Selection (Standalone Only)
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithDataBaseId(1)  // Select database 1
    .Build();
```

### Retry Strategy
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithConnectionRetryStrategy(
        numOfRetries: 5,
        factor: 100,
        exponentBase: 2
    )
    .Build();
```

## PubSub Patterns

### Configuration-Time Subscriptions
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithPubSubSubscriptionConfig(new StandalonePubSubSubscriptionConfig()
        .WithChannel("alerts")
        .WithPattern("log:*")
        .WithCallback((msg, ctx) => {
            Console.WriteLine($"Received: {msg.Message}");
        }))
    .Build();

await using var client = await GlideClient.CreateClient(config);
```

**Key Finding:** PubSub subscriptions configured at connection time, not after

### Dynamic Subscribe/Unsubscribe
```csharp
await client.PSubscribeAsync("news*");
await client.UnsubscribeAsync("alerts");
```

### Publishing
```csharp
await client.PublishAsync("channel", "message");
```

**Key Finding:** PubSub auto-reconnection built-in, resubscribes on topology changes

## Testing Patterns

### Test Configuration
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithClientName("test-client")
    .WithRequestTimeout(TimeSpan.FromSeconds(2))
    .Build();
```

### Cleanup Pattern
```csharp
await using var client = await GlideClient.CreateClient(config);
try
{
    // Test operations
}
finally
{
    await client.Del(["test:key1", "test:key2"]);
}
```

**Key Finding:** `await using` ensures cleanup even on exceptions

## Performance Considerations

### Connection Pooling
**Key Finding:** Built-in connection pooling, no manual management needed

### Pipeline Batching
```csharp
// Batch multiple operations for better throughput
var pipeline = new Batch(atomic: false);
for (int i = 0; i < 1000; i++)
{
    pipeline.StringSet($"key:{i}", $"value:{i}");
}
await client.Exec(pipeline, raiseOnError: true);
```

### Concurrent Operations
```csharp
var tasks = Enumerable.Range(0, 100)
    .Select(i => client.StringSetAsync($"key:{i}", $"value:{i}"));
await Task.WhenAll(tasks);
```

**Key Finding:** C# async/await enables efficient concurrent operations

## Next Steps

- [x] Basic operations POC
- [x] Batch/pipeline POC
- [x] Cluster operations POC
- [x] Vector search POC (using CustomCommand)
- [ ] PubSub POC (when testing environment available)
- [ ] Anti-pattern analysis (when C# patterns emerge)
- [ ] Performance benchmarking
