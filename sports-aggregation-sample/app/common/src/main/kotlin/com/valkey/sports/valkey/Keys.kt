package com.valkey.sports.valkey

/**
 * Centralized Valkey key naming conventions.
 *
 * Key schema:
 *   game:{gameId}                    → Hash    — Live game state (indexed by ValkeySearch)
 *   pstats:{gameId}:{period}         → Hash    — Per-period stats for a game (indexed by ValkeySearch)
 *   active_games                     → Sorted Set — Game IDs scored by viewer count
 *   events:{gameId}                  → Stream  — Append-only log of game events
 *   team:{abbreviation}              → Hash    — Team season statistics
 *   idx:games                        → ValkeySearch Index on game: hashes
 *   idx:period-stats                 → ValkeySearch Index on pstats: hashes
 *   game:updates                     → Pub/Sub Channel
 */
object Keys {
    /** Hash key for a game's current state: game:{gameId} */
    fun game(gameId: String) = "game:$gameId"

    /** Hash key for per-period stats: pstats:{gameId}:{period} */
    fun periodStats(gameId: String, period: Int) = "pstats:$gameId:$period"

    /** Sorted set tracking all active game IDs */
    const val ACTIVE_GAMES = "active_games"

    /** Stream key for game events: events:{gameId} */
    fun events(gameId: String) = "events:$gameId"

    /** Hash key for team season stats: team:{abbreviation} */
    fun team(abbreviation: String) = "team:$abbreviation"

    /** The ValkeySearch index name for game data */
    const val GAME_INDEX = "idx:games"

    /** The ValkeySearch index name for per-period stats */
    const val PERIOD_STATS_INDEX = "idx:period-stats"

    /** Pub/Sub channel for game update notifications. */
    const val GAME_UPDATES_CHANNEL = "game:updates"
}
