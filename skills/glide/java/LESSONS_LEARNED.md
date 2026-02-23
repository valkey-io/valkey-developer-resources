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
- [ ] Cluster operations POC
- [ ] Document retry strategies for batches
- [ ] Document batch options (timeout, routing)

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
