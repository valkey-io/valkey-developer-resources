# FlicEnjoyer

A streaming platform demo app showcasing [ValkeySearch 1.2](https://github.com/valkey-io/Valkey-Search) Full Text Search capabilities — catalog search with typeahead and fuzzy matching, user watch history with resume, and offline analytics via FT.AGGREGATE.

Built with Java 26, JavaFX, and [valkey-glide](https://github.com/valkey-io/valkey-glide).

Part of the [Valkey-Samples](https://github.com/valkey-io/Valkey-Samples) repository.

## Prerequisites

- **Java 26** — set `JAVA_HOME` to point to your JDK 26 installation
- **Docker** — for running Valkey and PostgreSQL

## Setup

### 1. Start Valkey

```bash
docker compose up -d
```

The app connects to Valkey and PostgreSQL on `localhost` via port mappings (`6379` and `5432`). If these ports are already in use on your machine, update the host ports in `docker-compose.yml` and `config.yaml` to match.

### 2. Run the app

```bash
./gradlew run
```

On first launch you'll be prompted for your name. Your profile is saved to `~/.flicenjoyer/profile.yaml`.

## Features

- **Upload** — Add videos with title, genre, description, tags, and optional thumbnail
- **Search** — Typeahead prefix search with automatic fuzzy fallback for misspellings
- **Browse** — Filter catalog by genre with sortable results
- **Watch History** — Resume playback from where you left off, per-user session state
- **Reports** — FT.AGGREGATE analytics: top titles by viewer count, catalog summary by genre
- **Benchmarks** — Compare PostgreSQL-direct vs Valkey-cached throughput under concurrent load (catalog, resume, search)

## Development

### Run tests

```bash
./gradlew test
```

### Run integration tests

Integration tests use Testcontainers and are currently gated (ValkeySearch 1.2 FTS not yet complete in available images):

```bash
FLICENJOYER_INTEGRATION_TESTS=true ./gradlew integrationTest
```

### Reset data

Erase all catalog and watch history from Valkey and clean local media files:

```bash
./gradlew resetData
```

### Backup / restore database

The PostgreSQL database is ephemeral (no Docker volume). Back up before `docker compose down`:

```bash
./gradlew dbBackup    # saves to backups/flicenjoyer.sql
./gradlew dbRestore   # restores from backups/flicenjoyer.sql
```

The dump file is stored at `backups/flicenjoyer.sql` in the project root (git-ignored). It contains a full `pg_dump` with `--clean --if-exists`, so restoring drops and recreates tables automatically.


### Icons

App icons are individual SVG files in `src/main/resources/icons/`. To add a new icon, create an SVG file with a `<path>` element (and optional `data-filled="true"` attribute) and register its name in `IconLoader.ICON_NAMES`.

### Format code

```bash
./gradlew spotlessApply
```

### Check formatting

```bash
./gradlew spotlessCheck
```

## Project Structure

```
src/main/java/com/flicenjoyer/
├── FlicEnjoyerApp.java          # JavaFX Application entry point
├── BenchmarkCli.java            # CLI benchmark runner
├── SeedData.java                # Seeds demo catalog + watch history
├── UnseedData.java              # Removes seeded demo data
├── ResetData.java               # Erases all data from Valkey + local media
├── model/                       # Domain records and enums
│   ├── Movie.java
│   ├── Genre.java
│   ├── WatchHistoryEntry.java
│   └── AggregationResult.java
├── db/                          # PostgreSQL repositories and connection pool
│   ├── DatabaseProvider.java
│   ├── CatalogRepository.java
│   └── WatchHistoryRepository.java
├── valkey/                      # Valkey client, config, indexing, utilities
│   ├── AppConfig.java
│   ├── AppPaths.java
│   ├── ValkeyClientProvider.java
│   ├── ValkeyClient.java
│   ├── GlideValkeyClient.java
│   ├── ValkeyKeys.java
│   ├── IndexManager.java
│   ├── UserProfileManager.java
│   ├── HashParser.java
│   └── QueryEscaper.java
├── service/                     # Business logic (cache-aside orchestration)
│   ├── CatalogService.java
│   ├── UploadService.java
│   ├── WatchHistoryService.java
│   ├── AggregationService.java
│   └── BenchmarkService.java
└── ui/                          # JavaFX views and UI utilities
    ├── MainController.java
    ├── SearchView.java
    ├── CatalogView.java
    ├── VideoFormView.java
    ├── PlayerView.java
    ├── WatchHistoryView.java
    ├── BenchmarkView.java
    ├── ReportsView.java
    ├── AdminView.java
    ├── PlaybackState.java
    ├── BackgroundTask.java
    ├── DataLoader.java
    ├── UiExecutors.java
    ├── UiFactory.java
    ├── MovieCard.java
    ├── StarRating.java
    ├── IconLoader.java
    ├── NotificationBanner.java
    ├── FxThread.java
    └── ViewId.java
```

## Configuration

| File | Location | Purpose |
|---|---|---|
| `config.yaml` | Project root | Valkey host/port |
| `~/.flicenjoyer/profile.yaml` | Home dir | User identity (name + UUID) |
| `~/.flicenjoyer/media/` | Home dir | Uploaded videos and thumbnails |

## Benchmarking

FlicEnjoyer includes a benchmark tool that compares PostgreSQL-direct vs Valkey-cached throughput under concurrent load.

```bash
./gradlew benchmark --args="--threads=64 --ops=500 --operation=catalog"
./gradlew benchmark --args="--threads=64 --ops=500 --operation=resume"
./gradlew benchmark --args="--threads=64 --ops=500 --operation=search"
```

### Why PostgreSQL is configured with minimal buffers

The `docker-compose.yml` configures PostgreSQL with `shared_buffers=128kB` and `work_mem=64kB`. This is intentional and simulates realistic production conditions:

- In production, PostgreSQL's `shared_buffers` is typically 25% of system RAM (e.g., 4GB on a 16GB instance), but the working dataset is often 10–100× larger. Most queries must fetch pages from the OS page cache or disk — not from PostgreSQL's hot buffer pool.
- Our demo dataset is tiny (50–100 rows) and would trivially fit in any buffer cache, making PostgreSQL appear artificially fast for simple lookups.
- By constraining `shared_buffers` to 128kB, we force PostgreSQL to evict pages on every query — simulating the buffer cache miss rate that real applications experience when their working set exceeds available memory.
- Valkey, by contrast, **always** serves from memory regardless of dataset size. That is its core value proposition as a caching layer.

This configuration does not make PostgreSQL artificially slow — it prevents PostgreSQL from being artificially fast on a trivially small dataset. The benchmark demonstrates what happens when you add Valkey in front of a database whose buffer cache cannot hold your entire working set, which is the normal case in production.

### Workload profile

Each benchmark uses a **7:1 read/write mix** (87.5% reads, 12.5% writes) — realistic for content platforms where reads dominate. Both the DB-direct and Valkey-cached paths perform identical database work on writes; the difference is that the Valkey path serves reads from cache without touching the database.

## Known Limitations

- **Volume/mute delay (~500ms)** — JavaFX `MediaPlayer` applies volume and mute changes asynchronously to its internal audio buffer. This causes a noticeable ~500ms delay between adjusting the volume slider or toggling mute and hearing the effect. The delay is present during playback and is especially noticeable when changing volume while paused and then resuming. This is a JavaFX platform limitation with no available workaround.

## Design Documents

See `sdd/` for the full steering design documents:

- `product.md` — Product overview, scope, success criteria
- `tech.md` — Technology stack, dependencies, tooling
- `structure.md` — Project structure, naming conventions, testing policy
- `design-backend.md` — Data model, Valkey schemas, service design
- `design-frontend.md` — UI/UX design, navigation, view layouts
- `glide-vss-1.2-api.md` — GLIDE ValkeySearch 1.2 API reference
- `mockups.html` — Interactive HTML mockups (open in browser)
