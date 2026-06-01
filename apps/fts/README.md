# FlicEnjoyer

A streaming platform demo app showcasing [ValkeySearch 1.2](https://github.com/valkey-io/Valkey-Search) Full Text Search capabilities — catalog search with typeahead and fuzzy matching, user watch history with resume, and offline analytics via FT.AGGREGATE.

Built with Java 21, JavaFX, and [valkey-glide](https://github.com/valkey-io/valkey-glide).

Part of the [Valkey-Samples](https://github.com/valkey-io/Valkey-Samples) repository. See [Jira AEA-325](https://bitquill.atlassian.net) for the full story.

## Prerequisites

- **Java 21** — set `JAVA_HOME` to point to your JDK 21 installation
- **Docker** — for running Valkey
- **valkey-glide** — built locally from the `edlng/vss-1.2-commands` branch (see below)

## Setup

### 1. Start Valkey

```bash
docker compose up -d
```

The app connects to `localhost:6379` by default (configured in `config.yaml`). If port 6379 is already in use, change the host port in `docker-compose.yml` and update `config.yaml` to match.

### 2. Build valkey-glide locally

The app requires an unreleased version of valkey-glide with ValkeySearch 1.2 support:

```bash
cd ../../../valkey-glide/java
./gradlew :client:publishToMavenLocal -x test -x spotbugsMain -x spotbugsTest -x javadoc
```

This publishes `io.valkey:valkey-glide:255.255.255` to your local Maven repository. See `sdd/glide-vss-1.2-api.md` for details.

### 3. Run the app

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
- **Benchmarks** — Measure search, resume, and aggregation latency (median, p95, p99, ops/sec)

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
├── model/       # Records: Movie, WatchHistoryEntry, AggregationResult
├── valkey/      # AppConfig, ValkeyClientProvider, IndexManager, UserProfileManager
├── service/     # CatalogService, UploadService, WatchHistoryService, AggregationService, BenchmarkService
└── ui/          # MainController, UploadView (more views coming)
```

## Configuration

| File | Location | Purpose |
|---|---|---|
| `config.yaml` | Project root | Valkey host/port |
| `~/.flicenjoyer/profile.yaml` | Home dir | User identity (name + UUID) |
| `~/.flicenjoyer/media/` | Home dir | Uploaded videos and thumbnails |

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
