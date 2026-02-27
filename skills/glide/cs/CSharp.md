# C# GLIDE Skill (Preview)

> **⚠️ Status:** C# GLIDE is in early development (v0.9.0). This skill will be fully developed when v1.0 is released and available on NuGet.

## Current Status

- **Version:** v0.9.0 (September 17, 2025)
- **Repository:** https://github.com/valkey-io/valkey-glide-csharp
- **NuGet:** Not yet published
- **Documentation:** https://glide.valkey.io/languages/csharp

## Installation (Source Build Required)

```bash
git clone https://github.com/valkey-io/valkey-glide-csharp.git
cd valkey-glide-csharp
# Follow DEVELOPER.md for build instructions
```

## Basic Usage (from v0.9.0 README)

### Standalone Client

```csharp
using Valkey.Glide;

var config = GlideClientConfiguration.Builder()
    .WithAddress("localhost", 6379)
    .Build();

await using var client = await GlideClient.CreateClient(config);

// Basic operations
await client.StringSetAsync("key", "value");
var result = await client.StringGetAsync("key");
Console.WriteLine($"Value: {result}");
```

### Cluster Client

```csharp
var config = GlideClusterClientConfiguration.Builder()
    .WithAddress("localhost", 7000)
    .WithAddress("localhost", 7001)
    .WithAddress("localhost", 7002)
    .Build();

await using var client = await GlideClusterClient.CreateClient(config);
```

### Pub/Sub

```csharp
var config = GlideClientConfiguration.Builder()
    .WithAddress("localhost", 6379)
    .WithPubSubSubscriptions(builder => builder
        .WithChannel("alerts")
        .WithPattern("log:*")
        .WithCallback((msg, ctx) => {
            Console.WriteLine($"Received: {msg.Message}");
        }))
    .Build();

await using var client = await GlideClient.CreateClient(config);

// Subscribe/unsubscribe dynamically
client.PSubscribeAsync("news*");
client.UnsubscribeAsync("alerts");
```

### Error Handling

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

## Key Features

- **Rust Core:** High performance with memory safety
- **Async/Await:** Native .NET async patterns
- **Connection Pooling:** Efficient connection management
- **Pipeline Support:** Batch operations for reduced latency
- **Pub/Sub:** Message patterns and callbacks
- **Cluster Support:** Multi-node routing

## Exception Types

- `ConnectionException` - Connection failures
- `TimeoutException` - Operation timeouts
- `ValkeyException` - General Valkey errors

## Ecosystem Integration

C# GLIDE works well with:
- **ASP.NET Core** - Caching layer or session store
- **Entity Framework** - High-performance caching
- **Minimal APIs** - Microservices and API backends
- **Background Services** - Queue processing

## Next Steps

**When C# GLIDE reaches v1.0:**
1. Full POC development (basic operations, batch/pipeline, vector search, cluster)
2. Comprehensive lessons learned document
3. Complete skill file with all patterns
4. Anti-pattern analysis
5. Validation against production Valkey

## References

- [GitHub Repository](https://github.com/valkey-io/valkey-glide-csharp)
- [API Documentation](https://docs.github.io/valkey-glide/)
- [General Concepts](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts)
- [Contributing Guidelines](https://github.com/valkey-io/valkey-glide-csharp/blob/main/CONTRIBUTING.md)

---

**Last Updated:** 2026-02-27  
**C# GLIDE Version:** v0.9.0 (Pre-release)
