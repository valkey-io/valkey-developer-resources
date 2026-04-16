# Technical Design: Frontend — FlicEnjoyer

## Overview

JavaFX desktop GUI with a hamburger-menu navigation and card-grid content layout, styled after modern streaming platforms. All data access is delegated to the service layer — UI classes contain no Valkey logic.

## Application Entry Point

`FlicEnjoyerApp` extends `javafx.application.Application`:
1. Initializes `ValkeyClientProvider` (connect to Valkey)
2. Loads or creates user profile via `UserProfileManager`
3. Runs `IndexManager.ensureIndexes()`
4. Loads `MainController` and shows the primary stage

## Navigation

### Title Bar

Fixed header displaying: `☰ 🎬 FlicEnjoyer — {Current View Name}`

- Hamburger button (☰) on the left opens the navigation menu
- App name and current view name always visible
- View name updates on navigation (e.g., "Search", "Browse", "My History")

### Hamburger Menu

Slide-out panel from the left with a dark overlay backdrop. Contains six navigation items with icons:

| Menu Item | Icon | View Class | Service Dependency |
|---|---|---|---|
| Search | 🔍 | `SearchView` | `CatalogService` |
| Browse | 📂 | `CatalogView` | `CatalogService` |
| Upload | ⬆️ | `UploadView` | `UploadService` |
| My History | 📜 | `WatchHistoryView` | `WatchHistoryService` |
| Reports | 📊 | `ReportsView` | `AggregationService` |
| Benchmarks | ⚡ | `BenchmarkView` | `BenchmarkService` |

Player is not in the menu — it is navigated to programmatically from Browse, My History, or Search when a video is selected.

Active item is highlighted with a left border accent. Menu closes on item selection or overlay click.

## Content Layout

### Card Grid

Search, Browse, My History, and Reports (Top Titles) views use a responsive card grid instead of tables. Each card has:

- **Thumbnail**: User-uploaded thumbnail image rendered via `PlaybackState.loadThumbnail()`. Images are loaded asynchronously (`backgroundLoading=true`) and scaled to fit within the card's thumbnail area using `fitWidth`/`fitHeight` with `preserveRatio=true` — the image fits inside the container without distortion or overflow. Portrait and non-standard aspect ratios display with letterboxing (black bars) rather than cropping or stretching. Falls back to a gradient placeholder if no thumbnail is available.
- **Body**: Title (truncated with ellipsis), metadata (year, genre, duration), star rating
- **Hover**: Border highlight and slight upward translate
- **Selection**: Highlighted border and shadow (Search view)

Grid uses `auto-fill` with `minmax(180px, 1fr)` for responsive column count.

### Genre Thumbnail Colors

Each genre maps to a distinct gradient palette for visual differentiation:
- Sci-Fi: deep blue
- Action: red
- Crime: dark gray
- Drama: green
- Thriller: purple
- Comedy: gold
- Fantasy: sky blue

## View Details

### SearchView

- Search bar with 🔍 emoji, text input with debounced listener (300ms), and hint text ("typeahead + fuzzy fallback")
- Results displayed as a card grid
- Clicking a card selects it and opens a horizontal detail pane below the grid with:
  - Larger thumbnail on the left
  - Title, metadata, description, tags, and Play button on the right

### CatalogView

- Filter bar: genre `ComboBox` + sort `ComboBox` (rating, year, title)
- Results as a card grid showing all titles matching the filter

### WatchHistoryView

- Card grid with additional elements per card:
  - Status badge overlaid on thumbnail ("In Progress" amber / "Completed" green)
  - Timestamp overlay on thumbnail (e.g., "45:22 / 2:28:00") for in-progress titles
  - Progress bar beneath the card body (percentage fill)
  - Full-width "▶ Resume" button for in-progress titles; no button for completed titles
  - "Last watched" date in metadata

### UploadView

Form for adding new videos to the catalog.

