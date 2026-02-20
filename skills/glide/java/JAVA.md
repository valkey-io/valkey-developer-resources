# General Java Guidelines

## External Resources

### Code Snippets
- TBD

---

## Core Principles

1. Use Valkey GLIDE clients (`glide-for-redis`), NOT the Jedis or Lettuce clients.
2. Avoid catching general exceptions when handling GLIDE errors.
3. Use batching / pipelining when suitable to group operations for efficiency.

---

## Package Selection

### ✅ CORRECT: Use GLIDE

**Maven:**
```xml
<dependency>
    <groupId>io.valkey</groupId>
    <artifactId>valkey-glide</artifactId>
    <version>1.0.0</version>
</dependency>
```

**Gradle:**
```gradle
implementation 'io.valkey:valkey-glide:1.0.0'
```

### ❌ INCORRECT: Don't use Jedis or Lettuce
```java
// NEVER use these
import redis.clients.jedis.*;
import io.lettuce.core.*;
```

---

## Client Creation Pattern

### Choose Cluster vs Standalone

**Use cluster client when:**
- Running multiple GLIDE nodes
- Using multiple Valkey clusters

Otherwise, use standalone client.

---

## Batch Commands (Java)

### Standalone Client

```java
// TBD
```

### Cluster Client

```java
// TBD
```

---

## Common Pitfalls

### 1. Using Jedis/Lettuce Instead of GLIDE
**Problem:** Using legacy Redis clients
**Solution:** Always use `valkey-glide` package

---

## Dependencies

### Package Installation

**Maven:**
```xml
<dependency>
    <groupId>io.valkey</groupId>
    <artifactId>valkey-glide</artifactId>
    <version>1.0.0</version>
</dependency>
```

---

## Summary Checklist

When implementing Valkey functionality with GLIDE:

- [ ] Use `valkey-glide`, NOT Jedis or Lettuce
- [ ] Support both cluster and standalone modes
- [ ] Use batching for bulk operations

---

## References

- [Valkey GLIDE Documentation](https://glide.valkey.io/)
- [GLIDE Java Client](https://github.com/valkey-io/valkey-glide/tree/main/java)

---

**Version:** 1.0
**Last Updated:** 2026-02-20
**Source:** Production implementation experience
