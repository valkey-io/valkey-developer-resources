# Go GLIDE Performance Patterns

Language-specific optimization patterns for Go implementations using `valkey-glide/go`.

## Quick Wins

### 1. Client Reuse Pattern

**❌ Anti-Pattern: Per-Request Client Creation**
```go
// NEVER do this - creates new connection per request
func handleRequest(w http.ResponseWriter, r *http.Request) {
    cfg := config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379})

    client, err := glide.NewClient(cfg)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    defer client.Close()
    
    data, _ := client.Get(r.Context(), "key")
    w.Write([]byte(data))
}
```

**✅ Correct: Singleton Client**
```go
package main

import (
    "context"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

var client *glide.Client

func init() {
    cfg := config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
        WithRequestTimeout(500).
        WithClientName("my-app-client")

    var err error
    client, err = glide.NewClient(cfg)
    if err != nil {
        log.Fatal("Failed to create client:", err)
    }
}

func handleRequest(w http.ResponseWriter, r *http.Request) {
    data, err := client.Get(r.Context(), "key")
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    w.Write([]byte(data))
}

func main() {
    http.HandleFunc("/", handleRequest)
    
    // Graceful shutdown
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    
    go func() {
        <-sigChan
        client.Close()
        os.Exit(0)
    }()
    
    log.Fatal(http.ListenAndServe(":8080", nil))
}
```

### 2. Request Timeout Configuration

**Production-Ready Configuration:**

For a complete production-ready configuration example with all recommended settings (timeouts, retry strategies, throughput tuning, AZ affinity), see `assets/config-templates/go-config.go`.

**✅ Always Configure Timeouts**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

cfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithRequestTimeout(500) // milliseconds

client, err := glide.NewClient(cfg)
```

**Timeout Guidelines**:
- Real-time apps (sub-10ms): 20-50ms
- Web APIs: 200-500ms
- Background jobs: 1000-5000ms

## Batching Patterns

### Pipeline (Non-Atomic)

**❌ Sequential Operations**
```go
// 3 network roundtrips (~15ms)
user1, _ := client.Get(ctx, "user:1")
user2, _ := client.Get(ctx, "user:2")
user3, _ := client.Get(ctx, "user:3")
```

**✅ Pipeline Batch**
```go
import "github.com/valkey-io/valkey-glide/go/v2/pipeline"

// 1 network roundtrip (~5ms)
batch := pipeline.NewStandaloneBatch(false) // false = pipeline (non-atomic)
batch.Get("user:1")
batch.Get("user:2")
batch.Get("user:3")

results, err := client.Exec(ctx, *batch, false)
if err != nil {
    log.Fatal(err)
}

user1 := results[0].(string)
user2 := results[1].(string)
user3 := results[2].(string)
```

### Transaction (Atomic)

**✅ Atomic Operations**
```go
import "github.com/valkey-io/valkey-glide/go/v2/pipeline"

transaction := pipeline.NewStandaloneBatch(true) // true = transaction (atomic)
transaction.Set("balance:user:123", "100")
transaction.Incr("transaction:count")
transaction.Set("last_update", fmt.Sprintf("%d", time.Now().Unix()))

results, err := client.Exec(ctx, *transaction, false)
if err != nil {
    log.Fatal(err)
}
// All commands succeed or all fail
```

### Batch Size Guidelines

```go
import "github.com/valkey-io/valkey-glide/go/v2/pipeline"

// Optimal: 10-100 commands
batch := pipeline.NewStandaloneBatch(false)
for i := 0; i < 50; i++ {
    batch.Get(fmt.Sprintf("key:%d", i))
}
results, err := client.Exec(ctx, *batch, false)

// Avoid: >1000 commands (split into smaller batches)
keys := make([]string, 5000)
for i := range keys {
    keys[i] = fmt.Sprintf("key:%d", i)
}

