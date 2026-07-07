# Technical Design: Backend — FlicEnjoyer

## Overview

FlicEnjoyer is a JavaFX desktop application that uses PostgreSQL as its primary datastore and Valkey as a caching layer with ValkeySearch 1.2 for Full Text Search. It demonstrates how Valkey dramatically improves application performance over direct database access through cache-aside patterns, while ValkeySearch provides sub-10ms typeahead and fuzzy search without an external search engine.

## Architecture

```
┌─────────────┐
│   JavaFX UI │
└──────┬──────┘
       │
┌──────▼──────┐
│   service/  │  Business logic, cache-aside orchestration
└──┬───────┬──┘
   │       │
┌──▼──┐ ┌─▼────┐
│ db/ │ │valkey/│  PostgreSQL repos / Valkey cache + FTS
└──┬──┘ └──┬───┘
   │        │
┌──▼──┐ ┌──▼───┐
│ PG  │ │Valkey│  PostgreSQL DB / Valkey + ValkeySearch
└─────┘ └──────┘
```

**Data flow (cache-aside pattern):**
1. **Read:** Check Valkey cache → if miss, query PostgreSQL → populate cache → return
2. **Write:** Write to PostgreSQL → invalidate/update Valkey cache → update ValkeySearch index
3. **Search:** ValkeySearch FTS indexes (populated from DB on startup and kept in sync on writes)

## Data Model

### PostgreSQL Schema

#### `catalog` table

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| `title` | VARCHAR(255) | NOT NULL |
| `genre` | VARCHAR(50) | NOT NULL |
| `description` | TEXT | |
| `tags` | TEXT | Comma-separated |
| `release_year` | INTEGER | |
| `rating` | NUMERIC(3,1) | |
| `duration_minutes` | DOUBLE PRECISION | |
| `video_path` | TEXT | |
| `thumbnail_path` | TEXT | |
| `created_at` | TIMESTAMP | DEFAULT now() |

#### `watch_history` table

| Column | Type | Constraints |
|---|---|---|
| `user_id` | UUID | NOT NULL |
| `catalog_id` | UUID | NOT NULL, REFERENCES catalog(id) |
| `title` | VARCHAR(255) | Denormalized for display |
| `resume_timestamp` | INTEGER | Seconds into playback |
| `completed` | BOOLEAN | DEFAULT false |
| `last_watched` | BIGINT | Unix epoch seconds |
| PRIMARY KEY | | (user_id, catalog_id) |

### Valkey Key Schemas (Cache Layer)

#### Catalog Cache (Hash per title)

Key pattern: `catalog:{id}` (e.g., `catalog:f47ac10b-...`)

Same fields as the PostgreSQL `catalog` table — serialized into a Valkey Hash. TTL: none (invalidated on write).

#### Watch History Cache (Hash per user+title)

Key pattern: `watch:{userId}:{catalogId}`

Same fields as the PostgreSQL `watch_history` table. TTL: none (invalidated on write).

### ValkeySearch FTS Indexes

#### `idx:catalog`

```java
FT.create(client, "idx:catalog",
    new FieldInfo[] {
        new FieldInfo("title", new TextField(false, 1.0, true, false, true)),
        new FieldInfo("genre", new TagField(',', false, true)),
        new FieldInfo("description", new TextField()),
        new FieldInfo("tags", new TagField(',', false, false)),
        new FieldInfo("releaseYear", new NumericField(true)),
        new FieldInfo("rating", new NumericField(true)),
        new FieldInfo("durationMinutes", new NumericField(false)),
        new FieldInfo("videoPath", new TagField()),
        new FieldInfo("thumbnailPath", new TagField()),
    },
    FTCreateOptions.builder()
        .dataType(DataType.HASH)
        .prefixes(new String[] {"catalog:"})
        .language("english")
        .build()
);
```

Key choices:
- `title` has `withSuffixTrie` for prefix/contains queries, `sortable` for alphabetical sorting (WEIGHT must be 1.0 — custom weights not yet supported by ValkeySearch 1.2)
- `genre` and `releaseYear` are `sortable` for filtered/sorted browsing
- `rating` is `sortable` for "top rated" views

#### `idx:watch`

```java
FT.create(client, "idx:watch",
    new FieldInfo[] {
        new FieldInfo("userId", new TagField()),
        new FieldInfo("catalogId", new TagField()),
        new FieldInfo("title", new TextField()),
        new FieldInfo("resumeTimestamp", new NumericField()),
        new FieldInfo("completed", new TagField()),
        new FieldInfo("lastWatched", new NumericField(true)),
    },
    FTCreateOptions.builder()
        .dataType(DataType.HASH)
        .prefixes(new String[] {"watch:"})
        .build()
);
```

