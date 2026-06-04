package com.valkey.sports.feeder

import com.valkey.sports.model.GameState
import com.valkey.sports.model.GhlTeams
import com.valkey.sports.valkey.Keys
import com.valkey.sports.valkey.ValkeyConnection
import glide.api.GlideClient
import glide.api.models.commands.stream.StreamAddOptions
import org.slf4j.LoggerFactory
import kotlin.random.Random

/**
 * Manages multiple game simulators and writes state to Valkey.
 *
 * ## Valkey Features Used
 *
 * ### Data Storage
 * - **HSET** (Hash): Each game's live state is stored as a Valkey Hash at key `game:{gameId}`.
 *   Hashes provide O(1) field-level reads/writes, ideal for frequently-updated structured data
 *   like game scores and stats. ValkeySearch indexes these hashes automatically.
 *
 * - **ZADD** (Sorted Set): Active game IDs are tracked in a sorted set (`active_games`) with
 *   the viewer count as the score. This gives O(log N) ranked access to games by popularity.
 *
 * - **XADD** (Stream): Game events (goals, shots, penalties, etc.) are appended to per-game
 *   streams at key `events:{gameId}`. Streams provide an append-only log with automatic ID
 *   generation, perfect for event sourcing patterns.
 *
 * ### ValkeySearch Index
 * - **FT.CREATE**: Creates a search index on all `game:` prefixed hashes. The schema defines:
 *   - TAG fields (homeTeam, awayTeam, status) for exact-match filtering
 *   - NUMERIC SORTABLE fields (scores, shots, viewers, etc.) for range queries and sorting
 *   - TEXT field (timeRemaining) for full-text search capability
 *   This index enables the webapp to run FT.SEARCH and FT.AGGREGATE queries against live game data.
 */