batchSize := 100
for i := 0; i < len(keys); i += batchSize {
    batch := pipeline.NewStandaloneBatch(false)
    end := i + batchSize
    if end > len(keys) {
        end = len(keys)
    }
    
    for _, key := range keys[i:end] {
        batch.Get(key)
    }
    
    results, err := client.Exec(ctx, *batch, false)
    if err != nil {
        log.Printf("Batch failed: %v", err)
        continue
    }
    // Process results
}
```

## Concurrent Operations

### Goroutines with Channels

**✅ Concurrent Independent Operations**
```go
type result struct {
    key   string
    value string
    err   error
}

// Execute concurrently (wall-clock time = max latency)
ch := make(chan result, 3)

go func() {
    val, err := client.Get(ctx, "user:123")
    ch <- result{"user", val, err}
}()

go func() {
    val, err := client.LRange(ctx, "posts:123", 0, -1)
    ch <- result{"posts", strings.Join(val, ","), err}
}()

go func() {
    val, err := client.LRange(ctx, "comments:123", 0, -1)
    ch <- result{"comments", strings.Join(val, ","), err}
}()

// Collect results
for i := 0; i < 3; i++ {
    res := <-ch
    if res.err != nil {
        log.Printf("%s failed: %v", res.key, res.err)
    } else {
        log.Printf("%s: %s", res.key, res.value)
    }
}
```

**Note**: Batching is usually more efficient than goroutines for multiple operations.

### errgroup for Error Handling

**✅ Handle Partial Failures**
```go
import "golang.org/x/sync/errgroup"

g, ctx := errgroup.WithContext(ctx)

var user, posts, comments string

g.Go(func() error {
    var err error
    user, err = client.Get(ctx, "user:123")
    return err
})

g.Go(func() error {
    var err error
    postsSlice, err := client.LRange(ctx, "posts:123", 0, -1)
    posts = strings.Join(postsSlice, ",")
    return err
})

g.Go(func() error {
    var err error
    commentsSlice, err := client.LRange(ctx, "comments:123", 0, -1)
    comments = strings.Join(commentsSlice, ",")
    return err
})

if err := g.Wait(); err != nil {
    log.Printf("One or more operations failed: %v", err)
}
```

## Cluster Patterns

### Hash Tags for Co-location

**❌ Keys on Different Slots**
```go
// Multiple roundtrips to different shards
values, _ := client.MGet(ctx, []string{
    "user:123:name", "user:123:email", "user:123:age",
})
```

**❌ Related Entity Keys Without Hash Tags (Cluster)**
```go
// Geo/location data — each key lands on a different slot
client.Set("entity:"+entityId+":lat", latStr)
client.Set("entity:"+entityId+":lon", lonStr)
client.Set("entity:"+entityId+":updated", tsStr)

// Time-series — related buckets scattered across shards
client.LPush("ts:"+seriesId+":"+bucket, []string{encoded})
client.Set("ts:"+seriesId+":latest", encoded)
```

**✅ Hash Tags for Same Slot**
```go
// Single roundtrip - all keys on same shard
values, _ := client.MGet(ctx, []string{
    "{user:123}:name", "{user:123}:email", "{user:123}:age",
})

// Geo keys with hash tags — all co-located on same slot
client.Set("{entity:"+entityId+"}:lat", latStr)
client.Set("{entity:"+entityId+"}:lon", lonStr)
client.Set("{entity:"+entityId+"}:updated", tsStr)

// Time-series with hash tags — related buckets on same slot
client.LPush("{ts:"+seriesId+"}:"+bucket, []string{encoded})
client.Set("{ts:"+seriesId+"}:latest", encoded)

// Set related data
data := map[string]string{
    "{user:123}:name":        "John",
    "{user:123}:email":       "john@example.com",
    "{user:123}:preferences": `{"theme":"dark"}`,
}
client.MSet(ctx, data)
```

### Cluster Scan

**✅ Iterate All Keys in Cluster**
```go
import (
    "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/models"
)

cursor := models.NewClusterScanCursor()
var allKeys []string

for {
    newCursor, keys, err := clusterClient.Scan(ctx, cursor, &models.ScanOptions{
        Match: "user:*",
        Count: 100,
    })
    if err != nil {
        log.Fatal(err)
    }
    
    allKeys = append(allKeys, keys...)
    cursor = newCursor
    
    if cursor.IsFinished() {
        break
    }
}

