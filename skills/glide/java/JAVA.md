# General Java Guidelines

## External Resources

### Code Snippets
- TBD

---

## Core Principles

1. Use Valkey GLIDE clients (`valkey-glide`), NOT Jedis or Lettuce clients.
2. Avoid catching general exceptions when handling GLIDE errors - use specific exception types.
3. Use batching / pipelining when suitable to group operations for efficiency.
4. Prefer async chaining over blocking calls for production applications.
5. Add comments to clarify sync vs async when not obvious from syntax.

---

## Package Selection

### ✅ CORRECT: Use GLIDE

**Maven:**
```xml
<build>
    <extensions>
        <extension>
            <groupId>kr.motd.maven</groupId>
            <artifactId>os-maven-plugin</artifactId>
            <version>1.7.1</version>
        </extension>
    </extensions>
</build>
<dependencies>
    <dependency>
        <groupId>io.valkey</groupId>
        <artifactId>valkey-glide</artifactId>
        <classifier>${os.detected.classifier}</classifier>
        <version>[2.0.0,)</version>
    </dependency>
</dependencies>
```

**Gradle:**
```gradle
plugins {
    id 'com.google.osdetector' version '1.7.3'
}

dependencies {
    implementation group: 'io.valkey', name: 'valkey-glide', version: '2.+', classifier: osdetector.classifier
}
```

**Key Points:**
- Classifier is required (native binaries per platform)
- Use `os-maven-plugin` or `osdetector` for platform detection
- Supports: linux-x86_64, linux-aarch_64, osx-x86_64, osx-aarch_64, windows-x86_64

### ❌ INCORRECT: Don't use Jedis or Lettuce
```java
// NEVER use these
import redis.clients.jedis.*;
import io.lettuce.core.*;
```

**Why:** Jedis and Lettuce are Redis clients. GLIDE is the official AWS-recommended client with better performance and active development.

---

## Client Creation Pattern

### Core Imports
```java
import glide.api.GlideClient;
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.Batch;
import glide.api.models.ClusterBatch;
import glide.api.models.exceptions.RequestException;
import glide.api.models.exceptions.TimeoutException;
import glide.api.models.exceptions.ConnectionException;
```

### Choose Cluster vs Standalone

**Use cluster client when:**
- Running multiple GLIDE nodes
- Using multiple Valkey clusters

Otherwise, use standalone client.

### Async Pattern (Recommended for Production)
Use async method chaining, and narrow exception checking via `instanceof` in `exceptionally` handlers.

```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .requestTimeout(10000)  // Recommended: explicit timeout
    .build();

// Async (non-blocking) - using CompletableFuture chaining
GlideClient.createClient(config).thenCompose(client -> {
    return client.set("key", "value")
        .thenCompose(ok -> client.get("key"))
        .thenAccept(value -> System.out.println(value))
        .exceptionally(e -> {
            // Direct access to GLIDE exceptions, no unwrapping
            if (e instanceof RequestException) {
                System.err.println("Request error: " + e.getMessage());
            }
            return null;
        })
        .whenComplete((v, e) -> {
            try {
                client.close();
            } catch (ExecutionException ex) {
                System.err.println("Error closing: " + ex.getMessage());
            }
        });
}).join(); // Only block at the end
```

### Blocking Pattern (Simple Scripts/Demos Only)

```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder()
        .host("localhost")
        .port(6379)
        .build())
    .requestTimeout(10000)
    .build();

// Blocking (sync) - using .get() on CompletableFuture
try (GlideClient client = GlideClient.createClient(config).get()) {
    client.set("key", "value").get();
    String value = client.get("key").get();
    System.out.println(value);
}
```

**Key Points:**
- Client creation returns `CompletableFuture<GlideClient>`
- Async: Use `.thenCompose()`, `.thenAccept()`, etc. for chaining
- Blocking: Call `.get()` or `.join()` to block thread
- Always set explicit `requestTimeout()` (default may be too short)
- Use try-with-resources for automatic cleanup in blocking mode

---

## Async vs Blocking

### When to Use Async (Recommended)
- Production applications
- High concurrency requirements
- Non-blocking I/O frameworks (Netty, etc.)
- Better thread utilization

### When to Use Blocking
- Simple scripts or demos
- Sequential processing requirements
- Simpler code for prototypes

### Exception Handling Differences
These catch an `ExecutionException`, branch on the enclosed narrower exception, perform any narrow-specific processing, and then rethrows it.

**Async chaining:**
```java
client.get("key")
    .exceptionally(e -> {
        // Exception may be wrapped - unwrap to check actual cause
        Throwable cause = (e instanceof CompletionException && e.getCause() != null) 
            ? e.getCause() : e;
        
        if (cause instanceof RequestException) {
            // Handle and optionally rethrow
            System.err.println("Request error: " + cause.getMessage());
            throw new CompletionException((RequestException) cause);  // Rethrow
        }
        return null;  // Or return default value
    });
```

**Blocking with .get():**
```java
try {
    client.get("key").get();
} catch (ExecutionException e) {
    // Must unwrap: actual exception is in getCause()
    if (e.getCause() instanceof RequestException) {
        RequestException re = (RequestException) e.getCause();
        // Handle error
    }
}
```