- **Video file picker**: `FileChooser` filtered to common video formats (mp4, mkv, avi, mov). Displays selected filename.
- **Thumbnail file picker**: `FileChooser` filtered to image formats (png, jpg, jpeg). Shows a preview of the selected thumbnail.
- **Generate thumbnail (experimental)**: "Extract from video" button that loads the selected video into a temporary `MediaPlayer`, seeks to 10% of the duration, snapshots the `MediaView` frame, and saves it as the thumbnail. Marked experimental — may be dropped if codec/seeking issues prove too unreliable across platforms.
- **Text fields**: Title (required), Genre (ComboBox with fixed genre list from `Genre` enum — not editable), Description (TextArea), Tags (comma-separated text field), Release Year (spinner)
- **Upload button**: Validates required fields, calls `UploadService.uploadVideo()`, shows success confirmation, optionally navigates to Browse view
- **Validation**: Title and video file are required. Thumbnail is optional (genre gradient fallback used if absent).

- **Layout**: Two-column grid. Left column: metadata form fields (title, genre, year, description, tags). Right column: video file picker, thumbnail picker with preview. Below the grid: full-width row with the Upload button fixed-width and right-aligned.

**Layout** (FXML: `upload-view.fxml`):
```
┌─────────────────────┬────────────────────┐
│  Title:       [____]│  Video: [Choose]   │
│  Genre:       [▼  ] │  movie.mp4         │
│  Year:        [2026]│                    │
│  Description: [____]│  Thumb: [Choose]   │
│               [____]│  [Extract from vid]│
│  Tags:        [____]│  [preview]         │
├─────────────────────┴────────────────────┤
│                          [Upload Video]  │
└──────────────────────────────────────────┘
```

### PlayerView

Video player with seamless resume functionality using JavaFX `MediaPlayer` for local file playback.

- **Title display**: "Now Playing: {title}" with subtitle metadata
- **Video playback**: JavaFX `MediaView` backed by `MediaPlayer` loading the local video file from `videoPath` in the catalog hash. Basic playback only — no streaming, no transcoding.
- **Timeline scrubber**: Current time, range slider, total duration (monospace font)
- **Transport controls**: ⏮ ⏪ ▶ Play ⏩ ⏭ ⏹
- **Resume integration**: Loads resume point from `WatchHistoryService.getResumePoint()` and seeks to that position on open. Persists current position on pause/stop via `WatchHistoryService.updateResumePoint()`.
- **Auto-save**: Resume point persisted to Valkey every 3 seconds during playback, so progress is not lost on crash or unexpected exit.
- **Transport icons**: Individual SVG files in `src/main/resources/icons/`. `IconLoader` parses each file's `<path>` data and `data-filled` attribute at startup, rendering them as `SVGPath` nodes with an orange background. To add icons, drop an SVG file and register the name in `IconLoader.ICON_NAMES`.
- **Back navigation**: "<< Back to {source}" button at top of view, dynamically set based on which view launched the player.
- **Star rating**: 5-star rating widget in the top-right corner. Filled golden stars indicate the current rating (0–5). Click a star or press 0–5 keys to set the rating, persisted to Valkey immediately.
- **Opened from**: Resume button in WatchHistoryView or Play button in SearchView/CatalogView

### ReportsView

Two sections:

- **Top Titles by Viewers**: Card grid with thumbnail, title, large viewer count, and "viewers" label. Generate button in section header.
- **Catalog Summary by Genre**: Table (genre, title count, avg rating) — remains tabular as it's aggregate data with no title thumbnails. Generate button in section header.

### BenchmarkView

- Config bar: operation dropdown, iteration count spinner, Run button
- Progress bar with percentage
- Results as a 2×2 metric card grid: median, p95, p99, ops/sec

## Notifications

In-app notifications use a temporary overlay banner at the top of the current view, replacing modal dialogs for non-blocking feedback. Banners auto-dismiss after 4 seconds.

| Type | Background | Text | Emoji | Use Case |
|---|---|---|---|---|
| Success | `#2d6a4f` (green) | white | ✅ | Upload complete, action confirmed |
| Error | `#c73650` (red) | white | ❌ | Upload failed, connection error |
| Warning | `#b8860b` (dark yellow) | white | ⚠️ | Missing optional field, timeout fallback |

- Banners slide in from the top, overlay the view content, and fade out after 4 seconds
- Only one banner visible at a time — new notifications replace the current one
- Implemented as a shared `NotificationBanner` utility used by all views
- **Two variants**:
  - **Wide** (default) — full-width bar at the top, used for Upload and other form views
  - **Bubble** — fixed-width rounded pill anchored top-right, used for Player and other views where a wide banner would obstruct controls (e.g., back button)