Key choices:
- `lastWatched` is `sortable` for "recently watched" ordering
- `userId` and `catalogId` as TAG for exact-match filtering

## Cache-Aside Pattern

### Read Path

```
Service.getMovie(id):
  1. client.hgetall("catalog:{id}")
  2. if cache hit → deserialize Hash → return Movie
  3. if cache miss → CatalogRepository.findById(id)
  4. client.hset("catalog:{id}", movieToHash(movie))
  5. return movie
```

### Write Path

```
Service.uploadVideo(...):
  1. CatalogRepository.insert(movie)          // DB is source of truth
  2. client.hset("catalog:{id}", movieToHash(movie))  // populate cache
  // ValkeySearch auto-indexes the hash via prefix match
```

### Invalidation

```
Service.updateDuration(id, minutes):
  1. CatalogRepository.updateDuration(id, minutes)
  2. client.hset("catalog:{id}", Map.of("durationMinutes", minutes))  // update cache field
```

No TTL-based expiry — cache is explicitly invalidated/updated on writes. This keeps the demo deterministic and avoids stale data during benchmarks.

## Feature Design

### 1. Catalog Search (Typeahead + Fuzzy)

Search uses ValkeySearch FTS exclusively (not PostgreSQL). The FTS index is populated from DB data on startup and kept in sync on writes.

**Typeahead** (prefix matching):
```java
FT.search(client, "idx:catalog", "@title:inc*",
    FTSearchOptions.builder().limit(0, 10).build());
```

**Fuzzy search** (misspelling tolerance):
```java
FT.search(client, "idx:catalog", "@title:%%incetpion%%",
    FTSearchOptions.builder().limit(0, 10).build());
```

**Strategy**: Try prefix first. If results are empty or below a threshold, fall back to fuzzy.

**Filtered browsing**:
```java
FT.search(client, "idx:catalog", "@genre:{action}",
    FTSearchOptions.builder()
        .sortBy(gs("rating"), SortOrder.DESC)
        .limit(0, 20)
        .build());
```

### 2. Watch History & Resume

**Load user history** — cache-aside with FTS:
```java
// Fast path: ValkeySearch query
FT.search(client, "idx:watch", "@userId:{f47ac10b}",
    FTSearchOptions.builder()
        .sortBy(gs("lastWatched"), SortOrder.DESC)
        .build());
// If cache is cold: query DB, populate watch hashes in Valkey
```

**Get resume point** — cache-aside:
```java
// Fast path: direct hash lookup
client.hget(gs("watch:f47ac10b:42"), gs("resumeTimestamp"));
// Miss: query DB, populate cache
```

**Update resume point** — write-through:
```java
// 1. Write to DB
watchHistoryRepository.upsertResumePoint(userId, catalogId, seconds);
// 2. Update cache
client.hset(gs("watch:f47ac10b:42"), Map.of(
    gs("resumeTimestamp"), gs("1834"),
    gs("lastWatched"), gs(String.valueOf(Instant.now().getEpochSecond()))
));
```

### 3. Aggregation Reports

FT.AGGREGATE runs against ValkeySearch indexes (populated from DB).

**Report 1 — Top titles by viewer count**:
```java
FT.aggregate(client, "idx:watch", "@completed:{true|false}",
    FTAggregateOptions.builder()
        .addClause(new GroupBy(
            List.of(gs("@title")),
            List.of(new Reducer("COUNT", new String[]{}, gs("viewerCount")))
        ))
        .addClause(new SortBy(List.of(
            new SortProperty(gs("@viewerCount"), SortOrder.DESC)
        )))
        .addClause(new Limit(0, 20))
        .build());
```

**Report 2 — Catalog summary by genre**:
```java
FT.aggregate(client, "idx:catalog", "*",
    FTAggregateOptions.builder()
        .addClause(new GroupBy(
            List.of(gs("@genre")),
            List.of(
                new Reducer("COUNT", new String[]{}, gs("titleCount")),
                new Reducer("AVG", new String[]{"@rating"}, gs("avgRating"))
            )
        ))
        .addClause(new SortBy(List.of(
            new SortProperty(gs("@titleCount"), SortOrder.DESC)
        )))
        .build());
```

## Class Design

### model/

