# Go GLIDE Lessons Learned

## Batch Operation Retry Strategies

### When to Use RetryServerError
**Scenario:** Cluster resharding, server under load, transient server errors

```go
options := pipeline.NewClusterBatchOptions().
	WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
		WithRetryServerError(true).
		WithRetryConnectionError(false))

results, err := client.ExecWithOptions(ctx, batch, true, *options)
```

**Use when:**
- Cluster is resharding (TRYAGAIN responses)
- Server is under heavy load
- Transient OOM or loading dataset errors

**Trade-off:** May reorder commands within batch

### When to Use RetryConnectionError
**Scenario:** Network instability, cluster node failover

```go
options := pipeline.NewClusterBatchOptions().
	WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
		WithRetryServerError(false).
		WithRetryConnectionError(true))

results, err := client.ExecWithOptions(ctx, batch, true, *options)
```

**Use when:**
- Network instability (cross-region, VPN)
- Cluster node failover in progress
- Connection pool exhaustion

**Trade-off:** May duplicate entire batch

### When to Use Both
**Scenario:** Maximum resilience for idempotent operations

```go
options := pipeline.NewClusterBatchOptions().
	WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
		WithRetryServerError(true).
		WithRetryConnectionError(true))

results, err := client.ExecWithOptions(ctx, batch, true, *options)
```

**Use when:**
- High availability required
- Operations are idempotent (SET, not INCR)
- Can tolerate reordering and duplication

**Trade-off:** Possible reordering + duplication

### When to Disable Retries
**Scenario:** Strict latency requirements, non-idempotent operations

```go
options := pipeline.NewClusterBatchOptions().
	WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
		WithRetryServerError(false).
		WithRetryConnectionError(false))

results, err := client.ExecWithOptions(ctx, batch, true, *options)
```

**Use when:**
- SLA-bound operations (strict latency requirements)
- Non-idempotent commands (INCR, LPUSH)
- Already have application-level retry logic
- Need predictable failure behavior

**Trade-off:** Fail fast on any error

---

## Import Patterns

### Core Imports
```go
import (
	"context"
	
	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)
```

**Key Finding:** Go GLIDE uses standard Go package structure. Main client in `glide`, configuration in `config`, batching in `pipeline`.

## Client Creation

### Standalone Client
```go
cfg := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
	WithRequestTimeout(10000)

client, err := glide.NewClient(cfg)
if err != nil {
	// Handle error
}
defer client.Close()
```

### Cluster Client
```go
cfg := config.NewClusterClientConfiguration().
	WithAddress(&config.NodeAddress{Host: "localhost", Port: 7000}).
	WithRequestTimeout(10000)

client, err := glide.NewClusterClient(cfg)
if err != nil {
	// Handle error
}
defer client.Close()
```

**Key Findings:**
- Configuration uses builder pattern with `With*()` methods
- Client creation returns `(client, error)` tuple
- Always use `defer client.Close()` for cleanup
- Context required for all operations

## Context Pattern

```go
ctx := context.Background()
value, err := client.Get(ctx, "key")
```

**Key Finding:** All operations require `context.Context` as first parameter. Use `context.Background()` for simple cases, or context with timeout/cancellation for production.

## Error Handling

```go
_, err := client.Set(ctx, "key", "value")
if err != nil {
	fmt.Println("Error:", err)
	return
}
```

**Key Finding:** Go uses explicit error returns. Always check `err != nil`. Errors are descriptive strings (e.g., "WRONGTYPE: Operation against a key holding the wrong kind of value").

## Batch/Pipeline API

### Standalone Batches
```go
// Non-atomic (pipeline)
pipeline := pipeline.NewStandaloneBatch(false).
	Set("key1", "value1").
	Set("key2", "value2").
	Get("key1")

results, err := client.Exec(ctx, *pipeline, true)
```

### Cluster Batches
```go
// Atomic (transaction)
transaction := pipeline.NewClusterBatch(true).
	Set("{user}:1", "Alice").
	Set("{user}:2", "Bob")

results, err := client.Exec(ctx, *transaction, true)
```

**Key Findings:**
- `pipeline.NewStandaloneBatch(bool)` for standalone
- `pipeline.NewClusterBatch(bool)` for cluster
- Fluent API with method chaining
- Must dereference with `*` when passing to `Exec()`
- Second parameter to `Exec()` is `raiseOnError` (bool)
- Returns `([]any, error)` - slice of interface{}

## Type System

### Results Handling
```go
results, err := client.Exec(ctx, *batch, true)
// results is []any ([]interface{})

// Type assertion needed
if str, ok := results[0].(string); ok {
	fmt.Println("String result:", str)
}
```

**Key Finding:** Results are `[]any` (interface slice). Need type assertions to access specific types. Common types: `string`, `int64`, `[]byte`.

## Cluster Operations

### Hash Tags for Same Slot
```go
// Keys with {user} tag map to same slot
batch := pipeline.NewClusterBatch(true).
	Set("{user}:1", "Alice").
	Set("{user}:2", "Bob")
```

