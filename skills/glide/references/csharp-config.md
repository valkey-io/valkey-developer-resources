# Configuration Options

## Database Selection (Standalone Only)
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithDataBaseId(1)
    .Build();
```

## Retry Strategy
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

## Client Name
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithClientName("my-app")
    .Build();
```

## Protocol Version
```csharp
var config = new StandaloneClientConfigurationBuilder()
    .WithAddress("localhost", 6379)
    .WithProtocolVersion(ConnectionConfiguration.Protocol.RESP2)
    .Build();
```

## Standalone Client
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

## Cluster Client
```csharp
var config = new ClusterClientConfigurationBuilder()
    .WithAddress("localhost", 7000)
    .WithAddress("localhost", 7001)
    .WithAddress("localhost", 7002)
    .Build();

await using var client = await GlideClusterClient.CreateClient(config);
```

## With Authentication and TLS
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
