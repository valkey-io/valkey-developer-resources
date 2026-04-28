# General Go Guidelines

## External Resources
- `../assets/go-config.go` - Client connection config templates, TLS/SSL, authentication (password, username, AWS IAM), cluster, standalone, etc.
- `go-anti-patterns.md` - Anti-patterns to avoid in Go GLIDE development including cluster slot patterns and CROSSSLOT errors, type assertion, and Hash vs JSON performance, and more

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
- See SKILL.md for retry strategy decision matrix

### Retry Strategies (Cluster Only)

```go
// Configure retry strategy
options := pipeline.NewClusterBatchOptions().
	WithRetryStrategy(*pipeline.NewClusterBatchRetryStrategy().
		WithRetryServerError(true).
		WithRetryConnectionError(false))

// Execute with options
results, err := client.ExecWithOptions(ctx, *batch, true, *options)
```

**API Pattern:**
- Use `ExecWithOptions()` instead of `Exec()` for retry strategies
- `NewClusterBatchRetryStrategy()` creates retry config
- Chain `WithRetryServerError()` and `WithRetryConnectionError()`
- Must dereference options with `*` when passing to `ExecWithOptions()`

---

## Type System

### Results Handling
```go
results, err := client.Exec(ctx, *batch, true)
if err != nil {
	return err
}
// results is []any ([]interface{})
```

**Key Points:**
- Results are `[]any` (interface slice)
- Always use two-value form for type assertions
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

**Key Points:**
- Use hash tags `{tag}` to control slot assignment
- Atomic operations require all keys in same slot
- Non-atomic batches automatically route to multiple nodes

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

### 7. Not Using defer for Cleanup
**Problem:** Forgetting to close client
**Solution:** Always use `defer client.Close()` after creation

---

## Client Lifecycle Management

```go
// package-level; initialize in main(), close on exit
var client *glide.Client

func main() {
    var err error
    client, err = glide.NewClient(cfg)
    if err != nil { log.Fatal(err) }
    defer client.Close()

    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()
    <-ctx.Done()
}
```

---

# Performance Optimization

Config templates: `../assets/go-config.go`

`inflightRequestsLimit` not exposed in Go — managed at Rust core level (default: 1000). Focus on batching and concurrency.

## AZ Affinity

```go
cfg := config.NewClusterClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "cluster.endpoint.cache.amazonaws.com", Port: 6379}).
    WithReadFrom(config.AzAffinity).
    WithClientAZ("us-east-1a").
    WithRequestTimeout(500 * time.Millisecond)

client, err := glide.NewClusterClient(cfg)
```

## Serverless / Lambda

```go
var lambdaClient *glide.Client

func ensureClient() error {
    if lambdaClient != nil {
        return nil
    }
    cfg := config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: os.Getenv("CACHE_ENDPOINT"), Port: 6379}).
        WithRequestTimeout(500 * time.Millisecond).
        WithLazyConnect(true). // Defer TCP+TLS handshake until first command
        WithClientName("lambda-handler").
        WithReconnectStrategy(config.NewBackoffStrategy(3, 500, 2))

    var err error
    lambdaClient, err = glide.NewClient(cfg)
    return err
}
```

## Retry Strategy

```go
cfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithReconnectStrategy(config.NewBackoffStrategy(10, 500, 2)). // retries, factor, exponentBase
    WithRequestTimeout(500 * time.Millisecond)
```

## Dedicated Blocking Client

```go
blockingClient, _ := glide.NewClient(
    config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
        WithRequestTimeout(30 * time.Second).
        WithClientName("queue-worker"),
)
item, err := blockingClient.BLPop(ctx, []string{"queue"}, 30*time.Second)
```

## Typed Error Handling

```go
import "errors"

value, err := client.Get(ctx, "key")
if err != nil {
    var timeoutErr *glide.TimeoutError
    var connErr *glide.ConnectionError
    var closingErr *glide.ClosingError

    switch {
    case errors.As(err, &timeoutErr):
        // Retry with exponential backoff
    case errors.As(err, &connErr):
        // Circuit breaker pattern
    case errors.As(err, &closingErr):
        // Client is closing — recreate
    }
}
```

## Cluster Scan

```go
cursor := models.NewClusterScanCursor()
var allKeys []string
scanOpts := *options.NewClusterScanOptions()
scanOpts.SetMatch("user:*")
scanOpts.SetCount(100)

for {
    result, err := clusterClient.ScanWithOptions(ctx, cursor, scanOpts)
    if err != nil { break }
    allKeys = append(allKeys, result.Keys...)
    cursor = result.Cursor
    if cursor.IsFinished() { break }
}
```

## Hash vs JSON for Structured Data

## Concurrent Operations

```go
// errgroup for concurrent operations with error handling:
g, ctx := errgroup.WithContext(ctx)
var user string
g.Go(func() error {
    var err error
    user, err = client.Get(ctx, "user:123")
    return err
})
// ... more goroutines
if err := g.Wait(); err != nil { /* handle */ }
```

## Goroutine Safety

```go
// ✅ Batch created per goroutine because Batch objects are NOT goroutine safe
go func() {
    batch := pipeline.NewStandaloneBatch(false)
    batch.Get("key1")
    client.Exec(ctx, *batch, false)
}()
```

## Monitoring

### OpenTelemetry

```go
err := glide.GetOtelInstance().Init(glide.OpenTelemetryConfig{
    Traces: &glide.OpenTelemetryTracesConfig{
        Endpoint:         "http://localhost:4318/v1/traces",
        SamplePercentage: 1,
    },
    Metrics: &glide.OpenTelemetryMetricsConfig{
        Endpoint: "http://localhost:4318/v1/metrics",
    },
})
```

### Logging

```go
import "github.com/valkey-io/valkey-glide/go/v2/logger"

logger.SetLoggerConfig(logger.Warn, "glide.log")  // Production
logger.SetLoggerConfig(logger.Error, "")           // Max performance
```

Server-side config: `server-configuration-guide.md`