## Logging

All UI operations that involve data interactions use `java.util.logging` (JUL) to log events with severity and tags to a local file that can be read by either a developer or an AI agent for troubleshooting or analysis.

- **Logger per class**: Each UI and service class obtains a logger via `Logger.getLogger(ClassName.class.getName())`
- **Severity levels**: `SEVERE` for errors/exceptions, `WARNING` for recoverable issues (e.g., missing thumbnail, codec failure), `INFO` for lifecycle events (upload started/completed, view navigated, extraction started), `FINE` for detailed diagnostics (Valkey round-trip times, file paths)
- **Tag convention**: Log messages are prefixed with a bracketed tag matching the operation: `[upload]`, `[browse]`, `[extract]`, `[player]`, `[config]`, `[valkey]`
- **Log file**: `~/.flicenjoyer/flicenjoyer.log`, configured via `logging.properties` on the classpath
- **Console output**: `INFO` and above also logged to stderr for development convenience
- **Configuration**: `src/main/resources/logging.properties` defines handlers, formatters, and levels. Loaded at startup in `FlicEnjoyerApp.main()` via `LogManager.getLogManager().readConfiguration()`
- **No external logging frameworks** — uses JUL only to avoid additional dependencies

## Threading & Non-Blocking UI

**Critical rule: no Valkey calls, disk I/O, or network I/O on the JavaFX Application Thread.** All data access — whether from Valkey, the filesystem, or any external source — must be asynchronous. Blocking the FX thread causes visible UI lag and unresponsive controls. This applies to image loading, file reads, and any operation that may take more than a few milliseconds.

### Patterns

- **`DataLoader<T>`** — serialized background data loader for view population (Browse, History, Administration). Uses a shared single-thread executor. Shows a spinner while loading. Supports cancellation on view leave.
- **`BackgroundTask`** — cancellable abstract task for one-off operations (upload, edit, delete). Runs on a shared single-thread executor. Delivers `onSuccess`/`onFailure`/`onCancelled`/`onFinally` callbacks on the FX thread.
- **`CompletableFuture.runAsync`** — fire-and-forget writes (persist resume point, rating, duration, watch state). No result needed on FX thread.
- **Typeahead search** — uses `AtomicReference<String>` + virtual thread loop. Each keystroke replaces the pending query without blocking. Stale results are discarded at multiple checkpoints (after search, between resume point fetches). No executor queue, no locks.

### Principles

- **Never block waiting for a lock.** Use try-lock patterns. If a lock cannot be acquired, queue the request locally and retry after 300–600ms.
- **Discard superseded requests.** Idempotent requests (e.g., search for "S" superseded by "Sea") should be dropped, not queued. Only the latest request matters.
- **Pre-fetch data on background threads.** Resume points, watch state, and other per-item data must be fetched in the background task, not during FX-thread card rendering.
- **Cancel in-flight tasks on view leave.** All views with async tasks register `onLeaveCallbacks` in `MainController` to cancel pending work when navigating away.
- **Load images asynchronously.** Use JavaFX `new Image(url, w, h, ratio, smooth, backgroundLoading=true)` for thumbnails. Synchronous image loading from disk blocks the FX thread and causes visible lag when rendering multiple cards.

## Styling

- Single CSS file (`src/main/resources/styles.css`)
- Dark theme with accent color `#e94560` (red-pink)
- Background: `#16213e` (dark navy), cards: `#1a1a2e`, header: `#0f3460`
- No external CSS frameworks

## FXML Files

All layouts in `src/main/resources/fxml/`:

| File | Controller |
|---|---|
| `main.fxml` | `MainController` |
| `search-view.fxml` | `SearchView` |
| `catalog-view.fxml` | `CatalogView` |
| `upload-view.fxml` | `UploadView` |
| `watch-history-view.fxml` | `WatchHistoryView` |
| `player-view.fxml` | `PlayerView` |
| `reports-view.fxml` | `ReportsView` |
| `benchmark-view.fxml` | `BenchmarkView` |

## Mockups

See [mockups.html](mockups.html) for the interactive HTML prototype (open in any browser).
