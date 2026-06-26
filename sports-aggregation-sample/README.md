# ValkeySearch Live GHL Analytics

A sample application demonstrating ValkeySearch aggregation features through a live Galactic Hockey League (GHL) sports streaming analytics dashboard. The app simulates real-time hockey games and uses ValkeySearch to power trending match rankings, win probability calculations, and live scoreboard updates.

> **Note:** This app uses the `valkey-bundle:9.1` Docker image which includes ValkeySearch.

## What This Demonstrates

This app showcases how to use **Valkey** with **ValkeySearch** for real-time analytics workloads:

- **FT.CREATE** — Defining a search index on live game data stored as Valkey Hashes
- **FT.SEARCH** — Querying game state with TAG filters and NUMERIC range queries
- **FT.AGGREGATE** — Server-side aggregation to rank trending matches by viewer engagement
- **HSET** — Storing structured game state as Hashes (auto-indexed by ValkeySearch)
- **ZADD** — Sorted Sets for viewer-ranked game tracking
- **XADD** — Streams for append-only game event logs (goals, shots, penalties)
- **PUBLISH / SUBSCRIBE** — Pub/Sub for event-driven updates (feeder notifies webapp instantly)
- **Server-Sent Events (SSE)** — Pushing real-time updates from Valkey to the browser

## Prerequisites

