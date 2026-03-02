# C# GLIDE Skill

> **Status:** Preview - C# GLIDE is available on NuGet but still has features being implemented before GA. See [official documentation](https://valkey.io/valkey-glide/) for latest updates.

## Package Selection

```csharp
// ✅ Correct
using Valkey.Glide;
using Valkey.Glide.Pipeline;
using static Valkey.Glide.ConnectionConfiguration;

// ❌ Wrong
using StackExchange.Redis;  // Different library (though Valkey.Glide provides compatibility layer)
```

**Why:** Valkey.Glide is the official high-performance client built on Rust core with native async/await support.

**Note:** Current NuGet version is 0.9.0. Features like IAM authentication and insecure TLS mode require version 2.0+ (not yet released).

## Client Creation

### Standalone Client
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithRequestTimeout(TimeSpan.FromSeconds(10))
    .Build();

await using var client = await GlideClient.CreateClient(config);
```

**Key Points:**
- Use `await using` for automatic async disposal
- `CreateClient` is async, returns `Task<GlideClient>`
- Set explicit timeout to avoid connection issues

### Cluster Client
```csharp
var config = new ClusterClientConfigurationBuilder()
    .WithAddress("localhost", 7000)
    .WithAddress("localhost", 7001)
    .WithAddress("localhost", 7002)
    .Build();

await using var client = await GlideClusterClient.CreateClient(config);
```

### With Authentication and TLS
```csharp
// Password authentication with TLS
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithAuthentication("username", "password")
    .WithTls()
    .Build();

// IAM authentication for AWS ElastiCache (requires v2.0+)
var iamAuthConfig = new IamAuthConfig("cluster-name", ServiceType.ElastiCache, "us-east-1");
var config = new ClusterClientConfigurationBuilder()
    .WithAddress("host", 6379)
    .WithAuthentication("username", iamAuthConfig)
    .WithTls(true)
    .Build();
```

**Note:** IAM authentication and insecure TLS mode require Valkey.Glide 2.0+. Current NuGet version (0.9.0) supports password authentication and TLS with CA-signed certificates.

## Async Patterns

All operations return `Task<T>`. Use async/await:

```csharp
async Task Example()
{
    var value = await client.StringGetAsync("key");
    await client.StringSetAsync("key", "value");
}
```

**Key Point:** Unlike Java's `CompletableFuture.get()`, C# uses `await` - no blocking calls needed.

## Batch/Pipeline Operations

### Standalone Batch
```csharp
// Atomic batch (transaction)
var batch = new Batch(atomic: true);
batch.StringSet("key1", "value1");
batch.StringGet("key1");
var results = await client.Exec(batch, raiseOnError: true);