| Class | Fields | Purpose |
|---|---|---|
| `Movie` | id, title, genre, description, tags, releaseYear, rating, durationMinutes, videoPath, thumbnailPath | Catalog domain object |
| `WatchHistoryEntry` | userId, catalogId, title, resumeTimestamp, completed, lastWatched | Watch state per user+title |
| `AggregationResult` | label, metrics (Map<String, Object>) | Generic container for report rows |
| `Genre` | SCI_FI, ACTION, DRAMA, CRIME, THRILLER, COMEDY, FANTASY, GAMING, OTHER | Enum of known genres |

### db/

| Class | Responsibility |
|---|---|
| `DatabaseProvider` | Initialize HikariCP connection pool from config. Provide `DataSource` singleton. Run `schema.sql` on startup to ensure tables exist. |
| `CatalogRepository` | CRUD operations on `catalog` table via JDBC. `findAll()`, `findById(id)`, `insert(movie)`, `updateDuration(id, minutes)`. |
| `WatchHistoryRepository` | CRUD on `watch_history` table. `findByUserId(userId)`, `findByUserAndCatalog(userId, catalogId)`, `upsert(entry)`. |

### valkey/

| Class | Responsibility |
|---|---|
| `ValkeyClientProvider` | Initialize and provide the GlideClient singleton. Connection config (host, port) loaded from application config file. |
| `UserProfileManager` | On first launch, prompt for user's full name, generate a UUID, and persist both to a local YAML file (`~/.flicenjoyer/profile.yaml`). On subsequent launches, load the existing profile. Provides `getUserId()` and `getDisplayName()`. |
| `IndexManager` | Create `idx:catalog` and `idx:watch` indexes if they don't exist (check via FT._LIST). Drop and recreate on schema changes. On startup, sync all DB catalog/watch data into Valkey hashes so FTS indexes are populated. |

### service/

| Class | Methods | Description |
|---|---|---|
| `CatalogService` | `searchPrefix(prefix, limit)`, `searchFuzzy(term, limit)`, `browseByGenre(genre, sortField, order, limit)`, `browseAll(genreFilter, sortField, descending)`, `getById(id)`, `updateDuration(catalogId, durationMinutes)` | Search via ValkeySearch FTS. `getById` uses cache-aside (Valkey → DB). `browseAll` queries DB with optional Valkey cache. |
| `UploadService` | `uploadVideo(title, genre, description, tags, releaseYear, videoFile, thumbnailFile)` | Writes to DB first, then populates Valkey cache hash (auto-indexed by ValkeySearch). |
| `WatchHistoryService` | `getUserHistory()`, `getResumePoint(catalogId)`, `updateResumePoint(catalogId, seconds)`, `markCompleted(catalogId)` | Cache-aside: Valkey first, DB fallback. Writes go to DB then update cache. |
| `AggregationService` | `topTitlesByViewers(limit)`, `catalogSummaryByGenre()` | FT.AGGREGATE against ValkeySearch indexes |
| `BenchmarkService` | `benchmark(task, iterations)`, `concurrentThroughput(task, threads, opsPerThread, onProgress)`, `concurrentComparison(dbTask, valkeyTask, threads, opsPerThread, onProgress)`, `createTasks(operation, ids, catalogService, watchHistoryService)` | Timing harness. `concurrentComparison` runs both DB-direct and Valkey-cached paths under concurrent load, returns paired throughput results for side-by-side display. `createTasks` builds matched task pairs for a given operation. |

### ui/

See [design-frontend.md](design-frontend.md) for UI class design and layout details.

## Application Configuration

Non-user-specific configuration is loaded from `config.yaml` in the working directory (falls back to defaults if absent).

```yaml
valkey:
  host: localhost
  port: 6379

database:
  host: localhost
  port: 5432
  name: flicenjoyer
  user: flicenjoyer
  password: flicenjoyer
```

Loaded at startup by `AppConfig` into a record. `ValkeyClientProvider` reads valkey config; `DatabaseProvider` reads database config.

| Class | Responsibility |
|---|---|
| `AppConfig` | Loads `config.yaml` from the working directory via SnakeYAML. Provides typed accessors (`valkeyHost()`, `valkeyPort()`, `dbHost()`, `dbPort()`, `dbName()`, `dbUser()`, `dbPassword()`). Falls back to defaults if file is missing or fields are absent. |

## Startup Sequence

