# Technical Design: Backend — FlicEnjoyer

## Overview

FlicEnjoyer is a JavaFX desktop application backed by Valkey with ValkeySearch 1.2. It demonstrates FTS capabilities through three features: catalog search (typeahead + fuzzy), user watch history with resume, and aggregation reports. All data lives in Valkey — there is no external database.

## Data Model

### Valkey Key Schemas

#### Catalog (Hash per title)

Key pattern: `catalog:{id}` (e.g., `catalog:1`, `catalog:42`)

| Hash Field | Type | Description |
|---|---|---|
| `title` | TEXT | Video title |
| `genre` | TAG | Genre(s), comma-separated |
| `description` | TEXT | Synopsis |
| `tags` | TAG | Searchable tags, comma-separated |
| `releaseYear` | NUMERIC | Year of release |
| `rating` | NUMERIC | Rating (0.0–10.0) |
| `durationMinutes` | NUMERIC | Runtime in minutes |
| `videoPath` | TAG | Absolute path to local video file |
| `thumbnailPath` | TAG | Absolute path to local thumbnail image |

#### Watch History (Hash per user+title)

Key pattern: `watch:{userId}:{catalogId}` (e.g., `watch:f47ac10b:42`)

| Hash Field | Type | Description |
|---|---|---|
| `userId` | TAG | UUID generated on first launch |
| `catalogId` | TAG | Reference to catalog entry |
| `title` | TEXT | Denormalized title for display |
| `resumeTimestamp` | NUMERIC | Seconds into playback |
| `completed` | TAG | "true" or "false" |
| `lastWatched` | NUMERIC | Unix epoch seconds |

### FTS Indexes

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

## Feature Design

### 1. Catalog Search (Typeahead + Fuzzy)

**Flow**: User types in search bar → debounced query fires on each keystroke → results update live.

**Typeahead** (prefix matching):
```java
// User typed "inc" → search for prefix match on title
FT.search(client, "idx:catalog", "@title:inc*",
    FTSearchOptions.builder()
        .limit(0, 10)
        .build());
```

**Fuzzy search** (misspelling tolerance):
```java
// User typed "incetpion" → fuzzy match with % operator
FT.search(client, "idx:catalog", "@title:%%incetpion%%",
    FTSearchOptions.builder()
        .limit(0, 10)
        .build());
```

**Strategy**: Try prefix first. If results are empty or below a threshold, fall back to fuzzy. The service layer handles this logic.

**Filtered browsing**:
```java
// Browse by genre, sorted by rating
FT.search(client, "idx:catalog", "@genre:{action}",
    FTSearchOptions.builder()
        .sortBy(gs("rating"), SortOrder.DESC)
        .limit(0, 20)
        .build());
```

### 2. Watch History & Resume

**Load user history** (session hydration on startup):
```java
// Get all watch entries for this user, most recent first
FT.search(client, "idx:watch", "@userId:{f47ac10b}",
    FTSearchOptions.builder()
        .sortBy(gs("lastWatched"), SortOrder.DESC)
        .build());
```

**Get resume point for a specific title**:
```java
// Direct hash lookup — no search needed
client.hget(gs("watch:f47ac10b:42"), gs("resumeTimestamp"));
```

**Update resume point**:
```java
client.hset(gs("watch:f47ac10b:42"), Map.of(
    gs("resumeTimestamp"), gs("1834"),
    gs("lastWatched"), gs(String.valueOf(Instant.now().getEpochSecond()))
));
```

### 3. Aggregation Reports

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
| `Movie` | id, title, genre, description, tags, releaseYear, rating, durationMinutes, videoPath, thumbnailPath | Catalog domain object (user-uploaded video) |
| `WatchHistoryEntry` | userId, catalogId, title, resumeTimestamp, completed, lastWatched | Watch state per user+title |
| `AggregationResult` | label, metrics (Map<String, Object>) | Generic container for report rows |
| `Genre` | SCI_FI, ACTION, DRAMA, CRIME, THRILLER, COMEDY, FANTASY, GAMING, OTHER | Enum of known genres with lowercase `value()` and capitalized `displayName()`. Single source of truth for genre lists and "Other" filtering. |

### valkey/

| Class | Responsibility |
|---|---|
| `ValkeyClientProvider` | Initialize and provide the GlideClient singleton. Connection config (host, port) loaded from application config file. |
| `UserProfileManager` | On first launch, prompt for user's full name, generate a UUID, and persist both to a local YAML file (`~/.flicenjoyer/profile.yaml`). On subsequent launches, load the existing profile. Provides `getUserId()` and `getDisplayName()`. |
| `IndexManager` | Create `idx:catalog` and `idx:watch` indexes if they don't exist (check via FT._LIST). Drop and recreate on schema changes. |

### service/

| Class | Methods | Description |
|---|---|---|
| `CatalogService` | `searchPrefix(prefix, limit)`, `searchFuzzy(term, limit)`, `browseByGenre(genre, sortField, order, limit)`, `browseAll(genreFilter, sortField, descending)`, `updateDuration(catalogId, durationMinutes)` | Catalog search via FT.SEARCH, with `browseAll` as a KEYS/HGETALL fallback when ValkeySearch is unavailable. `updateDuration` persists actual video duration discovered during playback. |
| `UploadService` | `uploadVideo(title, genre, description, tags, releaseYear, videoFile, thumbnailFile)` | Copies video and thumbnail to local media directory (`~/.flicenjoyer/media/`), generates a UUID catalog ID, writes the catalog hash to Valkey with file paths |
| `WatchHistoryService` | `getUserHistory()`, `getResumePoint(catalogId)`, `updateResumePoint(catalogId, seconds)`, `markCompleted(catalogId)` | Watch history CRUD scoped to the current userId from UserProfileManager |
| `AggregationService` | `topTitlesByViewers(limit)`, `catalogSummaryByGenre()` | FT.AGGREGATE report generation |
| `BenchmarkService` | `benchmarkSearch(query, iterations)`, `benchmarkResume(userId, catalogId, iterations)`, `benchmarkAggregate(reportName, iterations)` | Timing harness for performance measurement |