### CROSSSLOT Errors
```go
// Different slots in atomic batch fails
batch := pipeline.NewClusterBatch(true).
	Set("key1", "value1").  // Slot A
	Set("key2", "value2")   // Slot B

_, err := client.Exec(ctx, *batch, true)
// Error: "Received crossed slots in pipeline- CrossSlot"
```

### Multi-Slot Operations
```go
// Non-atomic batch can span slots
pipeline := pipeline.NewClusterBatch(false).
	Del([]string{"{user}:1", "{user}:2"}).  // Same slot
	Del([]string{"key1"}).                   // Different slot
	Del([]string{"key2"})                    // Different slot

results, err := client.Exec(ctx, *pipeline, true)
// Results: [2 1 1]
```

**Key Finding:** `Del()` takes `[]string` slice, not variadic args.

## Go vs Java Comparison

| Aspect | Java | Go |
|--------|------|-----|
| Client creation | `GlideClient.createClient(config).get()` | `glide.NewClient(cfg)` returns `(client, error)` |
| Batch creation | `new Batch(true)` | `pipeline.NewStandaloneBatch(true)` |
| Method chaining | `batch.set("k", "v").get("k")` | `batch.Set("k", "v").Get("k")` |
| Batch execution | `client.exec(batch, true).get()` | `client.Exec(ctx, *batch, true)` |
| Error handling | Try-catch with `ExecutionException` | Explicit `error` return, check `err != nil` |
| Async model | `CompletableFuture` | Context-based, synchronous API |
| Type system | Generics, casting `Object[]` | Interface `[]any`, type assertions |
| Cleanup | `try-with-resources` or `.close()` | `defer client.Close()` |

## Common Pitfalls

### 1. Forgetting Context
**Problem:** Calling operations without context
**Solution:** Always pass `context.Context` as first parameter

### 2. Not Checking Errors
**Problem:** Ignoring error returns
**Solution:** Always check `if err != nil`

### 3. Forgetting to Dereference Batch
**Problem:** Passing batch directly to `Exec()`
**Solution:** Use `*batch` to dereference pointer

### 4. Wrong Batch Type
**Problem:** Using `NewStandaloneBatch` with cluster client
**Solution:** Use `NewClusterBatch` for cluster, `NewStandaloneBatch` for standalone

### 5. CROSSSLOT in Atomic Batches
**Problem:** Keys in different slots in atomic batch
**Solution:** Use hash tags `{tag}` to ensure same slot

### 6. Type Assertions Without Checking
**Problem:** Direct type assertion without ok check
**Solution:** Use `value, ok := result.(Type)` pattern

## Summary

- Go GLIDE uses idiomatic Go patterns: explicit errors, context, defer
- Fluent API for batch building with method chaining
- Must dereference batch pointers when executing
- Results are `[]any` requiring type assertions
- Context required for all operations
- Cluster operations follow same patterns as Java (hash tags, CROSSSLOT)


## TLS and Authentication

### ✅ TLS + Authentication (Port 6479)
Successfully validated TLS with password authentication:

```go
// For self-signed certificates (testing only)
tlsConfig := config.NewTlsConfiguration().WithInsecureTLS(true)
advancedConfig := config.NewAdvancedClientConfiguration().WithTlsConfiguration(tlsConfig)

clientConfig := config.NewClientConfiguration().
	WithAddress(&config.NodeAddress{Host: host, Port: 6479}).
	WithUseTLS(true).
	WithCredentials(config.NewServerCredentials("", "mypassword")).
	WithRequestTimeout(5000).
	WithAdvancedConfiguration(advancedConfig)

client, err := glide.NewClient(clientConfig)
```

**Output:**
```
✓ TLS works: Hello with TLS!
```

### Key Findings

**TLS Configuration:**
- Use `NewTlsConfiguration()` to create TLS config
- Use `WithInsecureTLS(true)` for self-signed certs (testing only)
- Wrap in `NewAdvancedClientConfiguration()` 
- Pass to client config with `WithAdvancedConfiguration()`

**Authentication:**
- Use `config.NewServerCredentials(username, password)`
- Empty string for username if only password is needed
- Pass with `WithCredentials()` before `WithAdvancedConfiguration()`

**Method Chain Order:**
1. `WithAddress()`
2. `WithUseTLS(true)`
3. `WithCredentials()`
4. `WithRequestTimeout()`
5. `WithAdvancedConfiguration()` (must be last)

### Comparison with Java

| Aspect | Java | Go |
|--------|------|-----|
| TLS config | `TlsAdvancedConfiguration.builder()...build()` | `config.NewTlsConfiguration().With*()` |
| Insecure mode | `.useInsecureTLS(true)` | `.WithInsecureTLS(true)` |
| Advanced config | `AdvancedGlideClientConfiguration.builder()` | `config.NewAdvancedClientConfiguration()` |
| Credentials | `ServerCredentials.builder().password().build()` | `config.NewServerCredentials("", "password")` |
| Client creation | `GlideClient.createClient(config).get()` | `glide.NewClient(config)` |
