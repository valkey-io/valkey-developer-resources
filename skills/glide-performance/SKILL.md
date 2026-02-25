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

Optimize Valkey GLIDE clients across Node.js, Python, Java, Go, PHP. Uses progressive disclosure — loads only language-relevant patterns to minimize context.

## Structure

- **This file**: Always loaded. Universal anti-patterns and optimization strategies.
- **Language patterns** (loaded on-demand per detected language):
  - `reference/nodejs-patterns.md` — Node.js/TypeScript
  - `reference/python-patterns.md` — Python async/sync
  - `reference/java-patterns.md` — Java
  - `reference/go-patterns.md` — Go
  - `reference/php-patterns.md` — PHP

## When to Activate

- P99 latencies >100ms or timeout errors
- Migrating from legacy clients (node-redis, redis-py, Jedis, go-redis)
- High cross-AZ data transfer costs
- High throughput, >100K ops/sec workloads
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

**Action Required**: When the language is detected, you **MUST LOAD** the corresponding reference file:
- Node.js/TypeScript → Load `reference/nodejs-patterns.md`
- Python → Load `reference/python-patterns.md`
- Java → Load `reference/java-patterns.md`
- Go → Load `reference/go-patterns.md`
- PHP → Load `reference/php-patterns.md`

## Universal Anti-Patterns

### 1. Per-Request Client Creation [CRITICAL]
Client creation inside request handlers, loops, or frequently-called functions → connection overhead, exhaustion, memory leaks. Fix: create once at startup, reuse everywhere.

### 2. Missing Request Timeouts
No `requestTimeout`/`timeout` → operations hang indefinitely, cascading failures. Always configure:
- Real-time (sub-10ms): 20-50ms
- Web apps: 200-500ms
- Batch processing: 1000-5000ms

### 3. Sequential Operations
Multiple await/get calls in sequence = N × roundtrip latency. Fix: use batching (pipeline/transaction) or concurrent execution.

### 4. Blocking Commands on Shared Client
BLPOP, BRPOP, BLMOVE, BZPOPMIN, BZPOPMAX block the connection for all operations. Fix: dedicated client instance with longer timeout.

### 5. Large Batch Sizes
>1000 operations or >10MB payload → memory pressure, timeouts. Optimal: 10-100 commands per batch.

### 6. Missing Error Handling & Retries
No try-catch or retry config → immediate failure on transient network issues. Configure connection backoff with exponential retry.

## Core Optimization Strategies

### Batching (Pipeline & Transactions)
Execute multiple commands in one roundtrip. Reduces latency from N × roundtrip to 1 × roundtrip.
- Independent commands → Pipeline (non-atomic)
- Atomic operations → Transaction
- Bulk data → MGET/MSET
- Optimal batch size: 10-100 commands

### Cluster-Aware Operations
Use `{tag}` hash tags to co-locate related keys on same slot: `{user:123}:name`, `{user:123}:email` → single roundtrip for multi-key ops.

### AZ Affinity (Cost Optimization)
Route reads to same-AZ replicas. Reduces latency and cross-AZ transfer costs.
- Requires: Valkey 8.0+ or ElastiCache for Valkey 7.2+, cluster mode with replicas
- Use when: >80% reads
- Skip when: write-heavy, strong consistency required, single-AZ

### Async/Concurrent Patterns
Execute independent operations concurrently: wall-clock time = max(latencies) instead of sum(latencies). Batching is usually more efficient than concurrent individual operations.

### Data Size Optimization
- Values <100KB; compress if >10KB
- Split large objects across keys
- Use Hash structures for structured data instead of JSON strings

### SCAN vs Valkey-Search
SCAN iterates the full keyspace (O(N)) — use only for migrations/admin. For application-level search, use Valkey-Search (`FT.*`) which scales by result count, not keyspace size.

## Valkey Module Detection

Detect module usage via command patterns and provide optimization guidance.

### Supported Modules
- **Valkey-Search** (`FT.*`): Full-text search, secondary indexing
- **Valkey-JSON** (`JSON.*`): Native JSON document storage
- **Valkey-BloomFilter** (`BF.*`, `CF.*`, `CMS.*`, `TOPK.*`): Probabilistic data structures