### ui/

See [design-frontend.md](design-frontend.md) for UI class design and layout details.

## Application Configuration

Non-user-specific configuration is loaded from `config.yaml` in the working directory (falls back to defaults if absent).

```yaml
valkey:
  host: localhost
  port: 6379
```

Loaded at startup by `AppConfig` into a record. `ValkeyClientProvider` reads host/port from this config rather than command-line arguments or environment variables.

| Class | Responsibility |
|---|---|
| `AppConfig` | Loads `config.yaml` from the working directory via SnakeYAML. Provides typed accessors (`valkeyHost()`, `valkeyPort()`). Falls back to defaults if file is missing or fields are absent. |

## Startup Sequence

1. `AppConfig.load()` → load `config.yaml` from working directory (defaults if absent)
2. `FlicEnjoyerApp.start()` → create `ValkeyClientProvider` using config (host, port)
2. `UserProfileManager.load()` → if `~/.flicenjoyer/profile.yaml` exists, load userId and displayName; otherwise show a prompt dialog for the user's full name, generate a UUID, and persist the profile
3. `IndexManager.ensureIndexes()` → check FT._LIST, create `idx:catalog` and `idx:watch` if missing
4. `WatchHistoryService.getUserHistory()` → hydrate any existing watch state for this userId
5. Launch JavaFX stage with `MainController`

## Local Media Storage

Uploaded videos and thumbnails are stored at `~/.flicenjoyer/media/`:
- Videos: `~/.flicenjoyer/media/videos/{catalogId}.{ext}`
- Thumbnails: `~/.flicenjoyer/media/thumbnails/{catalogId}.{ext}`

`UploadService` copies the user-selected files to these paths and stores the absolute paths in the Valkey catalog hash. The catalog starts empty — all content is user-uploaded.

### Session State

On first launch, the user is prompted for their full name and a UUID is generated as their userId. This profile is persisted locally at `~/.flicenjoyer/profile.yaml`. Each session starts with whatever watch history already exists in Valkey for that userId — a brand new user starts empty.

## Performance Benchmarking

`BenchmarkService` runs each operation N times (configurable, default 1000) and reports:
- Median latency
- p95 latency
- p99 latency
- Operations per second
- Dataset size at time of benchmark (catalog count, watch history count)

Target benchmarks from acceptance criteria:
- Typeahead search: < 10ms median
- Resume point retrieval: < 1ms median
- Aggregation reports: documented with dataset size

Results displayed in `BenchmarkView` and printed to stdout for README documentation.

## Error Handling

- `ValkeyClientProvider` fails fast on connection error with clear message (host, port, cause)
- `IndexManager` catches "index already exists" responses gracefully
- `UploadService` validates required fields before writing to Valkey
- Service methods wrap Valkey exceptions in domain-specific exceptions with context

## Known Limitations

- **Volume/mute delay (~500ms)** — JavaFX `MediaPlayer` applies volume and mute changes asynchronously to its internal audio buffer. This causes a noticeable ~500ms delay between adjusting the volume slider or toggling mute and hearing the effect. The delay is present during playback and is especially noticeable when changing volume while paused and then resuming. This is a JavaFX platform limitation with no available workaround.

## Utilities

- `ResetData` — CLI utility (`./gradlew resetData`) that deletes all `catalog:*` and `watch:*` keys from Valkey and removes `~/.flicenjoyer/media/`. Uses `AppConfig` for connection settings.
- Icons are individual SVG files in `src/main/resources/icons/`, each containing a `<path>` with `data-filled` attribute. `IconLoader` parses them at startup. To add an icon, create the SVG file and register its name in `IconLoader.ICON_NAMES`.

## Integration Testing

Integration tests live in `src/integrationTest/java/` and use Testcontainers to run against a live Valkey instance. Run with `gradle integrationTest` — not part of the unit test suite or coverage gate.

Currently gated behind `FLICENJOYER_INTEGRATION_TESTS=true` environment variable. Uses the `valkey/valkey-bundle:unstable` Docker image via Testcontainers, which bundles ValkeySearch with FTS support. The `docker-java.properties` file in `src/integrationTest/resources/` sets `api.version=1.44` for Docker 29+ compatibility with Testcontainers.

### Proven capabilities

The integration tests verify:
- FT.CREATE with TEXT (withSuffixTrie, sortable), TAG (separator, sortable), and NUMERIC (sortable) fields
- WEIGHT must be 1.0 — custom weights not yet supported by ValkeySearch 1.2
- Exact search, prefix search (`@title:Incep*`), tag filter (`@genre:{Sci\-Fi}`)
- SORTBY on numeric fields
- CatalogService round-trip: `searchPrefix`, `searchFuzzy`, `browseByGenre`
- Genre escaping handled by `escapeTag` (e.g., `Sci-Fi` → `Sci\-Fi`)