class FeederService(
    private val client: GlideClient,
    private val numGames: Int = 8,
    private val tickIntervalMs: Long = 2000,
    private val seed: Long? = null
) {
    private val log = LoggerFactory.getLogger(FeederService::class.java)
    private val simulators = mutableListOf<GameSimulator>()
    private val random: Random = if (seed != null) Random(seed) else Random.Default

    fun initialize() {
        log.info("Initializing feeder with {} games", numGames)

        // Pick random matchups (deterministic if seed is set)
        val teams = GhlTeams.teams.shuffled(random).take(numGames * 2)
        for (i in 0 until numGames) {
            val home = teams[i * 2]
            val away = teams[i * 2 + 1]
            val gameId = "game-${i + 1}"
            simulators += GameSimulator(gameId, home.abbreviation, away.abbreviation, random)
        }

        // Create the search index for games
        createSearchIndex()
        createPeriodStatsIndex()

        log.info("Created {} game simulations", simulators.size)
    }

    private fun createSearchIndex() {
        try {
            val createCmd = arrayOf(
                "FT.CREATE", Keys.GAME_INDEX,
                "ON", "HASH",
                "PREFIX", "1", "game:",
                "SCHEMA",
                "homeTeam", "TAG",
                "awayTeam", "TAG",
                "homeScore", "NUMERIC", "SORTABLE",
                "awayScore", "NUMERIC", "SORTABLE",
                "period", "NUMERIC", "SORTABLE",
                "status", "TAG",
                "homeShots", "NUMERIC", "SORTABLE",
                "awayShots", "NUMERIC", "SORTABLE",
                "homePowerPlays", "NUMERIC", "SORTABLE",
                "awayPowerPlays", "NUMERIC", "SORTABLE",
                "homePenaltyMinutes", "NUMERIC", "SORTABLE",
                "awayPenaltyMinutes", "NUMERIC", "SORTABLE",
                "homeFaceoffWins", "NUMERIC", "SORTABLE",
                "awayFaceoffWins", "NUMERIC", "SORTABLE",
                "homeHits", "NUMERIC", "SORTABLE",
                "awayHits", "NUMERIC", "SORTABLE",
                "homeCorsi", "NUMERIC", "SORTABLE",
                "awayCorsi", "NUMERIC", "SORTABLE",
                "homeMissedShots", "NUMERIC", "SORTABLE",
                "awayMissedShots", "NUMERIC", "SORTABLE",
                "homeBlockedShots", "NUMERIC", "SORTABLE",
                "awayBlockedShots", "NUMERIC", "SORTABLE",
                "homeSavePercentage", "NUMERIC", "SORTABLE",
                "awaySavePercentage", "NUMERIC", "SORTABLE",
                "homeZoneTime", "NUMERIC", "SORTABLE",
                "awayZoneTime", "NUMERIC", "SORTABLE",
                "homeMomentum", "NUMERIC", "SORTABLE",
                "awayMomentum", "NUMERIC", "SORTABLE",
                "homeTimeOnAttack", "NUMERIC", "SORTABLE",
                "awayTimeOnAttack", "NUMERIC", "SORTABLE",
                "viewers", "NUMERIC", "SORTABLE",
                "startTime", "NUMERIC", "SORTABLE",
                "lastUpdate", "NUMERIC", "SORTABLE",
                "timeRemaining", "TEXT"
            )
            client.customCommand(createCmd).get()
            log.info("Created search index: {}", Keys.GAME_INDEX)
        } catch (e: Exception) {
            if (e.message?.contains("Index already exists") == true ||
                e.cause?.message?.contains("Index already exists") == true) {
                log.info("Search index already exists, continuing")
            } else {
                log.warn("Error creating search index: {}", e.message)
            }
        }
    }

    private fun createPeriodStatsIndex() {
        try {
            val createCmd = arrayOf(
                "FT.CREATE", Keys.PERIOD_STATS_INDEX,
                "ON", "HASH",
                "PREFIX", "1", "pstats:",
                "SCHEMA",
                "gameId", "TAG",
                "period", "NUMERIC", "SORTABLE",
                "homeTeam", "TAG",
                "awayTeam", "TAG",
                "homeShots", "NUMERIC", "SORTABLE",
                "awayShots", "NUMERIC", "SORTABLE",
                "homeCorsi", "NUMERIC", "SORTABLE",
                "awayCorsi", "NUMERIC", "SORTABLE",
                "homeHits", "NUMERIC", "SORTABLE",
                "awayHits", "NUMERIC", "SORTABLE",
                "homeFaceoffWins", "NUMERIC", "SORTABLE",
                "awayFaceoffWins", "NUMERIC", "SORTABLE",
                "avgHomeMomentum", "NUMERIC", "SORTABLE",
                "avgHomeZoneTime", "NUMERIC", "SORTABLE",
                "status", "TAG"
            )
            client.customCommand(createCmd).get()
            log.info("Created period stats index: {}", Keys.PERIOD_STATS_INDEX)
        } catch (e: Exception) {
            if (e.message?.contains("Index already exists") == true ||
                e.cause?.message?.contains("Index already exists") == true) {
                log.info("Period stats index already exists, continuing")
            } else {
                log.warn("Error creating period stats index: {}", e.message)
            }
        }
    }

    fun run() {
        log.info("Starting feeder loop (tick every {}ms)", tickIntervalMs)

        while (simulators.any { it.state.status != "final" }) {
            for (sim in simulators) {
                val events = sim.tick()
                writeGameState(sim.state)
                writePeriodStats(sim)

                for (event in events) {
                    writeEvent(event)
                }
            }

            // PUBLISH — Notify subscribers that game state has been updated.
            client.publish(System.currentTimeMillis().toString(), Keys.GAME_UPDATES_CHANNEL).get()

            Thread.sleep(tickIntervalMs)
        }

        // Publish one final update so the webapp sees the "final" status
        client.publish("final", Keys.GAME_UPDATES_CHANNEL).get()
        log.info("All games finished")
    }

    private fun writeGameState(state: GameState) {
        val args = mutableListOf("HSET", Keys.game(state.gameId))
        args += listOf("homeTeam", state.homeTeam)
        args += listOf("awayTeam", state.awayTeam)
        args += listOf("homeScore", state.homeScore.toString())
        args += listOf("awayScore", state.awayScore.toString())
        args += listOf("period", state.period.toString())
        args += listOf("timeRemaining", state.timeRemaining)
        args += listOf("status", state.status)
        args += listOf("homeShots", state.homeShots.toString())
        args += listOf("awayShots", state.awayShots.toString())
        args += listOf("homePowerPlays", state.homePowerPlays.toString())
        args += listOf("awayPowerPlays", state.awayPowerPlays.toString())
        args += listOf("homePenaltyMinutes", state.homePenaltyMinutes.toString())
        args += listOf("awayPenaltyMinutes", state.awayPenaltyMinutes.toString())
        args += listOf("homeFaceoffWins", state.homeFaceoffWins.toString())
        args += listOf("awayFaceoffWins", state.awayFaceoffWins.toString())
        args += listOf("homeHits", state.homeHits.toString())
        args += listOf("awayHits", state.awayHits.toString())
        args += listOf("homeCorsi", state.homeCorsi.toString())
        args += listOf("awayCorsi", state.awayCorsi.toString())
        args += listOf("homeMissedShots", state.homeMissedShots.toString())
        args += listOf("awayMissedShots", state.awayMissedShots.toString())
        args += listOf("homeBlockedShots", state.homeBlockedShots.toString())
        args += listOf("awayBlockedShots", state.awayBlockedShots.toString())
        args += listOf("homeSavePercentage", "%.1f".format(state.homeSavePercentage))
        args += listOf("awaySavePercentage", "%.1f".format(state.awaySavePercentage))
        args += listOf("homeZoneTime", "%.1f".format(state.homeZoneTime))
        args += listOf("awayZoneTime", "%.1f".format(state.awayZoneTime))
        args += listOf("homeMomentum", "%.1f".format(state.homeMomentum))
        args += listOf("awayMomentum", "%.1f".format(state.awayMomentum))
        args += listOf("homeTimeOnAttack", state.homeTimeOnAttack.toString())
        args += listOf("awayTimeOnAttack", state.awayTimeOnAttack.toString())
        args += listOf("viewers", state.viewers.toString())
        args += listOf("startTime", state.startTime.toString())
        args += listOf("lastUpdate", state.lastUpdate.toString())

        client.customCommand(args.toTypedArray()).get()

        // ZADD — Track game in a sorted set ranked by viewer count.
        client.customCommand(arrayOf(
            "ZADD", Keys.ACTIVE_GAMES, state.viewers.toString(), state.gameId
        )).get()
    }

    private fun writeEvent(event: com.valkey.sports.model.GameEvent) {
        // XADD — Append a game event to a per-game Stream.
        client.customCommand(arrayOf(
            "XADD", Keys.events(event.gameId), "*",
            "type", event.type,
            "team", event.team,
            "period", event.period.toString(),
            "time", event.time,
            "description", event.description
        )).get()
    }

    private fun writePeriodStats(sim: GameSimulator) {
        if (sim.state.status == "pregame") return
        val stats = sim.getPeriodStats()
        val key = Keys.periodStats(sim.state.gameId, sim.state.period)
        val args = mutableListOf("HSET", key)
        for ((field, value) in stats) {
            args += field
            args += value
        }
        client.customCommand(args.toTypedArray()).get()
    }
}
