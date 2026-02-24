# Java GLIDE Performance Patterns

Language-specific optimization patterns for Java implementations using `io.valkey:valkey-glide`.

## Quick Wins

### 1. Client Reuse Pattern

**❌ Anti-Pattern: Per-Request Client Creation**
```java
// NEVER do this - creates new connection per request
public String handleRequest(Request request) {
    GlideClient client = GlideClient.createClient(
        GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host("localhost").port(6379).build())
            .build()
    ).get();
    
    String data = client.get("key").get();
    client.close();
    return data;
}
```

**✅ Correct: Singleton Client**
```java
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

public class CacheService {
    private static final GlideClient client;
    
    static {
        try {
            GlideClientConfiguration config = GlideClientConfiguration.builder()
                .address(NodeAddress.builder()
                    .host("localhost")
                    .port(6379)
                    .build())
                .requestTimeout(500)
                .clientName("my-app-client")
                .build();
            
            client = GlideClient.createClient(config).get();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create client", e);
        }
    }
    
    public String handleRequest(Request request) {
        return client.get("key").get();
    }
    
    public static void shutdown() {
        if (client != null) {
            client.close();
        }
    }
}
```

### 2. Request Timeout Configuration

**Production-Ready Configuration:**

For a complete production-ready configuration example with all recommended settings (timeouts, retry strategies, throughput tuning, AZ affinity), see `assets/config-templates/java-config.java`.

**✅ Always Configure Timeouts**
```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .requestTimeout(500) // milliseconds
    .build();
```

**Timeout Guidelines**:
- Real-time apps (sub-10ms): 20-50ms
- Web APIs: 200-500ms
- Background jobs: 1000-5000ms

## Batching Patterns

### Pipeline (Non-Atomic)

**❌ Sequential Operations**
```java
// 3 network roundtrips (~15ms)
String user1 = client.get("user:1").get();
String user2 = client.get("user:2").get();
String user3 = client.get("user:3").get();
```

**✅ Pipeline Batch**
```java
import glide.api.models.Batch;

// 1 network roundtrip (~5ms)
Batch batch = new Batch(false); // false = pipeline (non-atomic)

batch.get("user:1");
batch.get("user:2");
batch.get("user:3");

Object[] results = client.exec(batch, true).get();
String user1 = (String) results[0];
String user2 = (String) results[1];
String user3 = (String) results[2];
```

### Transaction (Atomic)

**✅ Atomic Operations**
```java
Batch transaction = new Batch(true); // true = transaction (atomic)

transaction.set("balance:user:123", "100");
transaction.incr("transaction:count");
transaction.set("last_update", String.valueOf(System.currentTimeMillis()));

Object[] results = client.exec(transaction, true).get();
// All commands succeed or all fail
```

### Batch Size Guidelines

```java
// Optimal: 10-100 commands
Batch batch = new Batch(false);
for (int i = 0; i < 50; i++) {
    batch.get("key:" + i);
}
Object[] results = client.exec(batch, true).get();

// Avoid: >1000 commands (split into smaller batches)
List<String> keys = IntStream.range(0, 5000)
    .mapToObj(i -> "key:" + i)
    .collect(Collectors.toList());
int batchSize = 100;

for (int i = 0; i < keys.size(); i += batchSize) {
    Batch batch = new Batch(false);
    keys.subList(i, Math.min(i + batchSize, keys.size()))
        .forEach(batch::get);
    Object[] results = client.exec(batch, true).get();
    // Process results
}
```

## Concurrent Operations

### CompletableFuture Pattern

**✅ Concurrent Independent Operations**
```java
import java.util.concurrent.CompletableFuture;

// Execute concurrently (wall-clock time = max latency)
CompletableFuture<String> userFuture = client.get("user:123");
CompletableFuture<String[]> postsFuture = client.lrange("posts:123", 0, -1);
CompletableFuture<String[]> commentsFuture = client.lrange("comments:123", 0, -1);

CompletableFuture.allOf(userFuture, postsFuture, commentsFuture).join();

String user = userFuture.get();
String[] posts = postsFuture.get();
String[] comments = commentsFuture.get();
```

