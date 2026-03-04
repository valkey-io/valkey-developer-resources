# C# GLIDE Skill

## Code Snippets
- [csharp-config.cs](snippets/csharp-config.cs) - Optimized templates for production web applications

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
var batch = new Batch(isAtomic: true);
batch.StringSet("key1", "value1");
batch.StringGet("key1");
var results = await client.Exec(batch, raiseOnError: true);

// Non-atomic pipeline
var pipeline = new Batch(isAtomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
var results = await client.Exec(pipeline, raiseOnError: true);
```

### Cluster Batch
```csharp
// Atomic batch (requires same slot)
var batch = new ClusterBatch(isAtomic: true);
batch.StringSet("{user}:1", "Alice");
batch.StringGet("{user}:1");
var results = await client.Exec(batch, raiseOnError: true);

// Non-atomic pipeline (can span slots)
var pipeline = new ClusterBatch(isAtomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
var results = await client.Exec(pipeline, raiseOnError: true);
```

**Key Points:**
- Use named parameter `isAtomic:` for clarity
- Results are `object?[]?` - nullable array of nullable objects
- Cluster atomic batches require same hash slot

### Retry Strategies

**Note:** C# GLIDE v0.9.0 does not support batch retry strategies. This feature may be added in future versions.

For production resilience, implement retry logic at the application level:

```csharp
async Task<T> ExecuteWithRetryAsync<T>(
    Func<Task<T>> operation,
    int maxRetries = 3,
    int baseDelayMs = 100)
{
    for (int attempt = 0; attempt < maxRetries; attempt++)
    {
        try
        {
            return await operation();
        }
        catch (Exception ex) when (attempt < maxRetries - 1)
        {
            await Task.Delay(baseDelayMs * (int)Math.Pow(2, attempt));
        }
    }
    throw new InvalidOperationException("Max retries exceeded");
}

// Usage
var results = await ExecuteWithRetryAsync(async () =>
{
    var batch = new ClusterBatch(isAtomic: false);
    batch.StringSetAsync("key", "value");
    return await client.Exec(batch, raiseOnError: true);
});
```

See SKILL.md for retry strategy decision matrix (applicable when feature becomes available).

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
var batch = new ClusterBatch(isAtomic: true);
batch.StringSet("key1", "value1");  // Slot A
batch.StringSet("key2", "value2");  // Slot B
await client.Exec(batch, raiseOnError: true);  // Throws RequestException: CROSSSLOT

// ✅ This works - non-atomic can span slots
var pipeline = new ClusterBatch(isAtomic: false);
pipeline.StringSet("key1", "value1");
pipeline.StringSet("key2", "value2");
await client.Exec(pipeline, raiseOnError: true);
```

## Error Handling

```csharp
using static Valkey.Glide.Errors;
// Note: alias Valkey.Glide.Errors.TimeoutException to avoid conflict with System.TimeoutException
using TimeoutException = Valkey.Glide.Errors.TimeoutException;

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
catch (RequestException ex)
{
    Console.WriteLine($"Request error: {ex.Message}");
}
```

**Key Point:** Direct exception access (no wrapping like Java's `ExecutionException`). Exceptions are nested in `Valkey.Glide.Errors` — use `using static Valkey.Glide.Errors;` for convenience.

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
        numberOfRetries: 5,
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
var batch = new ClusterBatch(isAtomic: true);
batch.StringSet("key1", "value1");  // Different slots
batch.StringSet("key2", "value2");
await client.Exec(batch, raiseOnError: true);  // Throws

// Correct - use hash tags
var batch = new ClusterBatch(isAtomic: true);
batch.StringSet("{user}:1", "value1");  // Same slot
batch.StringSet("{user}:2", "value2");
await client.Exec(batch, raiseOnError: true);  // Success
```

## Summary Checklist

- [ ] Install `Valkey.Glide` NuGet package
- [ ] Use `await using` for client disposal
- [ ] Set explicit `RequestTimeout` in configuration
- [ ] Use `await` for all async operations (never `.Result` or `.Wait()`)
- [ ] Use `Batch(isAtomic: true)` for transactions, `Batch(isAtomic: false)` for pipelines
- [ ] Use hash tags `{tag}` for cluster atomic batches
- [ ] Handle specific exceptions: `ConnectionException`, `TimeoutException`, `RequestException`
- [ ] Configure PubSub subscriptions at connection time
- [ ] Use `ClusterBatch` for cluster mode, `Batch` for standalone
- [ ] Enable nullable reference types for better null safety

---

## Client Lifecycle Management

**ASP.NET Core:**
```csharp
// Program.cs
builder.Services.AddSingleton<GlideClient>(_ =>
    GlideClient.CreateClient(config).GetAwaiter().GetResult());

// Shutdown via IHostedService.StopAsync or await using for scripts
await using var client = await GlideClient.CreateClient(config);
```

---

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

---

# Performance Optimization

Config templates: [`snippets/csharp-config.cs`](snippets/csharp-config.cs)

`inflightRequestsLimit` not exposed in C# — managed at Rust core level (default: 1000). Focus on batching and `Task.WhenAll`.

## AZ Affinity

```csharp
using static Valkey.Glide.ConnectionConfiguration;

var config = new ClusterClientConfigurationBuilder()
    .WithAddress("cluster.endpoint.cache.amazonaws.com", 6379)
    .WithReadFrom(new ReadFrom(ReadFromStrategy.AzAffinity, "us-east-1a"))
    .WithRequestTimeout(TimeSpan.FromMilliseconds(500))
    .WithConnectionRetryStrategy(numberOfRetries: 10, factor: 500, exponentBase: 2)
    .WithClientName("my-app-cluster")
    .Build();

await using var client = await GlideClusterClient.CreateClient(config);
```

## Serverless / Lambda

```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress(Environment.GetEnvironmentVariable("CACHE_ENDPOINT")!, 6379)
    .WithRequestTimeout(TimeSpan.FromMilliseconds(500))
    .WithLazyConnect(true)  // Defer TCP+TLS handshake until first command
    .WithClientName("lambda-handler")
    .WithConnectionRetryStrategy(numberOfRetries: 3, factor: 500, exponentBase: 2)
    .Build();
```

## Retry Strategy

```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithRequestTimeout(TimeSpan.FromMilliseconds(500))
    .WithConnectionRetryStrategy(
        numberOfRetries: 10,
        factor: 500,        // Base delay in ms
        exponentBase: 2     // Exponential backoff
    )
    .Build();
```

## Dedicated Blocking Client

```csharp
var blockingConfig = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithRequestTimeout(TimeSpan.FromSeconds(30))
    .WithClientName("queue-worker")
    .Build();

await using var blockingClient = await GlideClient.CreateClient(blockingConfig);
var item = await blockingClient.ListBlockingLeftPopAsync(
    new ValkeyKey[] { "queue" }, TimeSpan.FromSeconds(30));
```

## Typed Error Handling

```csharp
using static Valkey.Glide.Errors;

try
{
    var value = await client.StringGetAsync("key");
}
catch (TimeoutException ex)
{
    // Retry with exponential backoff
}
catch (ConnectionException ex)
{
    // Transient — client will auto-reconnect; use circuit breaker pattern
}
catch (RequestException ex)
{
    // Server-side error (WRONGTYPE, etc.)
}
catch (ExecAbortException ex)
{
    // Transaction aborted
}
catch (ConfigurationError ex)
{
    // Invalid configuration — fix config and recreate client
}
```

## Hash vs JSON for Structured Data

```csharp
// ❌ Inefficient — must fetch/parse entire object
var json = JsonSerializer.Serialize(user);
await client.StringSetAsync("user:123", json);

// ✅ Efficient — fetch only needed fields
await client.HashSetAsync("user:123", new HashEntry[]
{
    new("name", "John"),
    new("email", "john@example.com")
});
var name = await client.HashGetAsync("user:123", "name");
```

## Concurrent Operations

```csharp
// Task.WhenAll for concurrent independent operations
var userTask = client.StringGetAsync("user:123");
var settingsTask = client.StringGetAsync("settings:123");
var statsTask = client.StringGetAsync("stats:123");

await Task.WhenAll(userTask, settingsTask, statsTask);

var user = userTask.Result;
var settings = settingsTask.Result;
var stats = statsTask.Result;
```

## Thread Safety

```csharp
// ✅ Batch created per scope (because Batch objects are NOT thread-safe — create one per operation scope.)
async Task ProcessAsync(GlideClient client)
{
    var batch = new Batch(isAtomic: false);
    batch.StringSet("key1", "value1");
    batch.StringGet("key1");
    await client.Exec(batch, raiseOnError: true);
}
```

## ASP.NET Core Integration

```csharp
// Program.cs — register as singleton
builder.Services.AddSingleton<GlideClient>(sp =>
    GlideClient.CreateClient(config).GetAwaiter().GetResult());

// Graceful shutdown via IHostedService
public class GlideShutdownService : IHostedService
{
    private readonly GlideClient _client;
    public GlideShutdownService(GlideClient client) => _client = client;
    public Task StartAsync(CancellationToken ct) => Task.CompletedTask;
    public async Task StopAsync(CancellationToken ct) => await _client.DisposeAsync();
}
```

## Monitoring

### OpenTelemetry

```csharp
// OpenTelemetry integration — check latest Valkey.Glide docs for C# API
// The Rust core emits traces/metrics; configure the OTel exporter at startup
```

### Logging

```csharp
// Set log level for production (reduce noise)
// Valkey.Glide uses the Rust core logger — configure via environment or API
```

Server-side config: [`performance/server-configuration-guide.md`](../performance/server-configuration-guide.md)