log.Printf("Found %d keys", len(allKeys))
```

## AZ Affinity Configuration

**✅ Enable for Read-Heavy Workloads**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

cfg := config.NewClusterClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "cluster.endpoint.cache.amazonaws.com", Port: 6379}).
    WithReadFrom(config.AzAffinity).
    WithClientAZ("us-east-1a"). // Your application's AZ
    WithRequestTimeout(500)

client, err := glide.NewClusterClient(cfg)
if err != nil {
    log.Fatal(err)
}
```

**Requirements**:
- Valkey 8.0+ or ElastiCache for Valkey 7.2+
- Cluster mode with replicas
- Read-heavy workload (>80% reads)

## Error Handling

### Typed Error Handling

**✅ Handle Specific Error Types**
```go
import (
    "errors"
    "github.com/valkey-io/valkey-glide/go/v2"
)

value, err := client.Get(ctx, "key")
if err != nil {
    var timeoutErr *glide.TimeoutError
    var connErr *glide.ConnectionError
    var reqErr *glide.RequestError
    
    switch {
    case errors.As(err, &timeoutErr):
        // Retry with exponential backoff
        log.Printf("Request timed out: %v", err)
    case errors.As(err, &connErr):
        // Circuit breaker pattern
        log.Printf("Connection failed: %v", err)
    case errors.As(err, &reqErr):
        // Server error - check command syntax
        log.Printf("Request error: %v", err)
    default:
        // Unknown error
        log.Printf("Unexpected error: %v", err)
    }
}
```

### Retry Strategy Configuration

**✅ Configure Connection Backoff**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

cfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithReconnectStrategy(config.NewBackoffStrategy(10, 500, 2)). // retries, factor, exponentBase
    WithRequestTimeout(500)

client, err := glide.NewClient(cfg)
```

## Advanced Patterns

### Context for Timeouts

**✅ Per-Operation Timeouts**
```go
// Operation-specific timeout
ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
defer cancel()

value, err := client.Get(ctx, "key")
if err != nil {
    if errors.Is(err, context.DeadlineExceeded) {
        log.Println("Operation timed out")
    }
}
```

### Blocking Commands

**✅ Dedicated Client for Blocking Operations**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

// Separate client for blocking commands
blockingCfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithRequestTimeout(30000). // 30 seconds
    WithClientName("queue-worker")

blockingClient, err := glide.NewClient(blockingCfg)
if err != nil {
    log.Fatal(err)
}

// Use for BLPOP, BRPOP, etc.
item, err := blockingClient.BLPop(ctx, []string{"queue"}, 30)

// Regular client for other operations
regularCfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithRequestTimeout(500).
    WithClientName("app-client")

regularClient, err := glide.NewClient(regularCfg)
```

### Throughput Tuning

GLIDE uses a single multiplexed connection, not a traditional connection pool. For high-throughput, ensure proper inflight request management.

**✅ High-Throughput Configuration**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

// The Go wrapper does not currently expose inflightRequestsLimit (default: 1000).
// It is managed at the Rust core level. Other wrappers (Node.js, Python,
// Java) allow configuring this value directly.
// For high-throughput in Go, focus on batching and concurrency patterns.
cfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "localhost", Port: 6379}).
    WithRequestTimeout(500)

client, err := glide.NewClient(cfg)
```

### Serverless/Lambda Optimization

**❌ Per-Invocation Client in Handler**
```go
func HandleLambdaRequest(event map[string]string) string {
    endpoint := os.Getenv("CACHE_ENDPOINT")
    cfg := config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: endpoint, Port: 6379}).
        WithRequestTimeout(1000)

    client, _ := glide.NewClient(cfg)
    defer client.Close()

    result, _ := client.Get(context.Background(), "request:" + event["requestId"])
    return result
}
```

**✅ Persistent Client with Lazy Connection**
```go
import (
    glide "github.com/valkey-io/valkey-glide/go/v2"
    "github.com/valkey-io/valkey-glide/go/v2/config"
)