**Note**: Batching is usually more efficient than CompletableFuture for multiple operations.

### CompletableFuture with Error Handling

**✅ Handle Partial Failures**
```java
List<CompletableFuture<String>> futures = List.of(
    client.get("key1"),
    client.get("key2"),
    client.get("key3")
);

futures.forEach(future -> 
    future.handle((result, ex) -> {
        if (ex != null) {
            System.err.println("Operation failed: " + ex.getMessage());
            return null;
        }
        return result;
    })
);

CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
```

## Cluster Patterns

### Hash Tags for Co-location

**❌ Keys on Different Slots**
```java
// Multiple roundtrips to different shards
String[] values = client.mget(new String[]{
    "user:123:name", "user:123:email", "user:123:age"
}).get();
```

**✅ Hash Tags for Same Slot**
```java
// Single roundtrip - all keys on same shard
String[] values = client.mget(new String[]{
    "{user:123}:name", "{user:123}:email", "{user:123}:age"
}).get();

// Set related data
Map<String, String> data = Map.of(
    "{user:123}:name", "John",
    "{user:123}:email", "john@example.com",
    "{user:123}:preferences", "{\"theme\":\"dark\"}"
);
client.mset(data).get();
```

### Cluster Scan

**✅ Iterate All Keys in Cluster**
```java
import glide.api.models.ClusterScanCursor;

ClusterScanCursor cursor = new ClusterScanCursor();
List<String> allKeys = new ArrayList<>();

do {
    Object[] result = clusterClient.scan(cursor, 
        ScanOptions.builder()
            .match("user:*")
            .count(100)
            .build()
    ).get();
    
    cursor = (ClusterScanCursor) result[0];
    String[] keys = (String[]) result[1];
    allKeys.addAll(Arrays.asList(keys));
} while (!cursor.isFinished());

System.out.println("Found " + allKeys.size() + " keys");
```

## AZ Affinity Configuration

**✅ Enable for Read-Heavy Workloads**
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
    .clientAZ("us-east-1a") // Your application's AZ
    .requestTimeout(500)
    .build();

GlideClusterClient client = GlideClusterClient.createClient(config).get();
```

**Requirements**:
- Valkey 8.0+ or ElastiCache for Valkey 7.2+
- Cluster mode with replicas
- Read-heavy workload (>80% reads)

## Error Handling

### Typed Exception Handling

**✅ Handle Specific Exception Types**
```java
import glide.api.models.exceptions.ConnectionException;
import glide.api.models.exceptions.TimeoutException;
import glide.api.models.exceptions.RequestException;

try {
    String result = client.get("key").get();
} catch (ExecutionException e) {
    Throwable cause = e.getCause();
    if (cause instanceof TimeoutException) {
        // Retry with exponential backoff
        System.err.println("Request timed out");
    } else if (cause instanceof ConnectionException) {
        // Circuit breaker pattern
        System.err.println("Connection failed");
    } else if (cause instanceof RequestException) {
        // Server error - check command syntax
        System.err.println("Request error: " + cause.getMessage());
    } else {
        // Unknown error
        System.err.println("Unexpected error: " + cause);
    }
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    System.err.println("Operation interrupted");
}
```

### Retry Strategy Configuration

**✅ Configure Reconnect Strategy**
```java
import glide.api.models.configuration.BackoffStrategy;

GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .reconnectStrategy(BackoffStrategy.builder()
        .numberOfRetries(10)
        .factor(500)        // Base delay in ms
        .exponentBase(2)    // Exponential backoff
        .build())
    .requestTimeout(500)
    .build();
