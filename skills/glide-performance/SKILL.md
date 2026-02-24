---
name: GLIDE Performance Optimization
description: Expert guidance for optimizing Valkey GLIDE clients across Node.js, Python, Java, Go, and PHP with progressive disclosure
version: 1.0.0
author: Valkey Maintainers
tags:
  - performance
  - optimization
  - valkey
  - glide
  - redis
  - caching
languages:
  - javascript
  - typescript
  - python
  - java
  - go
  - php
---

# GLIDE Performance Optimization Skill

Expert guidance for optimizing Valkey GLIDE clients across Node.js, Python, Java, Go, and PHP. This skill uses progressive disclosure—loading only the content relevant to your current task to minimize context usage.

## How This Skill Works

This skill automatically detects the programming language you're working with and loads language-specific optimization patterns on-demand:

- **Core Principles** (this file): Always loaded, provides universal anti-patterns and optimization strategies
- **Language-Specific Patterns**: Loaded only when reviewing code in that language
  - `reference/nodejs-patterns.md` - Node.js/TypeScript specific guidance
  - `reference/python-patterns.md` - Python async/sync specific guidance  
  - `reference/java-patterns.md` - Java specific guidance
  - `reference/go-patterns.md` - Go specific guidance
  - `reference/php-patterns.md` - PHP specific guidance

**Context Efficiency**: Reviewing Node.js code loads only Node.js patterns. Python/Java/Go/PHP patterns remain unloaded, reducing the amount of context loaded into your AI tool.

## When to Use This Skill

- P99 latencies >100ms or timeout errors
- Migrating from legacy clients (node-redis, redis-py, Jedis, go-redis)
- High cross-AZ data transfer costs in AWS
- High-throughput applications (>100K ops/sec)
- Production performance incidents
- Real-time features requiring sub-10ms latency
- ElastiCache/Valkey cost optimization
- Serverless/Lambda deployments

## Language Detection & Loading

When you review code, this skill detects the language from:

1. **File extensions**: `.js`, `.ts`, `.py`, `.java`, `.go`, `.php`
2. **Import statements**: 
   - Node.js: `import { GlideClient }`, `require('@valkey/valkey-glide')`
   - Python: `from glide import`, `import glide`
   - Java: `import glide.api.*`
   - Go: `import "github.com/valkey-io/valkey-glide/go/v2"`
   - PHP: `use ValkeyGlide`, `use ValkeyGlideCluster`, `new ValkeyGlide()`
3. **Syntax patterns**: Language-specific keywords and structures

**Action Required**: When language is detected, load the corresponding reference file:
- Node.js/TypeScript → Load `.kiro/skills/glide-performance/reference/nodejs-patterns.md`
- Python → Load `.kiro/skills/glide-performance/reference/python-patterns.md`
- Java → Load `.kiro/skills/glide-performance/reference/java-patterns.md`
- Go → Load `.kiro/skills/glide-performance/reference/go-patterns.md`
- PHP → Load `.kiro/skills/glide-performance/reference/php-patterns.md`

## Universal Anti-Patterns (All Languages)

These anti-patterns cause performance issues regardless of language:

### 1. Per-Request Client Creation (CRITICAL)

**Problem**: Creating a new client for each request adds massive connection overhead.

**Impact**: 
- Latency increases
- Connection exhaustion
- Memory leaks from unclosed connections

**Detection**: Look for client creation inside request handlers, loops, or frequently-called functions.

**Fix**: Create client once at application startup, reuse everywhere.

### 2. Missing Request Timeouts

**Problem**: Operations can hang indefinitely without timeouts, causing cascading failures.

**Impact**:
- Requests hang forever on network issues
- Thread/connection exhaustion
- Cascading failures across services

**Detection**: Client configuration missing `requestTimeout` or `timeout` parameter.

**Fix**: Always configure timeouts based on use case:
- Sub-10ms apps: 20-50ms
- Web apps: 200-500ms
- Batch processing: 1000-5000ms

### 3. Sequential Operations (High Latency)

**Problem**: Executing commands one-by-one multiplies network latency (N commands = N × roundtrip time).

**Impact**:
- Latency scales linearly with operation count
- Poor throughput
- Wasted network capacity

**Detection**: Multiple await/get calls in sequence without batching or concurrency.

**Fix**: Use batching (pipeline/transaction) or concurrent execution patterns.

### 4. Blocking Commands on Shared Client

**Problem**: BLPOP, BRPOP, BLMOVE, BZPOPMIN, BZPOPMAX block the connection, preventing other operations.

**Impact**:
- All operations on that client are blocked
- Timeouts on concurrent requests
- Poor resource utilization

**Detection**: Blocking commands (BLPOP, BRPOP, etc.) used on same client as regular commands.

**Fix**: Use dedicated client instance for blocking operations with longer timeout.

### 5. Large Batch Sizes (>1000 operations)

**Problem**: Batches with >1000 operations or >10MB payload cause memory issues and timeouts.

