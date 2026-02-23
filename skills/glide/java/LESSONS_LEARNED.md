# Java GLIDE Lessons Learned

## Import Patterns

### Core Imports
```java
import glide.api.GlideClient;
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.Batch;
import glide.api.models.ClusterBatch;
```

**Key Finding:** Batch classes are in `glide.api.models`, NOT `glide.api.models.commands.batch`

## Client Creation

### Synchronous Client (Default)
```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .requestTimeout(10000)  // Important: default timeout may be too short
    .build();

try (GlideClient client = GlideClient.createClient(config).get()) {
    // operations
}
```

**Key Findings:**
- Client creation returns `CompletableFuture<GlideClient>`, must call `.get()`
- Default timeout can cause issues - explicitly set `requestTimeout()`
- Use try-with-resources for automatic cleanup
- Builder pattern for configuration

## Batch/Pipeline API

### Constructor Pattern
```java
Batch pipeline = new Batch(false);     // Non-atomic (pipeline)
Batch transaction = new Batch(true);   // Atomic (transaction)
```

**Key Finding:** Boolean parameter (not named parameter like Python's `isAtomic=`)

### Execution
```java
Object[] results = client.exec(batch, raiseOnError).get();
```

**Key Findings:**
- Returns `CompletableFuture<Object[]>`, must call `.get()`
- `raiseOnError` is boolean (true/false), not snake_case like Python
- Results are Object array, need casting for specific types

## Error Handling

### Exception Types
```java
import glide.api.models.exceptions.RequestException;
import glide.api.models.exceptions.TimeoutException;
import glide.api.models.exceptions.ConnectionException;

try {
    client.lpop("string_key").get();
} catch (ExecutionException e) {
    // Actual exception is in getCause()
    if (e.getCause() instanceof RequestException) {
        System.out.println("Request error: " + e.getCause().getMessage());
    }
}
```

**Key Findings:**
- Exceptions wrapped in `ExecutionException` due to CompletableFuture
- Use `getCause()` to get actual GLIDE exception
- Specific exception types: `RequestException`, `TimeoutException`, `ConnectionException`

## Type System

### Generics and Casting
```java
// Results need casting
Object[] results = client.exec(batch, true).get();
String value = (String) results[2];
Long count = (Long) results[3];
```

**Key Finding:** No type safety on batch results - manual casting required

## Async Patterns

### CompletableFuture
```java
// All operations return CompletableFuture
CompletableFuture<String> future = client.get("key");

// Blocking (sync) - call .get()
String value = future.get();

// Non-blocking (async) - use chaining
client.get("key").thenAccept(value -> {
    System.out.println(value);
});
```

**Key Finding:** Java GLIDE is async-first using CompletableFuture. Call `.get()` to block (sync), or chain with `.thenAccept()`, `.thenApply()`, etc. for async. Always add comments to clarify sync vs async usage.

## Python vs Java Comparison

| Aspect | Python | Java |
|--------|--------|------|
| Client creation | `await GlideClient.create(config)` | `GlideClient.createClient(config).get()` |
| Batch constructor | `Batch(False)` or `Batch(isAtomic=False)` | `new Batch(false)` |
| Batch execution | `await client.exec(batch, raise_on_error=True)` | `client.exec(batch, true).get()` |
| Error parameter | `raise_on_error` (snake_case) | `raiseOnError` (camelCase) |
| Exception handling | Direct exception | Wrapped in `ExecutionException` |
| Imports | `from glide import ...` | `import glide.api...` |
| Async model | `async/await` | `CompletableFuture` |

## Common Pitfalls

### 1. Wrong Batch Import
**Problem:** Trying to import from `glide.api.models.commands.batch.Batch`
**Solution:** Import from `glide.api.models.Batch`

### 2. Forgetting .get() on CompletableFuture
**Problem:** Operations return futures, not values
**Solution:** Always call `.get()` or use async chaining

### 3. Default Timeout Too Short
**Problem:** Connection timeouts on first request
**Solution:** Set explicit `requestTimeout()` in configuration (e.g., 10000ms)

### 4. Exception Unwrapping
**Problem:** Catching wrong exception type
**Solution:** Catch `ExecutionException` and use `getCause()` for actual error

### 5. Result Type Casting
**Problem:** `Object[]` results need casting
**Solution:** Cast to expected types: `(String)`, `(Long)`, etc.

## Next Steps

- [x] Vector search POC (FT.CREATE, FT.SEARCH)
- [x] Cluster operations POC (concepts demonstrated)
- [ ] Document retry strategies for batches
- [ ] Document batch options (timeout, routing)

---

## Cluster Operations

### Client Types
```java
// Standalone
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.Batch;

// Cluster
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.ClusterBatch;
```

### Hash Tags for Same Slot
```java
// In cluster mode, use hash tags to ensure keys map to same slot
ClusterBatch atomicBatch = new ClusterBatch(true);
atomicBatch.set("{user}:1", "Alice");  // Same slot
atomicBatch.set("{user}:2", "Bob");    // Same slot
client.exec(atomicBatch, true).get();  // Success
```

### CROSSSLOT Error
```java
// Atomic batch with keys in different slots fails
ClusterBatch crossSlot = new ClusterBatch(true);
crossSlot.set("key1", "value1");  // Slot A
crossSlot.set("key2", "value2");  // Slot B
client.exec(crossSlot, true).get();  // Throws RequestException: CROSSSLOT
```

**Key Finding:** CROSSSLOT error occurs when a single command/atomic batch operates on keys in different hash slots. In cluster mode, data is distributed across 16384 slots. Each key hashes to a specific slot, and slots are distributed across nodes. Commands requiring atomicity (like atomic batches or multi-key operations like `DEL`) must operate on keys in the same slot.

### Multi-Slot Operations
```java
// Non-atomic batch can span multiple slots
ClusterBatch pipeline = new ClusterBatch(false);
pipeline.set("key1", "value1");  // Slot A
pipeline.set("key2", "value2");  // Slot B
client.exec(pipeline, true).get();  // Success - GLIDE routes to different nodes

// Delete keys in same slot together
client.del(new String[]{"{user}:1", "{user}:2"}).get();  // Same slot - OK

// Delete keys in different slots separately
client.del(new String[]{"key1"}).get();
client.del(new String[]{"key2"}).get();
```

**Key Finding:** Non-atomic batches (pipelines) can span multiple slots. GLIDE automatically splits the pipeline into sub-pipelines per node, dispatches them independently, and reassembles responses in order.

### Cluster vs Standalone
- **Standalone:** Use `GlideClient` and `Batch`
- **Cluster:** Use `GlideClusterClient` and `ClusterBatch`
- **Atomic batch constraint:** All keys must map to same hash slot (cluster only)
- **Non-atomic batch:** Can span multiple slots in cluster mode
- **Hash tags:** Use `{tag}` to control slot assignment (e.g., `{user}:1`, `{user}:2`)

---

## Vector Search Patterns

### FT Module Imports
```java
import glide.api.commands.servermodules.FT;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.VectorFieldFlat;
import glide.api.models.commands.FT.FTCreateOptions.DistanceMetric;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.GlideString;
```

### Index Creation
```java
FieldInfo[] schema = new FieldInfo[] {
    new FieldInfo("embedding", 
        VectorFieldFlat.builder(DistanceMetric.COSINE, 3).build())
};
FT.create(client, "my_idx", schema).get();
```

### Vector Search
```java
float[] queryVec = {0.9f, 0.1f, 0.0f};
String query = "*=>[KNN 2 @embedding $vector AS score]";

FTSearchOptions opts = FTSearchOptions.builder()
    .params(Map.of(GlideString.of("vector"), GlideString.of(floatArrayToBytes(queryVec))))
    .build();

Object[] results = FT.search(client, "my_idx", query, opts).get();
// results[0] = count (Long)
// results[1] = Map of documents (only if count > 0)
```

**Key Finding:** FT.search returns `Object[]` where first element is count. Second element (documents map) only present if count > 0. Always check `results.length > 1` before accessing `results[1]`.

### Storing Documents with Vectors
```java
// CRITICAL: Use GlideString for binary vector data, NOT String
Map<GlideString, GlideString> doc = Map.of(
    GlideString.of("embedding"), GlideString.of(floatArrayToBytes(vec)),
    GlideString.of("category"), GlideString.of("A")
);
client.hset(GlideString.of("doc:1"), doc).get();
```

**Key Finding:** Binary vector data MUST use `GlideString`, not `String`. Converting bytes to String corrupts the data and breaks vector search. Use `GlideString.of(byte[])` for vectors.

### Vector Encoding
```java
private static byte[] floatArrayToBytes(float[] array) {
    ByteBuffer buffer = ByteBuffer.allocate(array.length * 4)
        .order(ByteOrder.LITTLE_ENDIAN);
    for (float f : array) {
        buffer.putFloat(f);
    }
    return buffer.array();
}
```

### Index Management
```java
// Drop index
FT.dropindex(client, "my_idx").get();

// Get info
Map<String, Object> info = FT.info(client, "my_idx").get();

// List all indexes
GlideString[] indexes = FT.list(client).get();
```

**Key Finding:** Use `GlideString.of()` factory method, not constructor. FT methods are static on `FT` class, not client methods.
