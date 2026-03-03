# Agent Skill: Valkey GLIDE Client Development

**Type:** AI Coding Assistant Skill
**Purpose:** Guide correct usage of Valkey GLIDE clients based on real-world implementation experience
**Audience:** AI agents (Claude, ChatGPT, etc.) and human developers

## Activation Triggers

**Use this skill when:**
- Generating new Valkey GLIDE code in any supported language
- Reviewing or analyzing applications that use Valkey GLIDE
- Debugging Valkey GLIDE related issues
- Asked about Valkey client patterns, batching, clustering, or error handling

**Example phrases:**
- "write Valkey GLIDE code"
- "review this Valkey code"
- "create Valkey client"
- "implement Valkey pipeline/batch/transaction"
- "fix CROSSSLOT error"
- "connect to Valkey cluster"
- "handle Valkey timeout exceptions"

## Language-Specific Guides
Consult the corresponding detailed guide for code generated in the selected language:

| Language/Framework | Reference File | Key Topics |
|-------------------|----------------|------------|
| **Python** | [Python-specific skill](python/PYTHON.md) | Mutable Default Arguments, Exception Handling, Class Attributes |
| **Java** | [Java-specific skill](java/JAVA.md) | CompletableFuture Patterns, Exception Unwrapping, GlideString for Binary Data |
| **Go** | [Go-specific skill](go/GO.md) | Context Pattern, Explicit Error Handling, Batch Pointer Dereferencing |
| **Node.js** | [Node.js-specific skill](js/JS.md) | Promise-Based API, Decoder.Bytes for Binary Data, Static FT Methods |
| **PHP** | [PHP-specific skill](php/PHP.md) | C Extension, PHPRedis Compatibility, Synchronous API, multi()/pipeline() |
| **C#** | [C#-specific skill](cs/CSharp.md) | Task-Based Async, await using Pattern, CustomCommand for FT Module |

---
## Overview

This skill provides patterns and constraints for implementing Valkey client operations using the GLIDE library. It captures lessons learned from production implementations to prevent common pitfalls.
The API provides batch command support (transactions and pipelines) for both standalone and clustered deployments.

### General Principles
1.  Avoid use of catching general exceptions when handling GLIDE errors, this is too vague and too broad.  Instead narrow the catch to GLIDE specific exceptions when possible, broaden exceptions for more generic errors but only as necessary, never as a general catch-all.
2.  Add comments as necessary to disambiguate between sync and async GLIDE calls when it is not clear (i.e. the word 'sync' nor the word 'async' appear in nearby syntax).

---
## Timeout Configuration

**Connection Timeout vs Request Timeout:**
- **Connection timeout**: Time to establish initial connection (typically 2 seconds)
- **Request timeout**: Time for individual command to complete (typically 250 milliseconds)

**When to Adjust Timeouts:**
Increase timeouts for:
- Large batch operations (>1000 keys)
- Vector search queries (high-dimensional data)
- Blocking operations (BLPOP, BRPOP with timeout)
- High network latency environments (cross-region, VPN)
- Cluster operations spanning multiple nodes
- Large data transfers (>1MB values)

**Handling Timeout Exceptions in Production:**

1. **Catch timeout-specific exceptions** (not generic exceptions):
   - Python: `TimeoutError`
   - Java: `TimeoutException`
   - Go: Check error type or message for timeout
   - Node.js: Check error message for "timeout"
   - PHP: Check exception message for timeout
   - C#: `TimeoutException`

2. **Log with structured context**:
   - Operation name (GET, SET, batch, etc.)
   - Key(s) involved
   - Configured timeout value
   - Timestamp and duration

3. **Implement fallback strategy**:
   - **Cache miss**: Fall back to database/source of truth
   - **Cache write**: Log and continue (eventual consistency)
   - **Critical read**: Retry with exponential backoff (max 2-3 attempts)
   - **Batch operation**: Consider partial retry of failed subset

4. **Emit metrics/alerts**:
   - Increment timeout counter for monitoring
   - Alert if timeout rate exceeds threshold (e.g., >1% of requests)
   - Track timeout duration distribution

5. **Decide on retry vs fail-fast**:
   - **Retry**: Transient network issues, server under load
   - **Fail-fast**: Strict SLA requirements, already at max timeout
   - **Circuit breaker**: After N consecutive timeouts, fail immediately for M seconds

---
## Batch Commands (Pipeline and Transaction)

**Batch API** replaces deprecated Transaction/ClusterTransaction APIs. Two modes:

**Atomic Batch (Transaction):**
- All commands execute as single atomic unit (MULTI/EXEC)
- Sequential execution, no interleaving
- **Cluster constraint:** All keys must map to same hash slot
- Use case: Consistency and isolation required

**Non-Atomic Batch (Pipeline):**
- Commands sent in single request, no atomicity
- Can span multiple slots/nodes in cluster
- Other operations may interleave
- Use case: Bulk independent operations

**Classes:**
- `Batch` / `StandaloneBatch` - Standalone mode
- `ClusterBatch` - Cluster mode
- Constructor: `Batch(isAtomic: bool)` or `ClusterBatch(isAtomic: bool)`

**Execution:**
```
client.exec(batch, raiseOnError, options?)
```

**Error Handling (`raiseOnError`):**
- `true`: Raises first error as exception
- `false`: Returns errors in result array at corresponding positions

**Options:**

`BatchOptions` (Standalone):
- `timeout`: Max wait time (ms)

`ClusterBatchOptions`:
- `timeout`: Max wait time (ms)
- `retryStrategy`: Retry config (non-atomic only)
  - `retryServerError`: Retry on TRYAGAIN (may reorder)
  - `retryConnectionError`: Retry entire batch (may duplicate)
- `route`: Single-node routing

**Multi-Node Support (Cluster Pipeline):**
- GLIDE splits pipeline into sub-pipelines per node
- Dispatches independently, reassembles responses in order
- Redirection errors (MOVED/ASK) always handled automatically
- Retry strategies apply per command, not all-or-nothing

**Deprecation:**
- `Transaction` → `Batch(true)`
- `ClusterTransaction` → `ClusterBatch(true)`

---