**Blocking with .join():**
```java
try {
    client.get("key").join();
} catch (CompletionException e) {
    // Must unwrap: actual exception is in getCause()
    if (e.getCause() instanceof RequestException) {
        RequestException re = (RequestException) e.getCause();
        // Handle error
    }
}
```

**Key Finding:** Async exceptions may arrive wrapped in `CompletionException` - unwrap with `getCause()` before checking type. Rethrow by wrapping in new `CompletionException` to propagate up the chain.

---

## Batch Commands (Java)

### Standalone Client

**Async (recommended):**
```java
Batch pipeline = new Batch(false);  // Non-atomic (pipeline)
pipeline.set("key1", "value1");
pipeline.set("key2", "value2");
pipeline.get("key1");

client.exec(pipeline, true)
    .thenAccept(results -> {
        // results is Object[]
        System.out.println(Arrays.toString(results));
    });
```

**Blocking:**
```java
Batch transaction = new Batch(true);  // Atomic (transaction)
transaction.set("counter", "0");
transaction.incr("counter");
transaction.get("counter");

Object[] results = client.exec(transaction, true).get();
// results: [OK, 1, 1]
```

### Key Points

- Constructor: `new Batch(boolean isAtomic)` - positional parameter, not named
- Execution: `client.exec(batch, raiseOnError)` - camelCase parameter
- Returns: `CompletableFuture<Object[]>` - need casting for specific types
- `raiseOnError=true`: Throws first error as exception
- `raiseOnError=false`: Returns errors in result array

---

## Error Handling

### Exception Types
```java
import glide.api.models.exceptions.RequestException;      // Command errors (WRONGTYPE, etc.)
import glide.api.models.exceptions.TimeoutException;      // Request timeout
import glide.api.models.exceptions.ConnectionException;   // Connection issues
```

### ✅ CORRECT: Specific Exception Handling

**Async:**
```java
client.lpop("string_key")
    .exceptionally(e -> {
        Throwable cause = (e instanceof CompletionException && e.getCause() != null) 
            ? e.getCause() : e;
        
        if (cause instanceof RequestException) {
            System.err.println("Request error: " + cause.getMessage());
        } else if (cause instanceof TimeoutException) {
            System.err.println("Timeout: " + cause.getMessage());
        }
        return null;
    });
```

**Blocking:**
```java
try {
    client.lpop("string_key").get();
} catch (ExecutionException e) {
    if (e.getCause() instanceof RequestException) {
        System.err.println("Request error: " + e.getCause().getMessage());
    }
}
```

### ❌ INCORRECT: Broad Exception Handling
```java
// DON'T catch Exception - too broad
try {
    client.get("key").get();
} catch (Exception e) {
    // Too vague
}
```

---

## Common Pitfalls

### 1. Using Jedis/Lettuce Instead of GLIDE
**Problem:** Using legacy Redis clients
**Solution:** Always use `valkey-glide` package

### 2. Missing Platform Classifier
**Problem:** Build fails with missing native library
**Solution:** Use `os-maven-plugin` or `osdetector` for automatic platform detection

### 3. Blocking in Production Code
**Problem:** Using `.get()` or `.join()` blocks threads, kills concurrency
**Solution:** Use async chaining with `.thenCompose()`, `.thenAccept()`, etc.

### 4. Forgetting .get() in Blocking Code
**Problem:** Operations return `CompletableFuture`, not values
**Solution:** Call `.get()` or `.join()` when blocking is acceptable

### 5. Default Timeout Too Short
**Problem:** Connection timeouts on first request
**Solution:** Set explicit `requestTimeout()` in configuration (e.g., 10000ms)

### 6. Wrong Batch Import
**Problem:** Trying to import from `glide.api.models.commands.batch.Batch`
**Solution:** Import from `glide.api.models.Batch`

### 7. Broad Exception Catching
**Problem:** Catching `Exception` instead of specific GLIDE exceptions
**Solution:** Catch `RequestException`, `TimeoutException`, `ConnectionException`

### 8. Not Unwrapping Exceptions in Blocking Code
**Problem:** Catching `ExecutionException` but not checking `getCause()`
**Solution:** Use `e.getCause()` to get actual GLIDE exception, or prefer async

---

## Summary Checklist

When implementing Valkey functionality with GLIDE:

- [ ] Use `valkey-glide`, NOT Jedis or Lettuce
- [ ] Include platform classifier with auto-detection
- [ ] Prefer async chaining over blocking for production
- [ ] Add comments to clarify sync vs async usage
- [ ] Set explicit `requestTimeout()` in configuration
- [ ] Import `Batch` from `glide.api.models`, not `glide.api.models.commands.batch`
- [ ] Catch specific exceptions: `RequestException`, `TimeoutException`, `ConnectionException`
- [ ] Use `.exceptionally()` for async error handling (no unwrapping needed)
- [ ] Unwrap exceptions with `.getCause()` when using blocking `.get()` or `.join()`
- [ ] Support both cluster and standalone modes
- [ ] Cast `Object[]` results to specific types as needed

---

## References

- [Valkey GLIDE Documentation](https://glide.valkey.io/)
- [GLIDE Java Client](https://github.com/valkey-io/valkey-glide/tree/main/java)

---

**Version:** 1.0
**Last Updated:** 2026-02-23
**Source:** Production implementation experience
