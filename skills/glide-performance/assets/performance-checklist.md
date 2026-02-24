# GLIDE Performance Optimization Checklist

Quick reference checklist for reviewing Valkey GLIDE client implementations.

## Critical Issues (Fix Immediately)

- [ ] **Client Reuse**: Client created once at startup, NOT per request
- [ ] **Request Timeout**: Timeout configured (default is 250ms; 500ms recommended for web apps)
- [ ] **Error Handling**: Try-catch blocks around client operations
- [ ] **Connection Backoff**: Retry strategy configured for resilience

## High-Impact Optimizations

- [ ] **Batching**: Batch used for bulk operations (10-100 commands, atomic for transactions, non-atomic for pipelines)
- [ ] **Sequential Operations**: Replaced with batching or concurrent execution
- [ ] **Blocking Commands**: Dedicated client for BLPOP/BRPOP/BLMOVE/etc.
- [ ] **Large Batches**: Batch sizes kept under 1000 commands

## Cluster Optimizations

- [ ] **Hash Tags**: Related keys use `{tag}` syntax for co-location
- [ ] **Multi-Key Commands**: MGET/MSET used instead of multiple GET/SET
- [ ] **Cluster Scan**: Proper cursor handling for iterating keys

## Cost Optimization

- [ ] **AZ Affinity**: Enabled for read-heavy workloads (>80% reads)
- [ ] **Read Strategy**: Appropriate readFrom configuration
- [ ] **Data Transfer**: Cross-AZ traffic minimized

## Data Optimization

- [ ] **Value Size**: Values kept under 100KB
- [ ] **Hash Structures**: Used for structured data instead of JSON strings
- [ ] **Compression**: Applied for values >10KB
- [ ] **Key Design**: Efficient key naming and organization

## Configuration

- [ ] **Timeout Settings**: Appropriate for use case (20-50ms real-time, 200-500ms web, 1000-5000ms batch)
- [ ] **Throughput Tuning**: inflightRequestsLimit tuned for throughput (GLIDE uses a single multiplexed connection, not a traditional pool)
- [ ] **Client Name**: Descriptive name set for debugging
- [ ] **Lazy Connect**: Enabled for serverless/Lambda deployments

## Monitoring & Observability

- [ ] **OpenTelemetry**: Tracing enabled with appropriate sampling
- [ ] **Logging**: Set to warn/error for production
- [ ] **Metrics**: P99 latency, throughput, error rate monitored
- [ ] **Alerting**: Alerts configured for timeouts and connection errors

## Language-Specific

### Node.js/TypeScript
- [ ] Promise.all() for concurrent operations
- [ ] Proper await on client creation
- [ ] TypeScript types used for configuration
- [ ] Graceful shutdown on SIGTERM

### Python
- [ ] Async client for async frameworks, sync for sync
- [ ] asyncio.gather() for concurrent operations (async)
- [ ] Context managers for automatic cleanup
- [ ] Type hints used

### Java
- [ ] CompletableFuture for concurrent operations
- [ ] Try-with-resources for automatic cleanup
- [ ] Proper exception handling
- [ ] Thread pool sizing

### Go
- [ ] Goroutines for concurrent operations
- [ ] Defer for cleanup
- [ ] Context for timeouts
- [ ] Error handling with proper checks

### PHP
- [ ] Client created once, reused via global/static variable
- [ ] MULTI/EXEC or pipeline for bulk operations
- [ ] ValkeyGlideException try-catch around operations
- [ ] Reconnection strategy with exponential backoff
- [ ] lazy_connect enabled for serverless/PHP-FPM cold starts
- [ ] Blocking commands avoided (use polling alternatives)
- [ ] Hash structures used instead of JSON strings

## Common Anti-Patterns to Avoid

- ❌ Creating client per request
- ❌ No request timeout configured
- ❌ Sequential operations without batching
- ❌ Blocking commands on shared client
- ❌ Batch sizes >1000 operations
- ❌ Missing error handling
- ❌ No retry strategy
- ❌ Large JSON strings instead of Hash structures
- ❌ Ignoring connection errors
- ❌ No monitoring/observability

## Performance Targets

These targets are general guidelines based on typical deployments. Your actual performance will vary based on infrastructure, network conditions, data sizes, and operation types. Always benchmark in your specific environment.

| Metric | Target | Use Case |
|--------|--------|----------|
| P99 Latency | <10ms | Real-time applications (requires low-latency network) |
| P99 Latency | <50ms | Web applications (typical network conditions) |
| P99 Latency | <500ms | Background jobs |
| Throughput | >10K ops/sec | Standard workloads (single node) |
| Throughput | >100K ops/sec | High-performance workloads (cluster mode, optimized) |
| Connection Errors | <0.1% | All workloads |
| Timeout Rate | <1% | All workloads |

**Note**: These targets assume properly configured infrastructure, optimized client settings, and appropriate network conditions. Benchmark your specific workload to establish realistic targets.

## Quick Wins (5-Minute Fixes)

1. **Add Request Timeout**: Set `requestTimeout: 500` in configuration (default is 250ms)
2. **Enable Client Reuse**: Move client creation to startup
3. **Add Error Handling**: Wrap operations in try-catch
4. **Configure Retry**: Add reconnect/backoff strategy configuration
5. **Enable Logging**: Set appropriate log level

## Before Deploying to Production

- [ ] Load testing completed
- [ ] P99 latency meets targets
- [ ] Error handling tested with network failures
- [ ] Monitoring dashboards created
- [ ] Alerts configured
- [ ] Runbook documented
- [ ] Rollback plan prepared
- [ ] Connection limits verified
- [ ] Timeout values validated
- [ ] Retry strategy tested

## Resources

- [GLIDE Wiki](https://glide.valkey.io/)
- [Batching Guide](https://glide.valkey.io/how-to/send-batch-commands/)
- [Connection Management](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#connection-management)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
- [Examples](https://github.com/valkey-io/valkey-glide/tree/main/examples)