```

## Advanced Patterns

### Try-With-Resources

**✅ Automatic Resource Management**
```java
try (GlideClient client = GlideClient.createClient(config).get()) {
    String result = client.get("key").get();
    // Client automatically closed
} catch (Exception e) {
    System.err.println("Error: " + e.getMessage());
}
```

### Blocking Commands

**✅ Dedicated Client for Blocking Operations**
```java
// Separate client for blocking commands
GlideClientConfiguration blockingConfig = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .requestTimeout(30000) // 30 seconds
    .clientName("queue-worker")
    .build();

GlideClient blockingClient = GlideClient.createClient(blockingConfig).get();

// Use for BLPOP, BRPOP, etc.
String[] item = blockingClient.blpop(new String[]{"queue"}, 30).get();

// Regular client for other operations
GlideClientConfiguration regularConfig = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .requestTimeout(500)
    .clientName("app-client")
    .build();

GlideClient regularClient = GlideClient.createClient(regularConfig).get();
```

### Throughput Tuning

GLIDE uses a single multiplexed connection, not a traditional connection pool. Tune throughput via `inflightRequestsLimit`.

**✅ High-Throughput Configuration**
```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .inflightRequestsLimit(2000) // Default: 1000
    .requestTimeout(500)
    .build();
```

## Data Structures

### Hash vs JSON

**❌ Large JSON Strings**
```java
import com.fasterxml.jackson.databind.ObjectMapper;

// Inefficient - must fetch/parse entire object
ObjectMapper mapper = new ObjectMapper();
Map<String, Object> user = Map.of("name", "John", "email", "john@example.com");
client.set("user:123", mapper.writeValueAsString(user)).get();

String data = client.get("user:123").get();
Map<String, Object> parsed = mapper.readValue(data, Map.class);
System.out.println(parsed.get("name")); // Had to fetch everything
```

**✅ Hash Data Structure**
```java
// Efficient - fetch only needed fields
Map<String, String> fields = Map.of(
    "name", "John",
    "email", "john@example.com",
    "age", "30"
);
client.hset("user:123", fields).get();

// Retrieve single field
String name = client.hget("user:123", "name").get();

// Retrieve multiple fields
String[] values = client.hmget("user:123", new String[]{"name", "email"}).get();

// Retrieve all fields
Map<String, String> allFields = client.hgetall("user:123").get();
```

## Monitoring

### OpenTelemetry Integration

**✅ Enable Tracing**
```java
import glide.api.OpenTelemetry;

// Initialize once at application startup
OpenTelemetry.init(
    OpenTelemetry.OpenTelemetryConfig.builder()
        .traces(
            OpenTelemetry.TracesConfig.builder()
                .endpoint("http://localhost:4318/v1/traces")
                .samplePercentage(1) // 1% sampling for production
                .build()
        )
        .metrics(
            OpenTelemetry.MetricsConfig.builder()
                .endpoint("http://localhost:4318/v1/metrics")
                .build()
        )
        .build()
);
```

### Logging Configuration

**✅ Production Logging**
```java
import glide.api.logging.Logger;

// Production: minimal logging
Logger.setLoggerConfig(Logger.Level.WARN, "glide.log");

// Development: verbose logging
Logger.setLoggerConfig(Logger.Level.INFO);

// Maximum performance: errors only
Logger.setLoggerConfig(Logger.Level.ERROR);
```

## SCAN vs Valkey-Search

### SCAN for Key Discovery (Scalability Concern)

**❌ SCAN Loop for Pattern-Based Key Lookup**
```java
// O(N) full keyspace iteration — degrades as dataset grows
List<String> matched = new ArrayList<>();
String cursor = "0";
do {
    Object[] result = client.scan(cursor, ScanOptions.builder()
        .match(pattern)
        .count(100)
        .build()
    ).get();
    cursor = (String) result[0];
    String[] keys = (String[]) result[1];
    matched.addAll(Arrays.asList(keys));
} while (!cursor.equals("0"));