1. `AppConfig.load()` → load `config.yaml` from working directory (defaults if absent)
2. `DatabaseProvider.init()` → create HikariCP pool, run `schema.sql` to ensure tables exist
3. `FlicEnjoyerApp.start()` → create `ValkeyClientProvider` using config (host, port)
4. `UserProfileManager.load()` → if `~/.flicenjoyer/profile.yaml` exists, load userId and displayName; otherwise show a prompt dialog for the user's full name, generate a UUID, and persist the profile
5. `IndexManager.ensureIndexes()` → check FT._LIST, create `idx:catalog` and `idx:watch` if missing
6. `IndexManager.syncFromDatabase()` → load all catalog and watch_history rows from DB, write as Valkey hashes (populates FTS indexes)
7. `WatchHistoryService.getUserHistory()` → hydrate any existing watch state for this userId (from cache, now warm)
8. Launch JavaFX stage with `MainController`

## Local Media Storage

Uploaded videos and thumbnails are stored at `~/.flicenjoyer/media/`:
- Videos: `~/.flicenjoyer/media/videos/{catalogId}.{ext}`
- Thumbnails: `~/.flicenjoyer/media/thumbnails/{catalogId}.{ext}`

`UploadService` copies the user-selected files to these paths and stores the absolute paths in both the DB and the Valkey cache hash.

### Session State

On first launch, the user is prompted for their full name and a UUID is generated as their userId. This profile is persisted locally at `~/.flicenjoyer/profile.yaml`. Each session starts with whatever watch history already exists in the DB for that userId.

## Performance Benchmarking

`BenchmarkService` measures throughput under concurrent load to demonstrate Valkey's advantage over direct database access. Under parallel threads, PostgreSQL's connection pool (5 connections via HikariCP) becomes the bottleneck — threads queue waiting for a connection. Valkey multiplexes all requests over a single connection with no pool contention, delivering dramatically higher throughput.

### Concurrent load benchmark

Spawns N threads, each performing M operations against the same path. Measures wall-clock time for all threads to complete, reports aggregate throughput (ops/sec).

**Why concurrency matters:** Single-request latency on localhost is similar for both backends (microsecond network hops). The real difference emerges under load — exactly the conditions a production app faces. With 32+ concurrent threads:
- PostgreSQL: threads contend for 5 pool connections, throughput plateaus
- Valkey: all threads share one multiplexed connection, throughput scales linearly

### Comparison mode

Runs the same operation under identical concurrent load against both paths:
1. **DB-direct:** N threads × M ops hitting PostgreSQL via JDBC
2. **Valkey-cached:** N threads × M ops hitting Valkey cache

Reports ops/sec for each and the speedup factor.

### UI controls

- **Threads:** Number of parallel threads (default: 32)
- **Ops/thread:** Operations per thread (default: 500)
- **Operation:** Catalog Lookup, Resume Point Retrieval, or Search

Target benchmarks (32 threads × 500 ops):
- Catalog Lookup: Valkey 5-20x faster than DB under load
- Resume Point Retrieval: Valkey 5-20x faster than DB under load
- Search (ValkeySearch FTS): demonstrates raw FTS throughput

Results displayed in `BenchmarkView` with side-by-side ops/sec and speedup factor.

## Error Handling

- `DatabaseProvider` fails fast on connection error with clear message (host, port, cause)
- `ValkeyClientProvider` fails fast on connection error with clear message (host, port, cause)
- `IndexManager` catches "index already exists" responses gracefully
- `UploadService` validates required fields before writing to DB
- Cache misses are not errors — they trigger a DB fallback transparently
- Service methods wrap DB/Valkey exceptions in domain-specific exceptions with context

## Known Limitations

- **Volume/mute delay (~500ms)** — JavaFX `MediaPlayer` applies volume and mute changes asynchronously to its internal audio buffer. This is a JavaFX platform limitation with no available workaround.
- **Cold cache on first startup** — `IndexManager.syncFromDatabase()` populates the cache on startup, so the first launch after a DB-only state change may be slightly slower.

## Utilities

- `ResetData` — CLI utility (`./gradlew resetData`) that deletes all data from PostgreSQL tables, all `catalog:*` and `watch:*` keys from Valkey, drops FTS indexes, and removes `~/.flicenjoyer/media/`.
- Icons are individual SVG files in `src/main/resources/icons/`, each containing a `<path>` with `data-filled` attribute. `IconLoader` parses them at startup.

## Integration Testing

Integration tests live in `src/integrationTest/java/` and use Testcontainers to run against live Valkey and PostgreSQL instances. Run with `gradle integrationTest`.

Currently gated behind `FLICENJOYER_INTEGRATION_TESTS=true` environment variable. Uses `valkey/valkey-bundle:unstable` for Valkey and `postgres:17` for PostgreSQL via Testcontainers.
