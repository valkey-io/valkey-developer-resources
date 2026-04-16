# Project Structure — FlicEnjoyer

## Directory Layout

```
apps/fts/
├── sdd/                                # Steering design documents
├── src/main/java/
│   ├── ui/                             # JavaFX views, controllers, and UI utilities
│   ├── service/                        # Business logic services
│   ├── valkey/                         # Valkey client setup, index management, config
│   └── model/                          # Domain records and enums
├── src/main/resources/                 # FXML layouts, CSS, logging.properties
├── src/test/java/                      # Unit tests mirroring src/main/java package structure
├── src/integrationTest/java/           # Integration tests (Testcontainers)
├── src/integrationTest/resources/      # docker-java.properties for Testcontainers
├── docker-compose.yml                  # Local Valkey + ValkeySearch
├── docker-compose.yml                   # Valkey + ValkeySearch via valkey-bundle image
├── config.yaml                         # Application config (Valkey host/port, etc.)
├── build.gradle.kts                    # Gradle build config
└── README.md
```

## Packaging

- Single Gradle project using Kotlin DSL
- JavaFX dependencies managed via Gradle
- Fat JAR or `application` plugin for distribution

## Module Organization

- `valkey/` — all Valkey interaction (client init, FT.CREATE indexes, config loading)
- `service/` — domain logic: catalog search, video upload, session hydration, aggregation reports
- `ui/` — JavaFX views, controllers, and shared UI utilities (e.g., background tasks, notifications)
- `model/` — domain records and enums shared across all layers

See [design-backend.md](design-backend.md) and [design-frontend.md](design-frontend.md) for specific class inventories.

## Naming Conventions

- Packages: lowercase dot-separated (`ui`, `service`, `valkey`, `model`)
- Classes: PascalCase (`CatalogService`, `SearchView`, `Movie`)
- Methods/fields: camelCase
- FXML files: kebab-case (`search-view.fxml`, `catalog-view.fxml`)

## Import Patterns

- `ui` depends on `service` and `model`
- `service` depends on `valkey` and `model`
- `valkey` depends on `model` and `valkey-glide`
- `model` has no internal dependencies

## Key Architectural Decisions

### GLIDE Client, Not Jedis/Lettuce

This project uses valkey-glide as the Valkey client library. Refer to the GLIDE skill (`../../skills/glide/`) for patterns.

### Layered Architecture

UI controllers contain no Valkey logic — they delegate to service classes which own all data access through the valkey layer.

### Data on Startup

The application creates FTS indexes via FT.CREATE on startup if they don't already exist. The catalog starts empty — all content is added by the user through the Upload view. User identity is established on first launch via a name prompt, generating a UUID persisted locally at `~/.flicenjoyer/profile.yaml`. Uploaded videos and thumbnails are stored at `~/.flicenjoyer/media/`. Watch history is scoped to this userId and starts empty for new users.

## File Relationships

- `valkey/` is the only layer that imports `valkey-glide` directly
- `service/` depends on `valkey/` for all data access
- `ui/` depends on `service/` for business logic
- `model/` is shared across all layers

## Testing

### Structure

- Unit tests live in `src/test/java/` mirroring the main source package structure
- Integration tests live in `src/integrationTest/java/` mirroring the main source package structure
- Each service class has a corresponding test class (e.g., `CatalogServiceTest`, `WatchHistoryServiceTest`)
- UI controllers are not unit tested — coverage focus is on `service/` and `valkey/` layers
- Integration tests exercise interop with a live Valkey instance via Testcontainers

### Policy

- Minimum 70% line coverage enforced via JaCoCo Gradle plugin on service, valkey, and model layers. UI package (`com.flicenjoyer.ui`) and app entry points (`FlicEnjoyerApp`, `ResetData`) are excluded from the coverage gate.
- Valkey interactions are mocked with Mockito (mock `GlideClient` and its return values) — unit tests must not require a running Valkey instance
- Unit tests run as part of the standard `gradle test` task
- Integration tests run via `gradle integrationTest` — separate from unit tests, no hard coverage requirement
- Coverage report generated on every build; build fails if unit test threshold is not met

## Linting & Formatting

- Spotless Gradle plugin with google-java-format enforces consistent code style
- `gradle spotlessCheck` verifies formatting; `gradle spotlessApply` auto-fixes
- Build fails if formatting violations are present
