# Stats & Calculation Methods

A breakdown of every stat displayed in the dashboard, grouped by where and how it's computed.

---

## 1. Computed Server-Side in Valkey (FT.AGGREGATE)

These run entirely inside Valkey — no data transferred to the app until the final result.

| Stat | Query | What it does |
|---|---|---|
| **Trending Matches** | `FT.AGGREGATE idx:games @status:{live}` with `APPLY @viewers AS trendScore`, `SORTBY @trendScore DESC` | Ranks live games by viewer count |
| **Excitement Ranking** | `FT.AGGREGATE idx:games @status:{live\|intermission}` with `APPLY (10 - abs(@homeScore - @awayScore) * 3) + (@homeShots + @awayShots) / 5 + @viewers / 10000 AS excitement`, `SORTBY @excitement DESC` | Composite score combining game closeness, shot volume, and audience size — all arithmetic done server-side |
| **Per-Period League Averages** | `FT.AGGREGATE idx:period-stats @period:[1 +inf]` with `GROUPBY @period`, `REDUCE AVG @homeShots`, `REDUCE AVG @awayShots`, `REDUCE AVG @homeCorsi`, `REDUCE AVG @awayCorsi`, `REDUCE AVG @avgHomeMomentum`, `REDUCE AVG @avgHomeZoneTime`, `REDUCE COUNT` | Groups all period-stat records by period number and computes averages across all games — used as a comparison baseline in the per-period breakdown |

---

## 2. Queried from Valkey, Computed App-Side (FT.SEARCH + Kotlin)

Data retrieved via `FT.SEARCH`, then the webapp applies a formula.

| Stat | Source | Calculation |
|---|---|---|
| **Win Probability** | `FT.SEARCH idx:games` returns full game state | Sigmoid model: `1 / (1 + e^(-rawScore))` where rawScore = score diff × 40% + shot diff × 15% + Corsi diff × 15% + momentum diff × 12% + home ice × 10% + PP diff × 8% |

---

## 3. Stored Per-Period in Valkey (HSET on `pstats:{gameId}:{period}`)

The feeder computes per-period deltas and writes them to Valkey hashes every tick. Indexed by ValkeySearch for aggregate queries.

| Stat | How it's computed |
|---|---|
| **Period SOG** | `currentHomeShots - periodStartHomeShots` (delta since period began) |
| **Period Corsi** | `currentHomeCorsi - periodStartHomeCorsi` |
| **Period Hits** | `currentHomeHits - periodStartHomeHits` |
| **Period Faceoff Wins** | `currentHomeFaceoffWins - periodStartHomeFaceoffWins` |
| **Avg Momentum (period)** | Running average of `homeMomentum` across all ticks in the current period |
| **Avg Zone Time (period)** | Running average of `homeZoneTime` across all ticks in the current period |

---

## 4. Computed in the Feeder, Written as Cumulative Values (HSET on `game:{gameId}`)

The game simulator generates these each tick and writes them to the game hash. ValkeySearch auto-indexes them for FT.SEARCH and FT.AGGREGATE.

| Stat | How it's generated |
|---|---|
| **Shots on Goal** | ~40% chance per tick, per team |
| **Corsi (shot attempts)** | Shots on goal + missed shots + blocked shots (all counted per tick) |
| **Missed Shots** | ~20% chance per tick |
| **Blocked Shots** | ~15% chance per tick (credited to blocking team, Corsi credited to shooting team) |
| **Hits** | ~25% chance per tick |
| **Faceoff Wins** | ~15% chance per tick |
| **Penalties / PIM** | ~3% chance per tick (2 or 5 minutes) |
| **Power Plays** | Awarded to opposing team on each penalty |
| **Zone Time %** | Random drift ±2% per tick, boosted +3% toward scoring team on goals. Clamped 25–75% |
| **Time on Attack** | Accumulated seconds proportional to zone time above 50% each tick |
| **Viewers** | Base (random 8K–45K) + random delta (-500 to +1500) + excitement boost (+2000 if close game in 3rd period) |
| **Save %** | `(opponentShots - opponentGoals) / opponentShots × 100` |
| **Momentum** | Composite: `recentEventRatio × 40% + corsiRatio × 30% + (zoneTime / 100) × 30%`. Recent events decay by 0.7× every 15 ticks. Clamped 10–90% |

---

## 5. Stored in Valkey Streams (XADD on `events:{gameId}`)

Append-only event log. Each entry has: `type`, `team`, `period`, `time`, `description`.

| Event Type | When it's written |
|---|---|
| `shot` | Each shot on goal |
| `goal` | Each goal (also generates a `shot` event) |
| `hit` | Each hit |
| `penalty` | Each penalty |
| `blocked_shot` | Each blocked shot |
| `missed_shot` | Each missed shot |
| `period_start` | Start of each period |
| `period_end` | End of each period |

Used for: shot dot backfill (reading historical shot events via `XREVRANGE` when a user selects a game mid-progress).

---

## 6. Computed Client-Side in JavaScript (from SSE history buffer)

The browser accumulates data points from SSE updates and renders charts/derived views.

| Stat/View | What it does |
|---|---|
| **Shot Differential** | `homeShots[t] - awayShots[t]` at each time point — single line chart, neutral color, zero-centered |
| **Shot Dots** | Per-tick delta (`shots[t] - shots[t-1]`) — if > 0, draw a dot at that game-elapsed timestamp. Backfilled dots (from stream history) rendered at 50% opacity |
| **Shot Running Totals** | Latest cumulative values from the game state, displayed as colored numbers on the dot strip |
| **All time-series charts** | Win prob, momentum, Corsi, zone time, viewers — raw values from SSE plotted against game-elapsed seconds (0–3600, fixed width with period dividers at 1200s and 2400s) |
| **Sparklines (sidebar)** | Last 30 win probability values rendered as inline SVG polyline per game |
| **Per-Period Breakdown (selected game)** | Read from `pstats:{gameId}:{1,2,3}` hashes via REST, displayed alongside league averages from FT.AGGREGATE |

---

## Valkey Data Structures Used

| Structure | Key Pattern | Purpose |
|---|---|---|
| **Hash** | `game:{gameId}` | Live game state (auto-indexed) |
| **Hash** | `pstats:{gameId}:{period}` | Per-period stats (auto-indexed) |
| **Sorted Set** | `active_games` | Games ranked by viewer count |
| **Stream** | `events:{gameId}` | Append-only event log |
| **Search Index** | `idx:games` | FT.SEARCH/FT.AGGREGATE on game hashes |
| **Search Index** | `idx:period-stats` | FT.AGGREGATE on period-stats hashes |
| **Pub/Sub Channel** | `game:updates` | Feeder → webapp real-time notification |