| Dependency | Version | Source |
|---|---|---|
| **Valkey Server + ValkeySearch** | 9.1 | [valkey/valkey-bundle](https://hub.docker.com/r/valkey/valkey-bundle) (Docker Hub) |
| **Valkey Glide** (Java) | 2.4.0 | [Maven Central](https://central.sonatype.com/artifact/io.valkey/valkey-glide) |

You also need:

| Tool | Version | Purpose |
|---|---|---|
| **Docker Desktop** | 24+ | Running Valkey |
| **Java** | 17+ | Building and running the Kotlin app |

## Getting Started

### Option A — Docker Compose (recommended)

Run the full stack with one command:

```bash
docker compose up
```

This pulls the `valkey-bundle:9.1` image (includes ValkeySearch), builds the Kotlin app, and starts everything. Open [http://localhost:8080](http://localhost:8080) to see the live dashboard.

To rebuild after code changes:

```bash
docker compose build feeder webapp
docker compose up
```

### Option B — Gradle (local development)

Start Valkey via Docker, then run the app locally:

```bash
# Start Valkey
docker compose up -d valkey

# Build and run the app
cd app
./gradlew build
./gradlew :feeder:run &          # start game simulator in background
./gradlew :webapp:bootRun        # start web dashboard
```

Open [http://localhost:8080](http://localhost:8080).

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Feeder (Kotlin CLI)                                             │
│  Simulates 4 concurrent GHL games, generates events every 2s     │
│  Writes to Valkey: HSET (game state), ZADD (rankings),           │
│                    XADD (event stream), PUBLISH (notification)   │
└──────────────┬───────────────────────────────────────────────────┘
               │ Valkey Glide Client
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Valkey + ValkeySearch Module                                    │
│                                                                  │
│  game:{id}  → Hash (live game state, auto-indexed)               │
│  idx:games  → Search Index (TAG, NUMERIC, TEXT fields)           │
│  events:{id}→ Stream (goal, shot, penalty, hit events)           │
│  active_games → Sorted Set (games ranked by viewers)             │
│  game:updates → Pub/Sub Channel (feeder → webapp notification)   │
│                                                                  │
│  FT.SEARCH   → filtered game retrieval                           │
│  FT.AGGREGATE → server-side trending calculation                 │
└──────────────┬───────────────────────────────────────────────────┘
               │ Valkey Glide Client
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Webapp (Spring Boot + Kotlin)                                   │
│                                                                  │
│  GameDataService  → queries Valkey (FT.SEARCH, FT.AGGREGATE)     │
│  SseController    → pushes updates to browsers via Pub/Sub+SSE   │
│  ApiController    → REST endpoints + benchmark runner            │
│  HomeController   → Thymeleaf initial page render                │
└──────────────┬───────────────────────────────────────────────────┘
               │ Server-Sent Events (SSE)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Browser (Vanilla JS)                                            │
│                                                                  │
│  EventSource('/api/sse/games') receives updates                  │
│  Updates DOM: scoreboard, trending list, win probability bars    │
│  No framework — just native SSE + template literals              │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Feeder** generates game events → writes to Valkey via `HSET`, `ZADD`, `XADD`
2. **Feeder** publishes a notification on the `game:updates` channel (`PUBLISH`)
3. **ValkeySearch** automatically indexes hash updates in real time
4. **Webapp** subscriber client receives the Pub/Sub message (event-driven, no polling)
5. **Webapp** queries Valkey via `FT.SEARCH` and `FT.AGGREGATE` for latest state
6. **SseController** pushes JSON payloads to all connected browsers via SSE
7. **Browser JS** receives SSE events and updates the DOM (scoreboard, trending, win probability)

No polling anywhere in the pipeline. Feeder → Pub/Sub → Webapp → SSE → Browser.

## Project Structure

```
app/
├── common/                          # Shared models and Valkey utilities
│   └── src/main/kotlin/.../
│       ├── model/
│       │   ├── Models.kt            # GameState, GameEvent, TrendingMatch, WinProbability
│       │   └── GhlTeams.kt          # All 32 GHL teams with divisions/conferences
│       └── valkey/
│           ├── Keys.kt              # Valkey key naming conventions (★ documented)
│           └── ValkeyConnection.kt  # Glide client factory
│
├── feeder/                          # Game simulation + Valkey data writer
│   └── src/main/kotlin/.../feeder/
│       ├── Main.kt                  # Entry point, config from env vars
│       ├── GameSimulator.kt         # Simulates one GHL game with realistic events
│       └── FeederService.kt         # Writes to Valkey, creates search index (★ documented)
│
├── webapp/                          # Spring Boot web application
│   └── src/main/kotlin/.../webapp/
│       ├── Application.kt           # Spring Boot entry point
│       ├── config/
│       │   └── ValkeyConfig.kt      # Glide client Spring bean
│       ├── service/
│       │   └── GameDataService.kt   # FT.SEARCH + FT.AGGREGATE queries (★ documented)
│       └── controller/
│           ├── HomeController.kt    # Thymeleaf initial page render
│           ├── SseController.kt     # SSE push to browsers (★ documented)
│           └── ApiController.kt     # REST API + benchmarks (★ documented)
│   └── src/main/resources/
│       ├── templates/index.html     # Dashboard page (Thymeleaf + SSE)
│       ├── static/js/app.js         # SSE client + DOM updates (★ documented)
│       ├── static/css/style.css     # Dark theme dashboard styles
│       └── application.yml          # Server and Valkey connection config
│
├── build.gradle.kts                 # Root build (Kotlin 1.9, JVM 17, Glide 2.3.1)
└── settings.gradle.kts              # Multi-module: common, feeder, webapp

docker/
├── valkey/Dockerfile                # Simple — pulls valkey-bundle:9.1 (includes ValkeySearch)

docker-compose.yaml                  # Orchestrates Valkey, feeder, and webapp
```

Files marked with ★ contain detailed inline documentation explaining Valkey features used and the data flow.

## Configuration

Both the feeder and webapp connect to Valkey via environment variables:

| Variable | Default | Description |
|---|---|---|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `NUM_GAMES` | `8` | Number of simultaneous games to simulate |
| `TICK_INTERVAL_MS` | `2000` | Milliseconds between game simulation ticks |

## ValkeySearch Queries Used

### FT.CREATE — Index Definition
```
FT.CREATE idx:games ON HASH PREFIX 1 game: SCHEMA
  homeTeam TAG  awayTeam TAG  status TAG
  homeScore NUMERIC SORTABLE  awayScore NUMERIC SORTABLE
  viewers NUMERIC SORTABLE  period NUMERIC SORTABLE
  homeShots NUMERIC SORTABLE  awayShots NUMERIC SORTABLE
  ...
```
See: [`FeederService.kt`](app/feeder/src/main/kotlin/com/valkey/sports/feeder/FeederService.kt)

### FT.SEARCH — Filtered Game Retrieval
```
FT.SEARCH idx:games @status:{live|pregame|intermission} LIMIT 0 20
FT.SEARCH idx:games @startTime:[0 +inf] LIMIT 0 20
```
See: [`GameDataService.kt`](app/webapp/src/main/kotlin/com/valkey/sports/webapp/service/GameDataService.kt)

### FT.AGGREGATE — Trending Matches
```
FT.AGGREGATE idx:games @status:{live}
  LOAD 10 @homeTeam @awayTeam @homeScore @awayScore @period
         @timeRemaining @status @viewers @homeShots @awayShots
  APPLY @viewers AS trendScore
  SORTBY 2 @trendScore DESC
  LIMIT 0 10
```
See: [`GameDataService.kt`](app/webapp/src/main/kotlin/com/valkey/sports/webapp/service/GameDataService.kt)

## Performance Benchmarks

The app includes a built-in benchmark accessible at `/api/benchmark?iterations=100` or via the dashboard UI button. It measures round-trip latency for each query type:

| Query | What it measures |
|---|---|
| FT.SEARCH all games | Full index scan with numeric range filter |
| FT.SEARCH active games | TAG filter on game status |
| FT.AGGREGATE trending | Server-side aggregation with LOAD, APPLY, SORTBY |
| Win probability calc | FT.SEARCH + application-level sigmoid computation |
