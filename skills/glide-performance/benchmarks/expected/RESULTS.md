# Expected Results — Answer Key

> **DO NOT READ THIS FILE BEFORE COMPLETING YOUR REVIEW.**
> This file is the answer key for the blind evaluation described in the benchmarks README.
> Reading it before reviewing the code defeats the purpose of the test.

## Scoring

- **Detection rate**: (correctly flagged anti-patterns) / (total known anti-patterns) — target ≥ 90%
- **False positive rate**: (incorrectly flagged good code) / (total good code sections) — target 0%

## Anti-Pattern Classes — Expected Findings

The table below uses the Node.js file as the reference. The same patterns appear across all language files with equivalent class/function names.

### Core Anti-Pattern Classes

| Class / Function | Expected Findings |
|---|---|
| `OrderProcessor` | Per-request client creation (every method); sequential gets in `getCustomerProfile` (should use MGET or Hash); missing timeout; missing error handling; missing TLS |
| `InventoryMonitor` | Per-request cluster client creation; sequential gets in loop in `checkAvailability`; cluster without TLS; missing timeout; missing error handling |
| `QueueWorker` | Per-request client creation; blocking command (`blpop`) on a general-purpose client (should use dedicated blocking client); missing error handling |
| `ReportGenerator` | Per-request client creation; nested sequential loops (region × date); missing timeout; missing error handling |
| `SessionManager` | Per-request client creation; JSON get-parse-modify-set pattern (should use Hash); missing timeout; missing error handling |
| `CatalogService` | Per-request cluster client creation; sequential gets in loop; cluster without TLS (despite having `readFrom` set); missing error handling |
| `handleLambdaRequest` | Per-request client creation in Lambda (should reuse across invocations with module-level variable); missing `lazyConnect`; client explicitly closed (prevents reuse) |
| `DocumentVault` | Per-request client creation (every method); JSON get-parse-modify-set pattern throughout (`reviseField`, `extractField`, `bumpViewCount` — should use Hash with `HSET`/`HGET`/`HINCRBY`); missing timeout; missing error handling |
| `TelemetryIngester` | Per-request client creation; sequential commands in loop in `ingestBatch` (4 commands per reading — should batch/pipeline); sequential `lpop` in `drainStream`; sequential gets in `snapshotAll`; missing timeout; missing error handling |
| `TokenBucketLimiter` | Per-request client creation; race condition (non-atomic read-modify-write — should use Lua script or transaction); missing timeout; missing error handling |
| `DistributedLockManager` | Per-request client creation (both methods); non-atomic lock release in `releaseExclusive` (GET + conditional DEL — should use Lua script); missing timeout; missing error handling |
| `GeoFenceTracker` | Per-request cluster client creation (every method); sequential sets/gets without batching; cluster without TLS; missing hash tags for related keys (`entity:{id}:lat/lon/updated` should use `{entity:id}`); missing timeout; missing error handling |
| `ContentIndexer` | Per-request client creation; `SCAN` for search in `locateByPattern` (should use Valkey-Search `FT.SEARCH` if available); sequential `SADD` in `tagMembership`; sequential `SISMEMBER` in `probeExistence`; missing timeout; missing error handling |
| `LeaderboardAggregator` | Per-request cluster client creation; sequential commands in loop (3 per entry — should pipeline); cluster without TLS; missing timeout; missing error handling |
| `FeatureFlagEvaluator` | Per-request client creation (both methods); sequential gets in loop in `resolveFlags` (2 per flag); sequential sets in `bulkToggle`; missing timeout; missing error handling |
| `NotificationDispatcher` | Per-request client creation **inside the loop** in `enqueueMany` (worst case — new connection per notification); blocking command (`brpop`) on same client used for non-blocking ops in `awaitDeliveryConfirmation`; missing timeout; missing error handling |
| `CartReconciler` | Per-request client creation; sequential gets in loop in `materializeCart` (multiple gets per item); missing timeout; missing error handling |
| `MigrationBridge` | Per-request client creation (two clients); sequential key-by-key transfer (should batch); missing timeout; missing error handling |
| `HealthProbe` | Per-request client creation **inside the loop** (new connection per endpoint); though `requestTimeout: 100` is set, this is a health check so per-request creation is somewhat expected — nuanced |
| `AnalyticsCollector` | Per-request client creation; sequential commands in `recordPageView` (6 commands — should pipeline); sequential gets in `computeHourlyRollup`; missing timeout; missing error handling |
| `ClusterShardBalancer` | Per-request cluster client creation; sequential get-set-delete in loop in `redistributeKeys`; sequential gets in `crossSlotAggregate`; cluster without TLS; missing timeout; missing error handling |
| `processWebhookEvent` | Per-request client creation; missing timeout; missing error handling |

### Edge Case / Subtle Pattern Classes

These test whether the AI gives nuanced feedback rather than blanket pass/fail.

