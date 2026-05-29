# Project Structure — FlicEnjoyer

## Directory Layout

```
apps/fts/
├── sdd/                                # Steering design documents
├── src/main/java/
│   ├── ui/                             # JavaFX views, controllers, and UI utilities
│   ├── service/                        # Business logic services (cache-aside orchestration)
│   ├── db/                             # PostgreSQL repositories and connection pool
│   ├── valkey/                         # Valkey client setup, index management, config
│   └── model/                          # Domain records and enums
├── src/main/resources/                 # FXML layouts, CSS, logging.properties, schema.sql
├── src/test/java/                      # Unit tests mirroring src/main/java package structure
├── src/integrationTest/java/           # Integration tests (Testcontainers)
├── src/integrationTest/resources/      # docker-java.properties for Testcontainers
├── docker-compose.yml                  # Local Valkey + ValkeySearch + PostgreSQL
├── config.yaml                         # Application config (Valkey host/port, DB connection)
├── build.gradle.kts                    # Gradle build config
└── README.md
```

## Packaging

- Single Gradle project using Kotlin DSL
- JavaFX dependencies managed via Gradle
- Fat JAR or `application` plugin for distribution

## Module Organization

- `db/` — PostgreSQL interaction (connection pool, JDBC repositories)
- `valkey/` — all Valkey interaction (client init, FT.CREATE indexes, config loading, cache operations)
- `service/` — domain logic with cache-aside orchestration: reads check Valkey first, fall back to DB; writes go to DB then update cache
- `ui/` — JavaFX views, controllers, and shared UI utilities (e.g., background tasks, notifications)
- `model/` — domain records and enums shared across all layers

See [design-backend.md](design-backend.md) and [design-frontend.md](design-frontend.md) for specific class inventories.

## Naming Conventions

- Packages: lowercase dot-separated (`ui`, `service`, `db`, `valkey`, `model`)
- Classes: PascalCase (`CatalogService`, `CatalogRepository`, `SearchView`, `Movie`)
- Methods/fields: camelCase
- FXML files: kebab-case (`search-view.fxml`, `catalog-view.fxml`)

## Import Patterns

- `ui` depends on `service` and `model`
- `service` depends on `db`, `valkey`, and `model`
- `db` depends on `model`
- `valkey` depends on `model` and `valkey-glide`
- `model` has no internal dependencies

## Key Architectural Decisions

### PostgreSQL as Source of Truth

All persistent data lives in PostgreSQL. Valkey is a caching and search acceleration layer — if Valkey is flushed, the app recovers by re-syncing from the database on next startup.

### GLIDE Client, Not Jedis/Lettuce

This project uses valkey-glide as the Valkey client library. Refer to the GLIDE skill (`../../skills/glide/`) for patterns.

### Cache-Aside Pattern

Services orchestrate the cache-aside logic:
- **Reads:** Check Valkey cache → miss → query DB → populate cache → return
- **Writes:** Write to DB → update Valkey cache (and ValkeySearch auto-indexes the hash)

No TTL-based expiry — cache is explicitly managed on writes for deterministic benchmark behavior.

### Layered Architecture

UI controllers contain no DB or Valkey logic — they delegate to service classes which orchestrate data access across both the db and valkey layers.

### Data on Startup

The application creates PostgreSQL tables via `schema.sql` on startup if they don't exist. FTS indexes are created via FT.CREATE if missing. `IndexManager.syncFromDatabase()` populates Valkey hashes from DB data so ValkeySearch indexes are warm. The catalog starts empty — all content is added by the user through the Upload view.

## File Relationships

- `db/` is the only layer that imports JDBC/HikariCP directly
- `valkey/` is the only layer that imports `valkey-glide` directly
- `service/` depends on both `db/` and `valkey/` for cache-aside orchestration
- `ui/` depends on `service/` for business logic
- `model/` is shared across all layers

## Testing

### Structure

- Unit tests live in `src/test/java/` mirroring the main source package structure
- Integration tests live in `src/integrationTest/java/` mirroring the main source package structure
- Each service class has a corresponding test class (e.g., `CatalogServiceTest`, `WatchHistoryServiceTest`)
- Repository classes have unit tests with mocked DataSource/Connection
- UI controllers are not unit tested — coverage focus is on `service/`, `db/`, and `valkey/` layers
- Integration tests exercise interop with live Valkey and PostgreSQL instances via Testcontainers

### Policy

- Minimum 70% line coverage enforced via JaCoCo Gradle plugin on service, db, valkey, and model layers. UI package (`com.flicenjoyer.ui`) and app entry points (`FlicEnjoyerApp`, `ResetData`) are excluded from the coverage gate.
- Valkey interactions are mocked with Mockito (mock `GlideClient` and its return values) — unit tests must not require a running Valkey instance
- DB interactions are mocked with Mockito (mock `DataSource`/`Connection`/`PreparedStatement`) — unit tests must not require a running PostgreSQL instance
- Unit tests run as part of the standard `gradle test` task
- Integration tests run via `gradle integrationTest` — separate from unit tests, no hard coverage requirement
- Coverage report generated on every build; build fails if unit test threshold is not met

## Linting & Formatting

- Spotless Gradle plugin with google-java-format enforces consistent code style
- `gradle spotlessCheck` verifies formatting; `gradle spotlessApply` auto-fixes
- Build fails if formatting violations are present
