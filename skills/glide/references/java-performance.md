# Java Performance Optimization

Config templates: `../assets/java-config.java`

## Client Lifecycle Management

**Spring Boot:**
```java
@Bean(destroyMethod = "close")
public GlideClient glideClient() throws ExecutionException, InterruptedException {
    return GlideClient.createClient(config).get();
}
```

**Plain Java (shutdown hook):**
```java
GlideClient client = GlideClient.createClient(config).get();
Runtime.getRuntime().addShutdownHook(new Thread(client::close));
```

---

## AZ Affinity

```java
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.ReadFrom;

GlideClusterClientConfiguration config = GlideClusterClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("cluster.endpoint.cache.amazonaws.com")
        .port(6379)
        .build())
    .readFrom(ReadFrom.AZ_AFFINITY)
    .clientAZ("us-east-1a")
    .requestTimeout(500)
    .build();

GlideClusterClient client = GlideClusterClient.createClient(config).get();
```

## Throughput Tuning

```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .inflightRequestsLimit(2000) // Default: 1000
    .requestTimeout(500)
    .build();
```

## Serverless / Lambda

```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .lazyConnect(true) // Defer connection until first command
    .requestTimeout(500)
    .build();
```

## Retry Strategy

```java
import glide.api.models.configuration.BackoffStrategy;

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .reconnectStrategy(BackoffStrategy.builder()
        .numberOfRetries(10)
        .factor(500)
        .exponentBase(2)
        .build())
    .requestTimeout(500)
    .build();
```

## Dedicated Blocking Client

```java
GlideClient blockingClient = GlideClient.createClient(
    GlideClientConfiguration.builder()
        .address(NodeAddress.builder().host("localhost").port(6379).build())
        .requestTimeout(30000)
        .clientName("queue-worker")
        .build()
).get();

String[] item = blockingClient.blpop(new String[]{"queue"}, 30).get();
```

---

## Concurrent Operations

```java
CompletableFuture<String> userFuture = client.get("user:123");
CompletableFuture<String[]> postsFuture = client.lrange("posts:123", 0, -1);
CompletableFuture.allOf(userFuture, postsFuture).join();
String user = userFuture.get();
```

## Thread Safety

```java
// ✅ Client shared across threads
private static final GlideClient client = createClient();

// ✅ Batch created per thread (because Batch objects are NOT thread-safe)
Batch batch = new Batch(false);
batch.get("key1");
client.exec(batch, true).get();
```

## Monitoring

### OpenTelemetry

```java
import glide.api.OpenTelemetry;

OpenTelemetry.init(
    OpenTelemetry.OpenTelemetryConfig.builder()
        .traces(OpenTelemetry.TracesConfig.builder()
            .endpoint("http://localhost:4318/v1/traces")
            .samplePercentage(1)
            .build())
        .metrics(OpenTelemetry.MetricsConfig.builder()
            .endpoint("http://localhost:4318/v1/metrics")
            .build())
        .build()
);
```

### Logging

```java
import glide.api.logging.Logger;

Logger.setLoggerConfig(Logger.Level.WARN, "glide.log");  // Production
Logger.setLoggerConfig(Logger.Level.ERROR);               // Max performance
```

Server-side config: `server-configuration-guide.md`
