# Java GLIDE Anti-Pattern Demonstrations

This demo proves common Java anti-patterns and their correct alternatives, based on [AyoKoding Java Anti-Patterns Guide](https://www.ayokoding.com/en/learn/software-engineering/programming-languages/java/in-the-field/anti-patterns/).

## Running the Demo

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd java/demos
./gradlew run -PmainClass=AntiPatternDemo
```

## Anti-Patterns Demonstrated

### 1. Resource Management: Not Closing Resources

**Anti-Pattern:**
```java
GlideClient client = GlideClient.createClient(config).get();
client.set("key", "value").get();
// PROBLEM: Client never closed, connection leaked
```

**Correct Approach:**
```java
try (GlideClient client = GlideClient.createClient(config).get()) {
    client.set("key", "value").get();
    // SOLUTION: try-with-resources guarantees cleanup
}
```

**Why This Fails:**
- Exhausts connection pool
- Causes memory leaks
- Prevents graceful shutdown
- Leads to "too many open connections" errors

**Demo Output:**
```
=== ANTI-PATTERN: Resource Leak ===
Set value (client NOT closed - RESOURCE LEAK!)

=== CORRECT: Try-With-Resources ===
Set value (client auto-closed via try-with-resources)
```

---

### 2. Concurrency: Swallowing InterruptedException

**Anti-Pattern:**
```java
try {
    String value = future.get();
} catch (InterruptedException e) {
    // PROBLEM: Swallowing interruption, thread can't be stopped
    System.out.println("Interrupted (but ignoring it)");
}
```

**Correct Approach:**
```java
try {
    String value = future.get();
} catch (InterruptedException e) {
    // SOLUTION: Restore interrupt status
    Thread.currentThread().interrupt();
    System.out.println("Interrupted (status restored)");
}
```

**Why This Fails:**
- Breaks thread cancellation mechanisms
- Makes threads unresponsive to shutdown
- Causes resource leaks during shutdown
- Violates interruption protocol

**Demo Output:**
```
=== ANTI-PATTERN: Swallowing InterruptedException ===
Value: value

=== CORRECT: Restore Interrupt Status ===
Value: value
```

---

### 3. Exception Handling: Not Unwrapping ExecutionException

**Anti-Pattern:**
```java
try {
    client.lpop("string:key").get();
} catch (RequestException e) {
    // PROBLEM: This never catches - RequestException wrapped in ExecutionException
    System.out.println("Caught RequestException (NEVER REACHED!)");
}
```

**Correct Approach:**
```java
try {
    client.lpop("string:key").get();
} catch (ExecutionException e) {
    // SOLUTION: Check getCause() for actual exception
    if (e.getCause() instanceof RequestException) {
        System.out.println("Caught: " + e.getCause().getMessage());
    }
}
```

**Why This Fails:**
- CompletableFuture wraps exceptions in ExecutionException
- Direct catch of GLIDE exceptions never triggers
- Errors go unhandled
- Difficult to debug

**Demo Output:**
```
=== ANTI-PATTERN: Wrong Exception Handling ===
Caught generic exception: ExecutionException

=== CORRECT: Unwrap ExecutionException ===
Caught RequestException via getCause(): WRONGTYPE: Operation against a key holding the wrong kind of value
```

---

### 4. Design: Primitive Obsession

**Anti-Pattern:**
```java
// Using raw strings, no type safety
String userId = "user:123";
String sessionId = "session:456";

// Easy to swap parameters - compiles but wrong!
storeUserData(client, sessionId, userId);  // WRONG ORDER!
```

**Correct Approach:**
```java
// Type-safe value objects
class UserId {
    private final String value;
    public UserId(String value) {
        if (!value.startsWith("user:")) {
            throw new IllegalArgumentException("Invalid user ID");
        }
        this.value = value;
    }
}

UserId userId = new UserId("user:123");
SessionId sessionId = new SessionId("session:456");

// Compiler prevents parameter swap!
storeUserDataTypeSafe(client, userId, sessionId);
```

**Why This Fails:**
- No type safety for domain concepts
- Easy to pass wrong values
- Validation duplicated everywhere
- No encapsulation of business rules

**Demo Output:**
```
=== ANTI-PATTERN: Primitive Obsession ===
Stored with primitives (no type safety)

=== CORRECT: Value Objects ===
Stored with value objects (type-safe)
```

---

## Key Takeaways

1. **Always use try-with-resources** for GLIDE clients
2. **Never swallow InterruptedException** - restore interrupt status
3. **Unwrap ExecutionException** to get actual GLIDE exceptions
4. **Use value objects** instead of primitives for domain concepts

## Related Resources

- [AyoKoding Java Anti-Patterns](https://www.ayokoding.com/en/learn/software-engineering/programming-languages/java/in-the-field/anti-patterns/)
- [Java GLIDE Documentation](https://github.com/valkey-io/valkey-glide/tree/main/java)
- [Effective Java (3rd Edition)](https://www.oreilly.com/library/view/effective-java-3rd/9780134686097/)
