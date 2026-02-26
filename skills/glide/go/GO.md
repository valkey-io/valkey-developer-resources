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
if err != nil {
	return err
}
// results is []any ([]interface{})

// ✅ Safe type assertion (recommended)
if str, ok := results[0].(string); ok {
	fmt.Println("String result:", str)
} else {
	// Handle unexpected type
}

// ❌ Unsafe - can panic if wrong type
strVal := results[0].(string)

// Common types
if str, ok := results[0].(string); ok {
	// "OK"
}
if intVal, ok := results[1].(int64); ok {
	// 42
}
if bytesVal, ok := results[2].([]byte); ok {
	// Binary data
}
```

**Key Points:**
- Results are `[]any` (interface slice)
- **Always use two-value form**: `value, ok := result.(Type)`
- Direct assertions can panic - avoid in production code
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

### 7. Type Assertions Without Safety Check
**Problem:** Direct assertion panics if wrong type
```go
// ❌ Wrong - panics if not string
str := results[0].(string)
```

**Solution:** Always use two-value form
```go
// ✅ Correct - safe type assertion
if str, ok := results[0].(string); ok {
	fmt.Println("Result:", str)
} else {
	// Handle unexpected type
	fmt.Println("Unexpected type")
}
```

### 8. Not Using defer for Cleanup
**Problem:** Forgetting to close client
**Solution:** Always use `defer client.Close()` after creation

---

## Go Best Practices for GLIDE

### Explicit Over Magic
Go GLIDE follows Go's philosophy of explicit, obvious code:

```go
// ✅ Explicit error handling (Go way)
value, err := client.Get(ctx, "key")
if err != nil {
	return fmt.Errorf("failed to get key: %w", err)
}

// ❌ Don't try to hide error handling
// No "smart" wrappers or generic error handlers
```

### No Struct Tag Magic
Unlike other languages, Go GLIDE doesn't use struct tags for configuration:

```go
// ✅ Explicit configuration
cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithRequestTimeout(10000)

// ❌ Not like this (anti-pattern from other ORMs)
// type Config struct {
//     Host string `valkey:"host"`
//     Port int    `valkey:"port"`
// }
```

### Separate Models for Different Concerns
If building a web application with GLIDE:

```go
// ✅ Separate models
type UserAPIResponse struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
}

type UserCacheModel struct {
	ID        int
	Name      string
	UpdatedAt time.Time
}

// Convert between them explicitly
func toAPIResponse(cache UserCacheModel) UserAPIResponse {
	return UserAPIResponse{
		ID:   cache.ID,
		Name: cache.Name,
	}
}

// ❌ Don't combine responsibilities
// type User struct {
//     ID   int    `json:"id" cache:"id"`
//     Name string `json:"name" cache:"name"`
// }
```

### Context for Cancellation
Use context properly for production code:

```go
// ✅ Production: timeout context
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

value, err := client.Get(ctx, "key")
if err != nil {
	if ctx.Err() == context.DeadlineExceeded {
		return fmt.Errorf("operation timed out")
	}
	return err
}

// ✅ Simple demos: background context
ctx := context.Background()
value, err := client.Get(ctx, "key")
```

### Error Wrapping
Provide context when returning errors:

```go
// ✅ Wrap errors with context
value, err := client.Get(ctx, userKey)
if err != nil {
	return fmt.Errorf("failed to fetch user %s: %w", userID, err)
}

// ❌ Don't lose error context
if err != nil {
	return err  // What failed? Which key?
}
```

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