// Non-atomic pipeline
var pipeline = new Batch(atomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
var results = await client.Exec(pipeline, raiseOnError: true);
```

### Cluster Batch
```csharp
// Atomic batch (requires same slot)
var batch = new ClusterBatch(atomic: true);
batch.StringSet("{user}:1", "Alice");
batch.StringGet("{user}:1");
var results = await client.Exec(batch, raiseOnError: true);

// Non-atomic pipeline (can span slots)
var pipeline = new ClusterBatch(atomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
var results = await client.Exec(pipeline, raiseOnError: true);
```

**Key Points:**
- Use named parameter `atomic:` for clarity
- Results are `object?[]?` - nullable array of nullable objects
- Cluster atomic batches require same hash slot

## Cluster Operations

### Hash Tags for Slot Control
```csharp
// Use {tag} to ensure keys map to same slot
await client.StringSetAsync("{user}:1:name", "Alice");
await client.StringSetAsync("{user}:1:email", "alice@example.com");

// Atomic batch requires same slot
var batch = new ClusterBatch(isAtomic: true);
batch.StringSetAsync("{order}:100:status", "pending");
batch.StringSet("{order}:100:total", "99.99");
await client.Exec(batch, raiseOnError: true);
```

### CROSSSLOT Error
```csharp
// ❌ This fails - keys in different slots
var batch = new ClusterBatch(atomic: true);
batch.StringSet("key1", "value1");  // Slot A
batch.StringSet("key2", "value2");  // Slot B
await client.Exec(batch, raiseOnError: true);  // Throws ValkeyException: CROSSSLOT

// ✅ This works - non-atomic can span slots
var pipeline = new ClusterBatch(atomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
await client.Exec(pipeline, raiseOnError: true);
```

## Error Handling

```csharp
try
{
    await client.StringSetAsync("key", "value");
    var result = await client.StringGetAsync("key");
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

**Key Point:** Direct exception access (no wrapping like Java's `ExecutionException`)

## PubSub Operations

### Configuration-Time Subscriptions
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithPubSubReconciliationInterval(TimeSpan.FromSeconds(1))
    .WithPubSubSubscriptionConfig(new StandalonePubSubSubscriptionConfig()
        .WithChannel("alerts")
        .WithPattern("log:*")
        .WithCallback((msg, ctx) => {
            Console.WriteLine($"Received: {msg.Message}");
        }))
    .Build();

await using var client = await GlideClient.CreateClient(config);
```

### Dynamic Subscribe/Unsubscribe
```csharp
await client.PSubscribeAsync("news*");
await client.UnsubscribeAsync("alerts");
```

### Publishing
```csharp
await client.PublishAsync("channel", "message");
```

## StackExchange.Redis Compatibility

Valkey.Glide provides compatibility layer:

```csharp
// Compatible with StackExchange.Redis API
var connection = await ConnectionMultiplexer.ConnectAsync("localhost:6379");
var db = connection.GetDatabase();

await db.StringSetAsync("key", "value");
var value = await db.StringGetAsync("key");
```

**Key Point:** Eases migration from StackExchange.Redis to Valkey.Glide

## Configuration Options

### Database Selection (Standalone Only)
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithDataBaseId(1)
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

### Client Name
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithClientName("my-app")
    .Build();
```

### Protocol Version
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithProtocolVersion(ConnectionConfiguration.Protocol.RESP2)
    .Build();
```

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
    await client.StringSetAsync("test:key", "value");
}
finally
{
    await client.Del(["test:key"]);
}
```

## Common Pitfalls

### ❌ Forgetting await
```csharp
// Wrong - returns Task, not value
var value = client.StringGetAsync("key");  // Task<ValkeyValue>

// Correct
var value = await client.StringGetAsync("key");  // ValkeyValue
```

### ❌ Not Using await using
```csharp
// Wrong - client not disposed
var client = await GlideClient.CreateClient(config);
// ... operations ...
// Client never disposed!

// Correct
await using var client = await GlideClient.CreateClient(config);
// ... operations ...
// Client automatically disposed
```

### ❌ Synchronous Blocking
```csharp
// Wrong - can cause deadlocks
var value = client.StringGetAsync("key").Result;

// Correct
var value = await client.StringGetAsync("key");
```

### ❌ Wrong Naming Convention
```csharp
// Wrong - C# uses PascalCase
await client.stringSetAsync("key", "value");

// Correct
await client.StringSetAsync("key", "value");
```

### ❌ Cluster Atomic Batch Across Slots
```csharp
// Wrong - CROSSSLOT error
var batch = new ClusterBatch(atomic: true);
batch.StringSet("key1", "value1");  // Different slots
batch.StringSet("key2", "value2");
await client.Exec(batch, raiseOnError: true);  // Throws

// Correct - use hash tags
var batch = new ClusterBatch(atomic: true);
batch.StringSet("{user}:1", "value1");  // Same slot
batch.StringSet("{user}:2", "value2");
await client.Exec(batch, raiseOnError: true);  // Success
```

## Summary Checklist

- [ ] Install `Valkey.Glide` NuGet package
- [ ] Use `await using` for client disposal
- [ ] Set explicit `RequestTimeout` in configuration
- [ ] Use `await` for all async operations (never `.Result` or `.Wait()`)
- [ ] Use `Batch(atomic: true)` for transactions, `Batch(atomic: false)` for pipelines
- [ ] Use hash tags `{tag}` for cluster atomic batches
- [ ] Handle specific exceptions: `ConnectionException`, `TimeoutException`, `ValkeyException`
- [ ] Configure PubSub subscriptions at connection time
- [ ] Use `ClusterBatch` for cluster mode, `Batch` for standalone
- [ ] Enable nullable reference types for better null safety

## Language Comparison

| Feature | Node.js | Java | C# |
|---------|---------|------|-----|
| Package | `@valkey/valkey-glide` | `io.valkey:valkey-glide` | `Valkey.Glide` |
| Client creation | `await GlideClient.createClient()` | `GlideClient.createClient().get()` | `await GlideClient.CreateClient()` |
| Async model | Promises | CompletableFuture | Task<T> |
| Resource cleanup | `client.close()` | try-with-resources | `await using` |
| Naming | camelCase | camelCase | PascalCase |
| Exception handling | Direct | Wrapped in ExecutionException | Direct |
| Batch constructor | `new Batch(false)` | `new Batch(false)` | `new Batch(isAtomic: false)` |
| Binary data | `Buffer` | `GlideString` | `GlideString` / `byte[]` |

## Additional Resources

- [Official Documentation](https://valkey.io/valkey-glide/)
- [GitHub Repository](https://github.com/valkey-io/valkey-glide-csharp)
- [NuGet Package](https://www.nuget.org/packages/Valkey.Glide)
- [General Concepts](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts)
