# Technology Stack — FlicEnjoyer

## Runtime

- Java 26
- JavaFX (GUI frontend)
- Gradle (build system)
- Use Java 21+ language features: records, `instanceof` pattern matching, `.toList()` on streams, `List.of()` / `Map.of()` for immutable collections, `var` for local type inference
- Accessibility: keyboard shortcuts for key interactions where applicable (e.g., media playback keys, numeric keys for rating)
- Non-blocking UI: no Valkey calls, disk I/O, or network I/O on the JavaFX Application Thread. All data access must be async. Thumbnails use `backgroundLoading=true` with `preserveRatio=true` fit-within scaling (no cropping or stretching). See [design-frontend.md](design-frontend.md#threading--non-blocking-ui) for patterns and principles.

### Runtime Dependencies

- `valkey-glide` (Java) — Valkey client library, version 2.4.1 from Maven Central. Includes ValkeySearch 1.2 command support (FT.CREATE, FT.SEARCH, FT.AGGREGATE, FT.INFO).
- See [glide-vss-1.2-api.md](glide-vss-1.2-api.md) for a summary of the FT.CREATE, FT.SEARCH, FT.AGGREGATE, and FT.INFO APIs. Refer to the [valkey-glide Java source](https://github.com/valkey-io/valkey-glide/tree/main/java) for full API contracts.
- PostgreSQL JDBC driver (`org.postgresql:postgresql:42.7.4`) — JDBC connectivity to PostgreSQL
- HikariCP (`com.zaxxer:HikariCP:6.2.1`) — High-performance JDBC connection pool
- JavaFX SDK — desktop GUI toolkit (controls, fxml, media, swing modules)
- SnakeYAML — YAML parsing/writing for local data files (user profile, application config)

### Icons

All app icons (player transport, navigation, status) are individual SVG files in `src/main/resources/icons/`. Each file contains a single `<path>` element with a `data-filled` attribute. At runtime, `IconLoader` parses the SVG path data and renders icons as JavaFX `SVGPath` nodes — scalable and resolution-independent. To add a new icon, drop an SVG file in the icons directory and register its name in `IconLoader.ICON_NAMES`.

### Local Data Format

- Use YAML (not JSON) for project-controlled local data files (user profile, application config). Video metadata is stored in Valkey, not locally.
- Application config (`config.yaml`) in the working directory for non-user-specific settings (e.g., Valkey host/port)
- Valkey's own data format (Hashes, JSON module if used) is unaffected — this constraint applies only to files we read/write locally
- Local file-based storage for uploaded videos and thumbnails

### Explicitly Excluded Dependencies

- `jedis`, `lettuce` — this project uses valkey-glide exclusively
- `elasticsearch`, `opensearch` — search is handled entirely by ValkeySearch FTS
- Node.js, React, or any JavaScript/TypeScript tooling
- External logging frameworks (SLF4J, Log4j, Logback) — uses `java.util.logging` (JUL) only
- ORM frameworks (Hibernate, JPA) — uses plain JDBC for simplicity and transparency in a sample app

## Valkey Client Patterns — GLIDE Skill Reference

For valkey-glide usage patterns, anti-patterns, and configuration, refer to the [valkey-glide documentation](https://github.com/valkey-io/valkey-glide).
However, prioritize using [glide-vss-1.2-api.md](glide-vss-1.2-api.md) for specific API syntax and contract, where applicable, over associated prescriptions in the skill, as it is more up-to-date than the skill. 

## Valkey Server Requirements

- Base image: `valkey/valkey-bundle:unstable` — bundles Valkey server with ValkeySearch, JSON, Bloom, and other modules pre-loaded
- ValkeySearch >= 1.2 required for FTS and FT.AGGREGATE — included in the bundle image
- `docker compose up` builds and runs the custom image automatically
- Reference: https://hub.docker.com/r/valkey/valkey

## PostgreSQL Requirements

- Image: `postgres:17` — latest stable PostgreSQL
- Database `flicenjoyer` created automatically via `POSTGRES_DB` env var
- Schema applied on application startup via `DatabaseProvider` running `schema.sql`
- `docker compose up` starts PostgreSQL alongside Valkey

## Development Tooling

- Java 26
- Gradle with Kotlin DSL
- JUnit 5 for unit testing
- Mockito for mocking Valkey interactions (GlideClient) in unit tests — service and valkey layer methods that call Valkey must be tested via mocked GlideClient, not a live instance
- JaCoCo for code coverage enforcement (minimum 70% line coverage on service/valkey/model layers; UI package and app entry points excluded from the gate)
- Spotless with google-java-format for consistent code formatting
- Docker Compose for local Valkey server with ValkeySearch module and PostgreSQL database
- Testcontainers (`org.testcontainers:testcontainers` + `junit-jupiter` + `postgresql`) for integration tests against `valkey/valkey-bundle:unstable` and `postgres:17`. See [design-backend.md](design-backend.md#integration-testing) for details.

## Packaging & Distribution

- Single Gradle project using Kotlin DSL
- Gradle `application` plugin for local development (`./gradlew run`)
- Turnkey `docker-compose` stack: `docker compose up` pulls `valkey/valkey-bundle:unstable` and `postgres:17`, ready for the app to connect.

## Compatibility

- Communicates with PostgreSQL via standard JDBC (primary datastore)
- Communicates with Valkey through standard Valkey commands and ValkeySearch module commands (caching + FTS)
- No Redis dependency — designed for Valkey from the ground up
- Standard commands: AUTH, PING, SELECT, HSET, HGETALL, HGET, CLIENT INFO, MODULE LIST
- ValkeySearch commands: FT._LIST, FT.INFO, FT.CREATE, FT.DROPINDEX, FT.SEARCH, FT.AGGREGATE