| Class / Function | Expected Findings |
|---|---|
| `ConfigHydrator` | Singleton pattern (good — client reuse). BUT: missing timeout config; missing error handling; missing reconnect strategy; sequential gets in `hydrateNamespace` (should use MGET or pipeline); sequential sets in `persistNamespace` (should pipeline). Should get partial credit. |
| `EphemeralCacheWarmer` | Per-request client creation (both methods); sequential sets in `primeFromSource` (should pipeline); sequential gets in `verifyWarmed` (should use MGET); has `requestTimeout` set (good). |
| `MultiTenantRouter` | Per-request cluster client creation (both methods); `SCAN` usage in `crossTenantScan` (consider Valkey-Search); sequential get after scan. Has TLS and timeout (good). |
| `CircuitBreakerCache` | Per-request client creation (both primary and fallback); fallback client created inside catch block (connection overhead during failure — should pre-initialize). Has timeout (good). |
| `SessionReplicator` | Per-request client creation **inside the loop** (new connection per replica); sequential replication (should parallelize or pipeline). |
| `ThrottledBatchProcessor` | Per-request client creation; sequential set + expire in loop (should pipeline, and use `SET` with `EX` option instead of separate `EXPIRE`). Has timeout (good). |
| `ReadHeavyClusterService` | Per-request cluster client creation; sequential reads for dashboard data (should pipeline or use MGET where possible); missing AZ affinity config despite being read-heavy (name is a hint). Has TLS and timeout (good). |
| `InsecureClusterGateway` | Per-request cluster client creation (via `openChannel` called in every method); cluster without TLS (the class name is a hint, but the AI should flag this based on code analysis, not the name); missing error handling. |
| `StatefulWorkerPool` | Per-request client creation (both methods); sequential gets in `reportHeartbeats`; has timeout and clientName (good). |
| `handleCronTick` | Per-request client creation; sequential list operations (lrange + loop of lpush/lrem — should pipeline); missing timeout; missing error handling. Lock pattern is reasonable. |
| `PartitionedTimeSeries` | Per-request cluster client creation (both methods); sequential lpush in loop in `appendSamples` (should pipeline); missing hash tags for related keys (`ts:{seriesId}:bucket` should use `{ts:seriesId}`); sequential lrange in `queryRange`. Has TLS and timeout (good). |

## Known-Good Code — Expected: Zero Findings

These sections should NOT be flagged. Any finding here is a false positive.

| Class / Function | Why It's Correct |
|---|---|
| `initializeSharedClients` (and the global client setup block) | Module-level shared clients with TLS, timeouts, reconnect strategy, AZ affinity, dedicated blocking client. This is the reference implementation. |
| `WellStructuredProfileService` | Uses shared client; Hash data structure (`hmget`/`hset`); error handling with fallback; batched updates via transactions with chunking. |
| `WellStructuredClusterCatalog` | Uses shared cluster client; hash tags for key co-location (`{category:id}`); batched `MGET` with chunking; error handling. |
| `WellStructuredQueueConsumer` | Uses dedicated blocking client for `blpop`; separate shared client for non-blocking ops; error handling with logging. |
| `handleOptimizedLambda` | Module-level persistent client (reused across Lambda invocations); timeout configured; reconnect strategy; error handling. |

## Scoring Template

Use this table to record results. Copy it and fill in the "Detected?" column after the blind review.

```markdown
| Class / Function | Key Anti-Patterns | Detected? | Notes |
|---|---|---|---|
| OrderProcessor | client-per-request, sequential gets, no timeout | | |
| InventoryMonitor | client-per-request, sequential loop, no TLS | | |
| QueueWorker | client-per-request, blocking on shared client | | |
| ReportGenerator | client-per-request, nested sequential loops | | |
| SessionManager | client-per-request, JSON get-parse-modify-set | | |
| CatalogService | client-per-request, sequential loop, no TLS | | |
| handleLambdaRequest | client-per-request in Lambda, no lazyConnect | | |
| DocumentVault | client-per-request, JSON get-parse-modify-set | | |
| TelemetryIngester | client-per-request, sequential batch commands | | |
| TokenBucketLimiter | client-per-request, non-atomic read-modify-write | | |
| DistributedLockManager | client-per-request, non-atomic lock release | | |
| GeoFenceTracker | client-per-request, no TLS, no hash tags | | |
| ContentIndexer | client-per-request, SCAN for search | | |
| LeaderboardAggregator | client-per-request, sequential loop, no TLS | | |
| FeatureFlagEvaluator | client-per-request, sequential gets/sets | | |
| NotificationDispatcher | client-per-request IN LOOP, blocking on shared | | |
| CartReconciler | client-per-request, sequential gets in loop | | |
| MigrationBridge | client-per-request, sequential transfer | | |
| HealthProbe | client-per-request in loop (nuanced) | | |
| AnalyticsCollector | client-per-request, sequential commands | | |
| ClusterShardBalancer | client-per-request, sequential loop, no TLS | | |
| processWebhookEvent | client-per-request, no timeout | | |
| ConfigHydrator | partial — singleton but no timeout/retry | | |
| EphemeralCacheWarmer | client-per-request, sequential ops | | |
| MultiTenantRouter | client-per-request, SCAN usage | | |
| CircuitBreakerCache | client-per-request, fallback in catch | | |
| SessionReplicator | client-per-request in loop | | |
| ThrottledBatchProcessor | client-per-request, set+expire separately | | |
| ReadHeavyClusterService | client-per-request, no AZ affinity | | |
| InsecureClusterGateway | client-per-request, no TLS | | |
| StatefulWorkerPool | client-per-request, sequential gets | | |
| handleCronTick | client-per-request, sequential list ops | | |
| PartitionedTimeSeries | client-per-request, no hash tags, sequential | | |
| **Known-Good Code** | | | |
| initializeSharedClients | Expected: no issues | | |
| WellStructuredProfileService | Expected: no issues | | |
| WellStructuredClusterCatalog | Expected: no issues | | |
| WellStructuredQueueConsumer | Expected: no issues | | |
| handleOptimizedLambda | Expected: no issues | | |

Detection rate: ___ / 33 = ___%
False positive rate: ___ / 5 = ___%
```
