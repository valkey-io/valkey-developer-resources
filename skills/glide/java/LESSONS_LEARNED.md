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
String value = future.get();  // Blocking

// Or use async chaining
client.get("key").thenAccept(value -> {
    System.out.println(value);
});
```

**Key Finding:** Java GLIDE is async-first, uses CompletableFuture (not callbacks)

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

- [ ] Vector search POC (FT.CREATE, FT.SEARCH)
- [ ] Cluster operations POC
- [ ] Document retry strategies for batches
- [ ] Document batch options (timeout, routing)