**Impact**:
- Memory pressure
- Request timeouts
- Poor error recovery

**Detection**: Batch/pipeline with >1000 commands or very large payloads.

**Fix**: Keep batches between 10-100 commands for optimal balance.

### 6. Missing Error Handling & Retries

**Problem**: Network failures without retry logic cause immediate failures.

**Impact**:
- Poor reliability
- Unnecessary error propagation
- User-facing failures for transient issues

**Detection**: No try-catch blocks or retry configuration around client operations.

**Fix**: Configure connection backoff and implement retry strategies for transient failures.

## Core Optimization Strategies

### 1. Batching (Pipeline & Transactions)

**Concept**: Execute multiple commands in a single network roundtrip.

**When to Use**:
- Multiple independent commands → Pipeline (non-atomic)
- Atomic operations → Transaction (atomic)
- Bulk data operations (MGET, MSET)

**Impact**: Reduces latency from N × roundtrip to 1 × roundtrip. For example, with 5ms network latency, 10 sequential operations take ~50ms, while a single batched operation takes ~5ms.

**Batch Size Guidelines**:
- Optimal: 10-100 commands (balances latency reduction with memory usage)
- Avoid: >1000 commands or >10MB payload (can cause timeouts and memory pressure)

### 2. Cluster-Aware Operations

**Hash Tags for Co-location**: Use `{tag}` syntax to ensure related keys map to same slot.

**Example**: `{user:123}:name`, `{user:123}:email`, `{user:123}:age` all map to same slot.

**Benefit**: Single roundtrip for multi-key operations on related data.

### 3. AZ Affinity (Cost Optimization)

**Concept**: Route read operations to replicas in same availability zone.

**Requirements**:
- Valkey 8.0+ or AWS ElastiCache for Valkey 7.2+
- Cluster mode with replicas
- Read-heavy workload (>80% reads)

**Impact**:
- Lower read latency
- Reduced cross-AZ data transfer costs
- Improved read throughput

**When NOT to use**:
- Write-heavy workloads
- Strong read consistency required
- Single-AZ deployments

### 4. Async/Concurrent Patterns

**Concept**: Execute independent operations concurrently instead of sequentially.

**Benefit**: Reduces wall-clock time from sum(latencies) to max(latencies).

**Note**: Batching is usually more efficient than concurrent individual operations.

### 5. Data Size Optimization

**Guidelines**:
- Keep values <100KB
- Use compression for values >10KB
- Split large objects across keys
- Use Hash data structures for structured data instead of JSON strings

## Valkey Module Detection & Optimization

Valkey modules extend core functionality with specialized data structures and operations. This skill detects module usage and provides module-specific optimization recommendations.

### Supported Modules

**Valkey-Search (FT.*)**: Full-text search and secondary indexing
**Valkey-JSON (JSON.*)**: Native JSON document storage and manipulation
**Valkey-BloomFilter (BF.*, CF.*, CMS.*, TOPK.*)**: Probabilistic data structures

### Module Detection

The skill automatically detects module usage through command patterns:

- `FT.SEARCH`, `FT.CREATE`, `FT.AGGREGATE` → Valkey-Search
- `JSON.GET`, `JSON.SET`, `JSON.MGET` → Valkey-JSON
- `BF.ADD`, `BF.EXISTS`, `CF.ADD` → Valkey-BloomFilter

### Common Module Anti-Patterns

**Valkey-Search:**
- Missing index definitions before queries
- Inefficient query patterns (e.g., wildcard prefix searches)
- Lack of result pagination for large result sets
- Not using `FT.AGGREGATE` for aggregation queries

**Valkey-JSON:**
- Using `JSON.GET` with full document retrieval instead of path-based queries
- Not leveraging `JSON.MGET` for batch operations
- Storing large JSON documents (>100KB) without splitting
- Missing `JSON.NUMINCRBY` for atomic numeric updates

**Valkey-BloomFilter:**
- Incorrect false-positive rate configuration
- Missing capacity planning (initial size too small)
- Not using Cuckoo Filters (`CF.*`) when deletions are needed
- Inefficient batch operations (sequential `BF.ADD` instead of `BF.MADD`)

### Module Recommendations

When the skill detects patterns that would benefit from modules:

**Complex JSON Operations Without Valkey-JSON:**
- Detecting `GET` + JSON parsing + modification + `SET` patterns
- Recommendation: Use `JSON.SET` with path syntax for atomic updates

**Full-Text Search Implemented with SCAN:**
- Detecting `SCAN` + pattern matching for text search
- Recommendation: Use Valkey-Search with `FT.CREATE` index and `FT.SEARCH`

**Set Membership Checks at Scale:**
- Detecting large `SISMEMBER` operations or `SMEMBERS` + filtering
- Recommendation: Use Bloom Filters (`BF.EXISTS`) for probabilistic membership

### Configuration Guidance

**Valkey-Search Index Optimization:**
- Use appropriate field types (TEXT, NUMERIC, TAG, GEO)
- Configure `STOPWORDS` for language-specific optimization
- Set `MAXPREFIXEXPANSIONS` to limit wildcard query cost
- Use `SORTBY` with indexed fields for efficient sorting