// Package-level client persists across warm invocations
var lambdaClient *glide.Client

func ensureClient() error {
    if lambdaClient != nil {
        return nil
    }
    cfg := config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: os.Getenv("CACHE_ENDPOINT"), Port: 6379}).
        WithRequestTimeout(500).
        WithLazyConnect(true). // Defer TCP+TLS handshake until first command
        WithClientName("lambda-handler").
        WithReconnectStrategy(config.NewBackoffStrategy(3, 500, 2))

    var err error
    lambdaClient, err = glide.NewClient(cfg)
    return err
}

func HandleLambdaRequest(event map[string]string) (string, error) {
    if err := ensureClient(); err != nil {
        return "", fmt.Errorf("cache init: %w", err)
    }

    result, err := lambdaClient.Get(context.Background(), "request:" + event["requestId"])
    if err != nil {
        return "", fmt.Errorf("cache read: %w", err)
    }
    return result, nil
}
```

**`LazyConnect`** defers the TCP+TLS handshake until the first command, reducing cold start by ~2-5ms. Combined with a package-level variable, the connection persists across warm invocations.

## Data Structures

### Hash vs JSON

**❌ Large JSON Strings**
```go
import "encoding/json"

// Inefficient - must fetch/parse entire object
user := map[string]interface{}{"name": "John", "email": "john@example.com"}
data, _ := json.Marshal(user)
client.Set(ctx, "user:123", string(data))

jsonStr, _ := client.Get(ctx, "user:123")
var parsed map[string]interface{}
json.Unmarshal([]byte(jsonStr), &parsed)
fmt.Println(parsed["name"]) // Had to fetch everything
```

**✅ Hash Data Structure**
```go
// Efficient - fetch only needed fields
fields := map[string]string{
    "name":  "John",
    "email": "john@example.com",
    "age":   "30",
}
client.HSet(ctx, "user:123", fields)

// Retrieve single field
name, _ := client.HGet(ctx, "user:123", "name")

// Retrieve multiple fields
values, _ := client.HMGet(ctx, "user:123", []string{"name", "email"})

// Retrieve all fields
allFields, _ := client.HGetAll(ctx, "user:123")
```

## Monitoring

### OpenTelemetry Integration

**✅ Enable Tracing**
```go
import "github.com/valkey-io/valkey-glide/go/v2/otel"

// Initialize once at application startup
otel.Init(&otel.Configuration{
    Traces: &otel.TracesConfig{
        Endpoint:         "http://localhost:4318/v1/traces",
        SamplePercentage: 1, // 1% sampling for production
    },
    Metrics: &otel.MetricsConfig{
        Endpoint: "http://localhost:4318/v1/metrics",
    },
})
```

### Logging Configuration

**✅ Production Logging**
```go
import "github.com/valkey-io/valkey-glide/go/v2/logger"

// Production: minimal logging
logger.SetLoggerConfig(logger.Warn, "glide.log")

// Development: verbose logging
logger.SetLoggerConfig(logger.Info, "")

// Maximum performance: errors only
logger.SetLoggerConfig(logger.Error, "")
```

## SCAN vs Valkey-Search

### SCAN for Key Discovery (Scalability Concern)

**❌ SCAN Loop for Pattern-Based Key Lookup**
```go
// O(N) full keyspace iteration — degrades as dataset grows
var matched []string
cursor := "0"
for {
    result, _ := client.Scan(cursor, config.ScanOptions{Match: pattern, Count: 100})
    cursor = result.Cursor
    matched = append(matched, result.Keys...)
    if cursor == "0" {
        break
    }
}
// Then individually fetching each matched key compounds the problem
for _, key := range matched {
    val, _ := client.Get(key)
    // ...
}
```

**✅ Valkey-Search Index for Efficient Queries**
```go
// Create index once at startup
client.FTCreate("idx:content", &ft.CreateOptions{
    Prefix: []string{"content:"},
    Schema: []ft.FieldSchema{
        {Name: "title", Type: ft.Text},
        {Name: "tags", Type: ft.Tag},
    },
})

