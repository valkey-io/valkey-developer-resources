# Agent Skill: Valkey GLIDE Client Development

**Type:** AI Coding Assistant Skill
**Purpose:** Guide correct usage of Valkey GLIDE clients based on real-world implementation experience
**Audience:** AI agents (Claude, ChatGPT, etc.) and human developers

## Language-Specific Guides
Consult the corresponding detailed guide for code generated in the selected language:

| Language/Framework | Reference File | Key Topics |
|-------------------|----------------|------------|
| **Python** | [Python-specific skill](python/PYTHON.md) | Mutable Default Arguments, Exception Handling, Class Attributes |
| **Java** | [Java-specific skill](java/JAVA.md) | CompletableFuture Patterns, Exception Unwrapping, GlideString for Binary Data |
| **Go** | [Go-specific skill](go/GO.md) | Context Pattern, Explicit Error Handling, Batch Pointer Dereferencing |
| **Node.js** | [Node.js-specific skill](js/JS.md) | Promise-Based API, Decoder.Bytes for Binary Data, Static FT Methods |
| **PHP** | [PHP-specific skill](php/PHP.md) | C Extension, PHPRedis Compatibility, Synchronous API, multi()/pipeline() |
| **C#** | [C#-specific skill](cs/CSharp.md) | ⚠️ Preview (v0.9.0) - Async/Await, Builder Pattern, Exception Types |

---
## Overview

This skill provides patterns and constraints for implementing Valkey client operations using the GLIDE library. It captures lessons learned from production implementations to prevent common pitfalls.
The API provides batch command support (transactions and pipelines) for both standalone and clustered deployments.

### General Principles
1.  Avoid use of catching general exceptions when handling GLIDE errors, this is too vague and too broad.  Instead narrow the catch to GLIDE specific exceptions when possible, broaden exceptions for more generic errors but only as necessary, never as a general catch-all.
2.  Add comments as necessary to disambiguate between sync and async GLIDE calls when it is not clear (i.e. the word 'sync' nor the word 'async' appear in nearby syntax).

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