### Module Anti-Patterns

**Valkey-Search**: Missing index definitions before queries; wildcard prefix searches; no pagination; not using `FT.AGGREGATE` for aggregations.

**Valkey-JSON**: Full document `JSON.GET` instead of path-based queries; not using `JSON.MGET` for batching; documents >100KB without splitting; missing `JSON.NUMINCRBY` for atomic updates.

**Valkey-BloomFilter**: Wrong false-positive rate; undersized initial capacity; not using Cuckoo Filters (`CF.*`) when deletions needed; sequential `BF.ADD` instead of `BF.MADD`.

### Pattern-to-Module Recommendations
- `GET` + JSON parse + modify + `SET` → use `JSON.SET` with path syntax
- `SCAN` + pattern matching for search → use `FT.CREATE` index + `FT.SEARCH`
- Large `SISMEMBER`/`SMEMBERS` + filtering → use `BF.EXISTS` for probabilistic membership

### Module Configuration
**Search**: Use appropriate field types (TEXT, NUMERIC, TAG, GEO). Set `STOPWORDS`, `MAXPREFIXEXPANSIONS`. Use `SORTBY` with indexed fields.

**JSON**: Configure `json-max-size`. Use path-based operations. Use `JSON.FORGET` to remove unused paths.

**BloomFilter**: Calculate capacity from expected cardinality. Error rate: 0.01 general, 0.001 critical. Pre-allocate with `BF.RESERVE`.

## Server Configuration

For full infrastructure guide: `assets/server-configuration-guide.md`

**Cluster mode**: Multi-key ops across unrelated keys → cluster. Single/related-key ops → standalone sufficient.

**Read/Write routing**:
- >80% reads → replicas + Prefer Replica or AZ Affinity
- >50% writes → Primary routing
- Balanced → Primary for consistency, 1-2 replicas for HA

**Memory policy**:
- Cache (SET with TTL) → `allkeys-lru`
- Persistent (no eviction) → `noeviction`
- Mixed TTL → `volatile-lru`

**ElastiCache node types**:
- Memory-intensive → r7g.large+
- Compute-intensive → m7g.large+
- Cost-optimized → t4g.small

## Client Configuration

Production templates: `reference/config-templates/{nodejs-config.ts,python-config.py,java-config.java,go-config.go,php-config.php}`

**Timeouts**: 20-50ms (real-time), 200-500ms (web), 1000-5000ms (batch)

**Retry**: Exponential backoff — 5-10 retries, 500ms base, 2x exponent, 10-20% jitter.

**Throughput**: GLIDE uses single multiplexed connection (not a pool). Increase `inflightRequestsLimit` from default 1000 for high-throughput (Node.js, Python, Java; not exposed in Go).

**Serverless**: `lazyConnect: true` to defer connection until first command.

## Performance Checklist

- [ ] Client reuse (not per-request)
- [ ] Request timeout configured (500ms recommended)
- [ ] Batching for bulk ops (10-100 commands)
- [ ] AZ Affinity for read-heavy (>80% reads)
- [ ] Connection backoff configured
- [ ] Concurrent patterns where appropriate
- [ ] Error handling with retry strategy
- [ ] Hash data structures for structured data
- [ ] Values <100KB
- [ ] Hash tags for related keys in cluster
- [ ] Dedicated client for blocking commands
- [ ] lazyConnect for serverless/Lambda
- [ ] OpenTelemetry enabled for monitoring
- [ ] Logging set to warn/error for production

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

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| P99 >100ms | Per-request client creation | Reuse client |
| Timeout errors | No timeout configured | Set timeout |
| Low throughput | Sequential operations | Batch or concurrency |
| High transfer costs | Cross-AZ traffic | AZ affinity |
| Connection errors | Network issues | Reconnect/backoff |
| Blocked operations | Blocking cmds on shared client | Dedicated client |
| Memory issues | Large batches (>1000) | Reduce to 10-100 |