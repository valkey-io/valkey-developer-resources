# General Go Guidelines

## Core Principles

1. Use Valkey GLIDE clients (`valkey-glide/go/v2`), NOT go-redis or other clients.
2. Always check error returns explicitly with `if err != nil`.
3. Use batching / pipelining when suitable to group operations for efficiency.
4. Pass `context.Context` to all operations.
5. Use `defer client.Close()` for cleanup.

---

## Package Selection

### ✅ CORRECT: Use GLIDE

**Installation:**
```bash
go get github.com/valkey-io/valkey-glide/go/v2
go mod tidy
```

**Imports:**
```go
import (
	"context"
	
	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)
```

**Key Points:**
- Requires Go 1.22 or above
- Standard Go module structure
- Context required for all operations

### ❌ INCORRECT: Don't use go-redis
```go
// NEVER use these
import "github.com/redis/go-redis/v9"
```

**Why:** go-redis is a Redis client. GLIDE is the official AWS-recommended client with better performance and active development.

---

## Client Creation Pattern

### Standalone Client
```go
cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithRequestTimeout(10000)

client, err := glide.NewClient(cfg)
if err != nil {
	// Handle error
	return
}
defer client.Close()

ctx := context.Background()
value, err := client.Get(ctx, "key")
```

### Cluster Client
```go
cfg := config.NewClusterClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 7000}).
	WithRequestTimeout(10000)

client, err := glide.NewClusterClient(cfg)
if err != nil {
	// Handle error
	return
}
defer client.Close()
```

**Key Points:**
- Configuration uses builder pattern with `With*()` methods
- Client creation returns `(client, error)` tuple
- Always check `err != nil`
- Use `defer client.Close()` for cleanup
- Context required for all operations

---

## Context Pattern

All operations require `context.Context` as first parameter:

```go
ctx := context.Background()

// Simple operations
value, err := client.Get(ctx, "key")
_, err = client.Set(ctx, "key", "value")

// With timeout
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
value, err := client.Get(ctx, "key")
```

**Key Points:**
- Use `context.Background()` for simple cases
- Use `context.WithTimeout()` or `context.WithCancel()` for production
- Context enables cancellation and timeout control

---

## Error Handling

### Explicit Error Checking
```go
_, err := client.Set(ctx, "key", "value")
if err != nil {
	fmt.Println("Error:", err)
	return
}

// Wrong type operation
_, err = client.LPop(ctx, "key")
if err != nil {
	// Error: "WRONGTYPE: Operation against a key holding the wrong kind of value"
	fmt.Println("Expected error:", err)
}
```

**Key Points:**
- Always check `err != nil`
- Errors are descriptive strings
- No exception unwrapping needed (unlike Java)

---

## Batch Commands (Go)

### Standalone Client

```go
// Non-atomic (pipeline)
pipeline := pipeline.NewStandaloneBatch(false).
	Set("user:1", "Alice").
	Set("user:2", "Bob").
	Get("user:1").
	Get("user:2")

results, err := client.Exec(ctx, *pipeline, true)
if err != nil {
	// Handle error
}
// results is []any: [OK OK Alice Bob]
```

```go
// Atomic (transaction)
transaction := pipeline.NewStandaloneBatch(true).
	Set("counter", "0").
	Incr("counter").
	Incr("counter").
	Get("counter")

results, err := client.Exec(ctx, *transaction, true)
// results: [OK 1 2 2]
```

### Cluster Client

```go
// Atomic batch - same slot required
atomicBatch := pipeline.NewClusterBatch(true).
	Set("{user}:1", "Alice").
	Set("{user}:2", "Bob").
	Get("{user}:1")

results, err := client.Exec(ctx, *atomicBatch, true)
```

```go
// Non-atomic pipeline - can span slots
pipelineBatch := pipeline.NewClusterBatch(false).
	Set("key1", "value1").
	Set("key2", "value2").
	Get("key1").
	Get("key2")

results, err := client.Exec(ctx, *pipelineBatch, true)
```

**Key Points:**
- `pipeline.NewStandaloneBatch(bool)` for standalone
- `pipeline.NewClusterBatch(bool)` for cluster
- Fluent API with method chaining
- Must dereference with `*` when passing to `Exec()`
- Second parameter is `raiseOnError` (bool)
- Returns `([]any, error)` - slice of interface{}

---

## Type System