// Then individually fetching each matched key compounds the problem
for (String key : matched) {
    String val = client.get(key).get();
    // ...
}
```

**✅ Valkey-Search Index for Efficient Queries**
```java
// Create index once at startup
client.ftCreate("idx:content", FTCreateOptions.builder()
    .prefix(List.of("content:"))
    .schema(List.of(
        new FieldSchema("title", FieldType.TEXT),
        new FieldSchema("tags", FieldType.TAG)
    ))
    .build()
).get();

// O(K) where K = result count, independent of total keyspace size
SearchResult results = client.ftSearch("idx:content", "@title:" + searchTerm).get();
```

**Note**: SCAN is appropriate for one-time migrations or admin tasks. For application-level search or filtering, Valkey-Search (`FT.*`) scales independently of keyspace size.

## Common Pitfalls

### 1. Not Calling get() on CompletableFuture

**❌ Missing get()**
```java
CompletableFuture<String> future = client.get("key");
System.out.println(future); // Prints CompletableFuture, not value!
```

**✅ Proper get()**
```java
String value = client.get("key").get();
System.out.println(value); // Prints actual value
```

### 2. Ignoring InterruptedException

**❌ Swallowing exception**
```java
try {
    String value = client.get("key").get();
} catch (InterruptedException e) {
    // Ignoring exception
}
```

**✅ Restore interrupt status**
```java
try {
    String value = client.get("key").get();
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw new RuntimeException("Operation interrupted", e);
}
```

### 3. Creating Client in Loop

**❌ Client per iteration**
```java
for (Item item : items) {
    GlideClient client = GlideClient.createClient(config).get(); // NEVER!
    client.set(item.getKey(), item.getValue()).get();
    client.close();
}
```

**✅ Reuse client**
```java
GlideClient client = GlideClient.createClient(config).get();
for (Item item : items) {
    client.set(item.getKey(), item.getValue()).get();
}
client.close();
```

### 4. Not Closing Client

**❌ Resource leak**
```java
GlideClient client = GlideClient.createClient(config).get();
// Use client
// Never closed - resource leak!
```

**✅ Proper cleanup**
```java
try (GlideClient client = GlideClient.createClient(config).get()) {
    // Use client
} // Automatically closed
```

## Thread Safety

### Client is Thread-Safe

**✅ Share Client Across Threads**
```java
// Single client can be safely used by multiple threads
private static final GlideClient client = createClient();

public void handleRequestThread1() {
    client.get("key1").get(); // Thread-safe
}

public void handleRequestThread2() {
    client.get("key2").get(); // Thread-safe
}
```

### Batch is NOT Thread-Safe

**❌ Sharing Batch Across Threads**
```java
Batch batch = new Batch(false);

// Thread 1
batch.get("key1"); // NOT thread-safe!

// Thread 2
batch.get("key2"); // NOT thread-safe!
```

**✅ Create Batch Per Thread**
```java
// Thread 1
Batch batch1 = new Batch(false);
batch1.get("key1");
client.exec(batch1, true).get();

// Thread 2
Batch batch2 = new Batch(false);
batch2.get("key2");
client.exec(batch2, true).get();
```

## Performance Checklist

- [ ] Client created once at startup, not per request
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching used for bulk operations (10-100 commands)
- [ ] CompletableFuture for concurrent independent operations
- [ ] Hash tags for related keys in cluster
- [ ] AZ affinity enabled for read-heavy workloads
- [ ] Error handling with typed exceptions
- [ ] Connection backoff configured
- [ ] Dedicated client for blocking commands
- [ ] Hash data structures for structured data
- [ ] Try-with-resources for automatic cleanup
- [ ] InterruptedException properly handled
- [ ] Thread safety considerations addressed
- [ ] OpenTelemetry enabled for monitoring
- [ ] Logging set to warn/error for production