**Valkey-JSON Memory Settings:**
- Configure `json-max-size` to prevent oversized documents
- Use path-based operations to minimize data transfer
- Leverage `JSON.FORGET` to remove unused paths

**Valkey-BloomFilter Capacity Planning:**
- Calculate initial capacity based on expected cardinality
- Set error rate based on use case (0.01 for general, 0.001 for critical)
- Use `BF.RESERVE` to pre-allocate with optimal parameters

## Server Configuration Recommendations

The skill analyzes your code patterns to provide infrastructure-level configuration recommendations. For comprehensive guidance on optimizing your Valkey/ElastiCache deployment, see:

**`assets/server-configuration-guide.md`** - Complete infrastructure optimization guide covering:

- **Cluster Architecture Selection**: When to use cluster mode vs standalone based on detected patterns
- **Read/Write Workload Analysis**: Routing strategies and replica configuration
- **Server-Side Tuning**: `maxmemory-policy`, `timeout`, `tcp-keepalive`, `maxclients` configuration
- **ElastiCache Recommendations**: Node type selection, Multi-AZ deployment, parameter groups, shard count

### Quick Server Configuration Insights

**Cluster Mode Detection:**
- Multi-key operations across unrelated keys → Cluster mode recommended
- Single-key or related-key operations → Standalone sufficient

**Read/Write Routing:**
- >80% reads → Enable replicas, use Prefer Replica or AZ Affinity read strategy
- >50% writes → Use Primary routing, optimize write performance
- Balanced workload → Use Primary for consistency, 1-2 replicas for HA

**Memory Policy:**
- Cache-like access (SET with TTL) → `maxmemory-policy = allkeys-lru`
- Persistent data (no eviction) → `maxmemory-policy = noeviction`
- Mixed TTL usage → `maxmemory-policy = volatile-lru`

**ElastiCache Node Types:**
- Memory-intensive (large values, many keys) → r7g.large or larger
- Compute-intensive (high ops/sec, small values) → m7g.large or larger
- Cost-optimized (serverless, low traffic) → t4g.small

For detailed recommendations with code examples and configuration templates, load `assets/server-configuration-guide.md`.

## Configuration Recommendations

### Production-Ready Templates

For complete, production-ready configuration examples with all recommended settings, see:
- `assets/config-templates/nodejs-config.ts` - Node.js/TypeScript
- `assets/config-templates/python-config.py` - Python async/sync
- `assets/config-templates/java-config.java` - Java
- `assets/config-templates/go-config.go` - Go
- `assets/config-templates/php-config.php` - PHP

These templates include timeouts, retry strategies, throughput tuning, and AZ affinity configuration.

### Request Timeouts

Configure based on your use case:
- Sub-10ms real-time apps: 20-50ms
- Web applications: 200-500ms
- Batch processing: 1000-5000ms

### Connection Retry Strategy

Configure exponential backoff for resilience:
- Number of retries: 5-10
- Base delay: 500ms
- Exponential base: 2
- Jitter percent: 10-20 (avoids thundering herd)

### Throughput Tuning

GLIDE uses a single multiplexed connection, not a traditional connection pool. For high-throughput scenarios:
- Increase `inflightRequestsLimit` from default 1000 (available in Node.js, Python, and Java; the Go wrapper does not currently expose this setting)

### Serverless/Lambda

Use `lazyConnect` to defer connection until first command, reducing cold start time.

## Performance Checklist

- [ ] Client reuse (not per-request creation)
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching for bulk operations (10-100 commands)
- [ ] AZ Affinity for read-heavy workloads (>80% reads)
- [ ] Async/concurrent patterns where appropriate
- [ ] Error handling with retry strategy
- [ ] Hash data structures for structured data
- [ ] Values <100KB
- [ ] Hash tags for related keys in cluster
- [ ] Dedicated client for blocking commands
- [ ] lazyConnect for serverless/Lambda

## Troubleshooting Guide

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| P99 >100ms | Per-request client creation | Reuse client instances |
| Timeout errors | No timeout configured | Set appropriate timeout |
| Low throughput | Sequential operations | Use batching or concurrency |
| High data transfer costs | Cross-AZ traffic | Enable AZ affinity |
| Connection errors | Network issues | Configure reconnect/backoff strategy |
| Blocked operations | Blocking commands on shared client | Use dedicated client |
| Memory issues | Large batches (>1000 ops) | Reduce batch size to 10-100 |

## Additional Resources

- [GLIDE Wiki - Batching](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#batching-pipeline-and-transaction)
- [GLIDE Wiki - Connection Management](https://github.com/valkey-io/valkey-glide/wiki/General-Concepts#connection-management)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
- [Benchmarks](https://github.com/valkey-io/valkey-glide/tree/main/benchmarks)
- [Examples](https://github.com/valkey-io/valkey-glide/tree/main/examples)