### Results Handling
```go
results, err := client.Exec(ctx, *batch, true)
// results is []any ([]interface{})

// Type assertion with safety check
if str, ok := results[0].(string); ok {
	fmt.Println("String result:", str)
}

// Common types
strVal := results[0].(string)      // "OK"
intVal := results[1].(int64)       // 42
bytesVal := results[2].([]byte)    // Binary data
```

**Key Points:**
- Results are `[]any` (interface slice)
- Use type assertions to access specific types
- Always use two-value form: `value, ok := result.(Type)`
- Common types: `string`, `int64`, `[]byte`

---

## Cluster Operations

### Hash Slots and CROSSSLOT Errors

```go
// Success - hash tags ensure same slot
atomicBatch := pipeline.NewClusterBatch(true).
	Set("{user}:1", "Alice").
	Set("{user}:2", "Bob")

results, err := client.Exec(ctx, *atomicBatch, true)
```

```go
// Fails - different slots
crossSlotBatch := pipeline.NewClusterBatch(true).
	Set("key1", "value1").  // Slot A
	Set("key2", "value2")   // Slot B

_, err := client.Exec(ctx, *crossSlotBatch, true)
// Error: "Received crossed slots in pipeline- CrossSlot"
```

### Multi-Slot Operations

```go
// Non-atomic batch can span slots
pipelineBatch := pipeline.NewClusterBatch(false).
	Set("key1", "value1").
	Set("key2", "value2").
	Get("key1").
	Get("key2")

results, err := client.Exec(ctx, *pipelineBatch, true)
```

```go
// Cleanup across multiple slots
cleanupBatch := pipeline.NewClusterBatch(false).
	Del([]string{"{user}:1", "{user}:2"}).  // Same slot
	Del([]string{"key1"}).                   // Different slot
	Del([]string{"key2"})                    // Different slot

results, err := client.Exec(ctx, *cleanupBatch, true)
// Results: [2 1 1]
```

**Key Points:**
- Use hash tags `{tag}` to control slot assignment
- Atomic operations require all keys in same slot
- Non-atomic batches automatically route to multiple nodes
- `Del()` takes `[]string` slice parameter

---

## Common Pitfalls

### 1. Using go-redis Instead of GLIDE
**Problem:** Using wrong client library
**Solution:** Always use `github.com/valkey-io/valkey-glide/go/v2`

### 2. Forgetting Context
**Problem:** Calling operations without context
**Solution:** Always pass `context.Context` as first parameter

### 3. Not Checking Errors
**Problem:** Ignoring error returns
**Solution:** Always check `if err != nil`

### 4. Forgetting to Dereference Batch
**Problem:** Passing batch directly: `client.Exec(ctx, batch, true)`
**Solution:** Dereference pointer: `client.Exec(ctx, *batch, true)`

### 5. Wrong Batch Type
**Problem:** Using `NewStandaloneBatch` with cluster client
**Solution:** Use `NewClusterBatch` for cluster, `NewStandaloneBatch` for standalone

### 6. CROSSSLOT Errors in Cluster Mode
**Problem:** Atomic batch with keys in different slots
**Solution:** Use hash tags `{tag}` to ensure keys map to same slot

### 7. Type Assertions Without Checking
**Problem:** Direct assertion: `str := result.(string)` panics if wrong type
**Solution:** Use safe form: `str, ok := result.(string)`

### 8. Not Using defer for Cleanup
**Problem:** Forgetting to close client
**Solution:** Always use `defer client.Close()` after creation

---

## Summary Checklist

When implementing Valkey functionality with GLIDE:

- [ ] Use `valkey-glide/go/v2`, NOT go-redis
- [ ] Import from correct packages: `glide`, `config`, `pipeline`
- [ ] Pass `context.Context` to all operations
- [ ] Always check `err != nil` after operations
- [ ] Use `defer client.Close()` for cleanup
- [ ] Dereference batch with `*` when passing to `Exec()`
- [ ] Use `NewStandaloneBatch` for standalone, `NewClusterBatch` for cluster
- [ ] Use hash tags `{tag}` for same-slot operations in cluster
- [ ] Use safe type assertions: `value, ok := result.(Type)`
- [ ] Handle `[]any` results with type assertions

---

## References

- [Valkey GLIDE Documentation](https://glide.valkey.io/)
- [GLIDE Go Client](https://github.com/valkey-io/valkey-glide/tree/main/go)
- [Go Package Documentation](https://pkg.go.dev/github.com/valkey-io/valkey-glide/go/v2)

---

**Version:** 1.0
**Last Updated:** 2026-02-25
**Source:** Production implementation experience