// O(K) where K = result count, independent of total keyspace size
results, _ := client.FTSearch("idx:content", "@title:"+searchTerm)
```

**Note**: SCAN is appropriate for one-time migrations or admin tasks. For application-level search or filtering, Valkey-Search (`FT.*`) scales independently of keyspace size.

## Common Pitfalls

### 1. Not Checking Errors

**❌ Ignoring errors**
```go
value, _ := client.Get(ctx, "key") // Ignoring error!
fmt.Println(value)
```

**✅ Proper error handling**
```go
value, err := client.Get(ctx, "key")
if err != nil {
    log.Printf("Failed to get key: %v", err)
    return
}
fmt.Println(value)
```

### 2. Not Using defer for Cleanup

**❌ Missing cleanup**
```go
import "github.com/valkey-io/valkey-glide/go/v2"

client, err := glide.NewClient(config)
if err != nil {
    return err
}
// Forgot to close - resource leak!
```

**✅ Proper cleanup**
```go
import "github.com/valkey-io/valkey-glide/go/v2"

client, err := glide.NewClient(config)
if err != nil {
    return err
}
defer client.Close()
```

### 3. Creating Client in Loop

**❌ Client per iteration**
```go
import "github.com/valkey-io/valkey-glide/go/v2"

for _, item := range items {
    client, _ := glide.NewClient(config) // NEVER!
    client.Set(ctx, item.Key, item.Value)
    client.Close()
}
```

**✅ Reuse client**
```go
import "github.com/valkey-io/valkey-glide/go/v2"

client, err := glide.NewClient(config)
if err != nil {
    log.Fatal(err)
}
defer client.Close()

for _, item := range items {
    if err := client.Set(ctx, item.Key, item.Value); err != nil {
        log.Printf("Failed to set %s: %v", item.Key, err)
    }
}
```

### 4. Not Using Context

**❌ Missing context**
```go
value, err := client.Get(nil, "key") // nil context!
```

**✅ Proper context**
```go
ctx := context.Background()
value, err := client.Get(ctx, "key")
```

## Goroutine Safety

### Client is Goroutine-Safe

**✅ Share Client Across Goroutines**
```go
import "github.com/valkey-io/valkey-glide/go/v2"

// Single client can be safely used by multiple goroutines
var client *glide.Client

func handleRequest1() {
    client.Get(ctx, "key1") // Goroutine-safe
}

func handleRequest2() {
    client.Get(ctx, "key2") // Goroutine-safe
}
```

### Batch is NOT Goroutine-Safe

**❌ Sharing Batch Across Goroutines**
```go
import "github.com/valkey-io/valkey-glide/go/v2/pipeline"

batch := pipeline.NewStandaloneBatch(false)

// Goroutine 1
go func() {
    batch.Get("key1") // NOT goroutine-safe!
}()

// Goroutine 2
go func() {
    batch.Get("key2") // NOT goroutine-safe!
}()
```

**✅ Create Batch Per Goroutine**
```go
import "github.com/valkey-io/valkey-glide/go/v2/pipeline"

// Goroutine 1
go func() {
    batch := pipeline.NewStandaloneBatch(false)
    batch.Get("key1")
    client.Exec(ctx, *batch, false)
}()

// Goroutine 2
go func() {
    batch := pipeline.NewStandaloneBatch(false)
    batch.Get("key2")
    client.Exec(ctx, *batch, false)
}()
```

## Performance Checklist

- [ ] Client created once at startup, not per request
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching used for bulk operations (10-100 commands)
- [ ] Goroutines for concurrent independent operations
- [ ] Hash tags for related keys in cluster
- [ ] AZ affinity enabled for read-heavy workloads
- [ ] Error handling with typed errors
- [ ] Connection backoff configured
- [ ] Dedicated client for blocking commands
- [ ] Hash data structures for structured data
- [ ] defer for cleanup
- [ ] Context used for all operations
- [ ] Goroutine safety considerations addressed
- [ ] OpenTelemetry enabled for monitoring
- [ ] Logging set to warn/error for production
- [ ] LazyConnect enabled for serverless/Lambda entry points
