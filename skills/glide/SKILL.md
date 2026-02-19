# Agent Skill: Valkey GLIDE Client Development

**Type:** AI Coding Assistant Skill
**Purpose:** Guide correct usage of Valkey GLIDE clients based on real-world implementation experience
**Audience:** AI agents (Claude, ChatGPT, etc.) and human developers

## Language-Specific Guides
Consult the corresponding detailed guide based on the language of the code requiring GLIDE support:

| Language/Framework | Reference File | Key Topics |
|-------------------|----------------|------------|
| **Python** | [Python-specific skill](python/PYTHON.md) | Mutable Default Arguments, Exception Handling, Class Attributes |

---
## Overview

This skill provides patterns and constraints for implementing Valkey client operations using the GLIDE library. It captures lessons learned from production implementations to prevent common pitfalls.
The API provides batch command support (transactions and pipelines) for both standalone and clustered deployments.

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

