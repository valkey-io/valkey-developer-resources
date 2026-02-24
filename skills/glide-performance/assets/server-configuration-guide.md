# Valkey/ElastiCache Server Configuration Guide

This guide helps you optimize your Valkey/ElastiCache infrastructure based on code patterns detected in your application. The GLIDE Performance Optimization Skill analyzes your code to provide these recommendations.

## Table of Contents

- [Cluster Architecture Selection](#cluster-architecture-selection)
- [Read/Write Workload Analysis](#readwrite-workload-analysis)
- [Server-Side Configuration Tuning](#server-side-configuration-tuning)
- [ElastiCache-Specific Recommendations](#elasticache-specific-recommendations)
- [Configuration Examples](#configuration-examples)

## Cluster Architecture Selection

### When to Use Cluster Mode

The skill analyzes your code patterns to determine if cluster mode would benefit your application:

**Indicators for Cluster Mode:**

- **Multi-key operations across different keys**: Code shows operations on many unrelated keys
- **High throughput requirements**: Code patterns suggest >100K ops/sec
- **Horizontal scaling needs**: Single-node memory limits are insufficient
- **Hash tag usage**: Code already uses `{tag}` syntax indicating cluster-aware design
- **Large dataset**: Code accesses thousands of unique keys

**Example Detection:**
```javascript
// Detected pattern: Many unrelated keys
await client.get('user:123');
await client.get('session:456');
await client.get('product:789');
await client.get('order:321');
// Recommendation: Cluster mode for horizontal scaling
```

### When to Use Standalone Mode

**Indicators for Standalone Mode:**

- **Single-key or related-key operations**: Most operations on same key or related keys
- **Low to moderate throughput**: <50K ops/sec
- **Simple deployment requirements**: No need for horizontal scaling
- **Transactions across multiple keys**: Heavy use of MULTI/EXEC without hash tags

**Example Detection:**
```python
# Detected pattern: Related keys, transactions
transaction = Batch(is_atomic=True)
transaction.set('user:123:name', 'John')
transaction.set('user:123:email', 'john@example.com')
transaction.set('user:123:age', '30')
await client.exec(transaction, raise_on_error=True)
# Recommendation: Standalone mode sufficient
```

### Cluster Slot Distribution Analysis

When cluster mode is recommended, the skill analyzes key distribution:

```go
// Detected pattern: Uneven key distribution
for i := 0; i < 1000; i++ {
    client.Set(ctx, fmt.Sprintf("user:%d", i), data)
}
// Recommendation: 3-6 shards for even distribution
```

## Read/Write Workload Analysis

The skill analyzes command patterns to detect read-heavy vs write-heavy workloads and recommends routing strategies.

### Read-Heavy Workloads (>80% reads)

**Detected Commands**: GET, MGET, HGET, HGETALL, SMEMBERS, LRANGE, ZRANGE

**Recommendations:**

1. **Enable Read Replicas**: Route reads to replicas to offload primary
2. **Configure Read Strategy**: Use Prefer Replica or AZ Affinity
3. **Increase Replica Count**: Add replicas for read scaling
4. **Enable AZ Affinity**: Reduce cross-AZ costs for same-AZ reads

**Example Detection:**
```java
// Detected pattern: 90% reads
for (String userId : userIds) {
    client.get("user:" + userId);           // Read
    client.hgetall("profile:" + userId);    // Read
    client.smembers("friends:" + userId);   // Read
}
// Occasional writes
client.set("user:123:lastSeen", timestamp); // Write (10%)

// Recommendation: readFrom = PREFER_REPLICA (or language equivalent), add 2 replicas per shard
```

### Write-Heavy Workloads (>50% writes)

**Detected Commands**: SET, MSET, HSET, SADD, LPUSH, ZADD, INCR, DECR, DEL

**Recommendations:**

1. **Primary-Only Routing**: Use Primary read strategy to avoid replication lag
2. **Optimize Write Performance**: Increase primary node size
3. **Batching**: Use pipelining/transactions to reduce write roundtrips
4. **Minimal Replicas**: Use replicas only for HA, not read scaling

**Example Detection:**
```php
// Detected pattern: 70% writes
$client->set("counter:$id", $value);        // Write
$client->incr("stats:views");               // Write
$client->lpush("queue:tasks", $task);       // Write
$client->hset("session:$id", $data);        // Write
$client->get("config:settings");            // Read (30%)

// Recommendation: readFrom = PRIMARY (or language equivalent), focus on write optimization
```

### Balanced Workloads (40-60% reads/writes)

**Recommendations:**

1. **Mixed Routing Strategy**: Use Primary read strategy for consistency
2. **Moderate Replica Count**: 1-2 replicas for HA
3. **Optimize Both Paths**: Batching for writes, inflight request tuning for reads

**Example Detection:**
```typescript
// Detected pattern: 50/50 read/write
await client.get(`user:${id}`);              // Read
await client.set(`user:${id}:status`, 'active'); // Write
await client.hgetall(`profile:${id}`);       // Read
await client.incr(`counter:${id}`);          // Write

// Recommendation: readFrom = PRIMARY (or language equivalent), 1 replica for HA
```

## Server-Side Configuration Tuning

Based on detected code patterns, the skill recommends server-side Valkey configuration parameters.

### Memory Eviction Policy (`maxmemory-policy`)

**Cache-Like Access Patterns:**

Detected: Frequent SET with TTL, GET operations, no persistence requirements

```python
# Detected pattern: Cache usage
await client.setex('cache:user:123', 3600, data)
await client.get('cache:product:456')
await client.expire('cache:session:789', 1800)

# Recommendation: maxmemory-policy = allkeys-lru
```

**Recommended**: `allkeys-lru` or `allkeys-lfu`

**Persistent Data Patterns:**

Detected: SET without TTL, critical data, no eviction acceptable

```java
// Detected pattern: Persistent data
client.set("user:123:email", "john@example.com");
client.hset("account:456", "balance", "1000.00");
client.sadd("permissions:admin", "user:123");

// Recommendation: maxmemory-policy = noeviction
```

**Recommended**: `noeviction` (with monitoring for memory limits)

**Volatile Keys Only:**

Detected: Mix of persistent and TTL keys, only TTL keys should be evicted

```go
// Detected pattern: Mixed TTL usage
client.Set(ctx, "user:123:name", "John", 0)           // No TTL
client.Set(ctx, "session:456", token, 30*time.Minute) // TTL
client.Set(ctx, "cache:789", data, 1*time.Hour)       // TTL

// Recommendation: maxmemory-policy = volatile-lru
```

**Recommended**: `volatile-lru` or `volatile-lfu`

### Connection Timeout (`timeout`)

**Long-Lived Connection Patterns:**

Detected: Persistent connections, infrequent operations, connection reuse

```php
// Detected pattern: Long-lived connections
global $valkeyClient; // Reused across requests
// Operations every few seconds

// Recommendation: timeout = 300 (5 minutes)
```

**Recommended**: `timeout = 300` (5 minutes) or higher

**Short-Lived Connection Patterns:**

Detected: Frequent reconnections, serverless/Lambda usage

```typescript
// Detected pattern: Serverless/Lambda
const client = await GlideClient.createClient({
    lazyConnect: true // Lambda cold starts
});

// Recommendation: timeout = 60 (1 minute)
```

**Recommended**: `timeout = 60` (1 minute)

### TCP Keep-Alive (`tcp-keepalive`)

**Detected Long Idle Periods:**

```python
# Detected pattern: Idle connections with occasional bursts
# Long gaps between operations

# Recommendation: tcp-keepalive = 60
```

**Recommended**: `tcp-keepalive = 60` (seconds)

**Benefit**: Prevents firewall/NAT timeout on idle connections

### Max Clients (`maxclients`)

**Detected Concurrency Configuration:**

```java
// Detected pattern: High concurrency configuration
GlideClientConfiguration config = GlideClientConfiguration.builder()
    .address(NodeAddress.builder().host("localhost").port(6379).build())
    .requestTimeout(500)
    .inflightRequestsLimit(2000) // High concurrency
    .build();

// Note: ElastiCache sets maxclients = 65000
// Individual nodes support up to 65,000 concurrent client connections
```

**Note**: In ElastiCache, `maxclients` has a value of 65,000. For self-managed Valkey/Redis, the default is 10,000 and can be adjusted. When planning capacity, ensure your total connection count across all application instances stays well below this limit.

**Calculation** (for capacity planning): `total_connections = number_of_app_instances × connections_per_instance`

**Example**:
- 10 app instances
- 100 connections per instance
- Total: 1,000 connections (well within the 65,000 limit)

## ElastiCache-Specific Recommendations

### Node Type Selection

Based on detected memory usage patterns and throughput requirements. These recommendations are starting points - actual node type selection should be based on load testing and cost analysis for your specific workload.

**Memory-Intensive Patterns:**

```javascript
// Detected pattern: Large values, many keys
await client.set('data:1', largeObject); // >10KB values
await client.set('data:2', largeObject);
// ... thousands of keys

// Recommendation: r7g.xlarge or larger (memory-optimized)
// Note: Actual node size depends on total dataset size and access patterns
```

**Recommended Node Types** (AWS ElastiCache):
- **r7g.large**: 13.07 GiB memory
- **r7g.xlarge**: 26.32 GiB memory
- **r7g.2xlarge**: 52.82 GiB memory

**Compute-Intensive Patterns:**

```python
# Detected pattern: High operation rate, small values
for i in range(100000):
    await client.incr(f'counter:{i}')
    await client.get(f'flag:{i}')

# Recommendation: m7g.large or larger (balanced compute/memory)
# Note: Throughput depends on operation types and network conditions
```

**Recommended Node Types** (AWS ElastiCache):
- **m7g.large**: 6.38 GiB memory
- **m7g.xlarge**: 12.93 GiB memory
- **m7g.2xlarge**: 26.04 GiB memory

**Important**: Throughput varies significantly based on operation types (simple vs complex), payload sizes, and network latency. Conduct load testing to validate node type selection.

### Multi-AZ Deployment

**High Availability Requirements Detected:**

```go
// Detected pattern: Critical path operations
userData, err := client.Get(ctx, "user:123")
if err != nil {
    // Application fails without Valkey
    return err
}

// Recommendation: Multi-AZ with automatic failover
```

**Recommended**: Enable Multi-AZ replication for automatic failover

**Non-Critical Usage Detected:**

```php
// Detected pattern: Graceful degradation
try {
    $data = $valkeyClient->get("cache:$id");
} catch (ValkeyGlideException $e) {
    $data = fetchFromDatabase($id); // Fallback
}

// Recommendation: Single-AZ acceptable (cost optimization)
```

**Recommended**: Single-AZ deployment to reduce costs

### Parameter Group Optimization

**Read-Heavy Workload:**

```
# ElastiCache Parameter Group for Read-Heavy Workloads
maxmemory-policy: allkeys-lru
timeout: 300
tcp-keepalive: 60
```

**Write-Heavy Workload:**

```
# ElastiCache Parameter Group for Write-Heavy Workloads
maxmemory-policy: noeviction
timeout: 60
tcp-keepalive: 30
```

**Note**: In ElastiCache, the `maxclients` parameter is fixed at 65,000 and persistence is managed internally.

**Cache Workload:**

```
# ElastiCache Parameter Group for Cache Workloads
maxmemory-policy: allkeys-lfu
timeout: 300
tcp-keepalive: 60
```

### Cluster Mode Configuration

**Shard Count Recommendations:**

Based on detected key distribution and throughput:

```typescript
// Detected pattern: 1M unique keys, even distribution
for (let i = 0; i < 1000000; i++) {
    await client.set(`key:${i}`, value);
}

// Recommendation: 3-6 shards for optimal distribution
```

**Shard Count Guidelines**:
- **1-10K keys**: 1 shard (standalone) - sufficient for most small applications
- **10K-100K keys**: 2-3 shards - provides horizontal scaling
- **100K-1M keys**: 3-6 shards - balances distribution and management overhead
- **1M+ keys**: 6-15 shards - for large-scale deployments

**Note**: These are starting points. Actual shard count should consider throughput requirements, data distribution patterns, and operational complexity. More shards increase management overhead but improve horizontal scalability.

**Replicas Per Shard:**

Based on detected read/write ratio:

- **Read-heavy (>80% reads)**: 2-3 replicas per shard
- **Balanced (40-60% reads)**: 1-2 replicas per shard
- **Write-heavy (>50% writes)**: 1 replica per shard (HA only)

## Configuration Examples

### Example 1: High-Traffic Web Application (Read-Heavy)

**Detected Code Pattern:**
```python
# 90% reads, 10% writes, 50K ops/sec
await client.get(f'user:{user_id}')
await client.hgetall(f'profile:{user_id}')
await client.smembers(f'friends:{user_id}')
```

**Recommended ElastiCache Configuration:**

```yaml
Cluster Mode: Enabled
Node Type: r7g.large
Shards: 3
Replicas per Shard: 2
Multi-AZ: Enabled
Parameter Group:
  maxmemory-policy: allkeys-lru
  timeout: 300
  tcp-keepalive: 60
```

**Client Configuration:**
```python
client = await GlideClusterClient.create(
    addresses=[NodeAddress("cluster.endpoint", 6379)],
    request_timeout=500,
    read_from=ReadFrom.AZ_AFFINITY,
    client_az="us-east-1a"
)
```

### Example 2: Real-Time Analytics (Write-Heavy)

**Detected Code Pattern:**
```java
// 70% writes, 30% reads, 100K ops/sec
client.incr("counter:views:" + pageId);
client.zadd("leaderboard", score, userId);
client.lpush("events:stream", event);
```

**Recommended ElastiCache Configuration:**

```yaml
Cluster Mode: Enabled
Node Type: m7g.xlarge
Shards: 6
Replicas per Shard: 1
Multi-AZ: Enabled
Parameter Group:
  maxmemory-policy: noeviction
  timeout: 60
  tcp-keepalive: 30
```

**Client Configuration:**
```java
GlideClusterClient client = GlideClusterClient.createClient(
    GlideClusterClientConfiguration.builder()
        .address(NodeAddress.builder()
            .host("cluster.endpoint")
            .port(6379)
            .build())
        .requestTimeout(500)
        .readFrom(ReadFrom.PRIMARY)  // Avoid replication lag
        .inflightRequestsLimit(2000)
        .build()
).get();
```

### Example 3: Session Store (Balanced)

**Detected Code Pattern:**
```typescript
// 50% reads, 50% writes, 20K ops/sec
await client.set(`session:${sessionId}`, data, { expiryMode: 'EX', expiry: 3600 });
await client.get(`session:${sessionId}`);
```

**Recommended ElastiCache Configuration:**

```yaml
Cluster Mode: Disabled (Standalone)
Node Type: r7g.large
Replicas: 1
Multi-AZ: Enabled
Parameter Group:
  maxmemory-policy: volatile-lru
  timeout: 300
  tcp-keepalive: 60
```

**Client Configuration:**
```typescript
const client = await GlideClient.createClient({
    addresses: [{ host: 'primary.endpoint', port: 6379 }],
    requestTimeout: 500,
    readFrom: "primary"
});
```

### Example 4: Serverless/Lambda Cache

**Detected Code Pattern:**
```go
// Lambda function, infrequent access, lazy connection
cfg := config.NewClientConfiguration().
    WithAddress(&config.NodeAddress{Host: "endpoint", Port: 6379}).
    WithLazyConnect(true)

client, err := glide.NewClient(cfg)
```

**Recommended ElastiCache Configuration:**

```yaml
Cluster Mode: Disabled (Standalone)
Node Type: t4g.small (cost-optimized)
Replicas: 0 (optional: 1 for HA)
Multi-AZ: Disabled (cost optimization)
Parameter Group:
  maxmemory-policy: allkeys-lru
  timeout: 60
  tcp-keepalive: 30
```

**Client Configuration:**
```go
client, err := glide.NewClient(
    config.NewClientConfiguration().
        WithAddress(&config.NodeAddress{Host: "endpoint", Port: 6379}).
        WithRequestTimeout(500).
        WithReconnectStrategy(config.NewBackoffStrategy(
            3,   // numberOfRetries
            200, // factor (base delay in ms)
            2,   // exponentBase
        )),
)
```

## Monitoring Recommendations

After applying server configuration changes, monitor these metrics:

### Key Metrics to Track

1. **Memory Usage**: Should stay below 80% of `maxmemory`
2. **Evictions**: Should be minimal for `noeviction`, expected for LRU/LFU
3. **Connection Count**: Should stay well below 65,000 (ElastiCache fixed `maxclients`)
4. **CPU Utilization**: Should stay below 90% of available CPU (for single-threaded Valkey/Redis, calculate as 90 / number_of_cores for the `CPUUtilization` metric; use `EngineCPUUtilization` directly on 4+ vCPU nodes)
5. **Network Throughput**: Should not saturate node capacity
6. **Replication Lag**: Should be <1 second for read replicas

### CloudWatch Alarms (ElastiCache)

```yaml
Alarms:
  - Metric: DatabaseMemoryUsagePercentage
    Threshold: 80%
    Action: Alert + consider scaling up
  
  - Metric: CPUUtilization
    Threshold: 90% / number_of_cores (e.g., 45% for 2-vCPU nodes)
    Action: Alert + consider scaling up
  
  - Metric: CurrConnections
    Threshold: 80% of 65,000 (ElastiCache default maxclients)
    Action: Alert + investigate connection leaks or scale out
  
  - Metric: Evictions
    Threshold: >0 (for noeviction policy); set application-appropriate threshold for LRU/LFU policies
    Action: Alert + increase memory
  
  - Metric: ReplicationLag
    Threshold: >1 (seconds)
    Action: Alert + investigate replication issues
```

## Additional Resources

- [ElastiCache Best Practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
- [Valkey Configuration](https://valkey.io/topics/config/)
- [GLIDE Wiki - Connection Management](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#connection-management)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
