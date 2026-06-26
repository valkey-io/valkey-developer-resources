package com.valkey.sports.webapp.service

import com.valkey.sports.model.GameEvent
import com.valkey.sports.model.GameState
import com.valkey.sports.model.TrendingMatch
import com.valkey.sports.model.WinProbability
import com.valkey.sports.valkey.Keys
import glide.api.GlideClient
import org.slf4j.LoggerFactory
import org.springframework.stereotype.Service

/**
 * Reads game data from Valkey using ValkeySearch queries and computes derived analytics.
 *
 * ## Valkey Features Used (Read Path)
 *
 * ### FT.SEARCH — Filtered Document Retrieval
 * ### FT.AGGREGATE — Server-Side Aggregation (ValkeySearch 1.2)
 * ### XREVRANGE — Stream reading for event history
 */
@Service
class GameDataService(private val client: GlideClient) {

    private val log = LoggerFactory.getLogger(GameDataService::class.java)

    fun getActiveGames(): List<GameState> {
        return try {
            val result = client.customCommand(arrayOf(
                "FT.SEARCH", Keys.GAME_INDEX, "@status:{live|pregame|intermission}",
                "LIMIT", "0", "50"
            )).get()
            parseSearchResults(result)
        } catch (e: Exception) {
            log.error("Error fetching active games: {}", e.message)
            emptyList()
        }
    }

    fun getAllGames(): List<GameState> {
        return try {
            val result = client.customCommand(arrayOf(
                "FT.SEARCH", Keys.GAME_INDEX, "@startTime:[0 +inf]",
                "LIMIT", "0", "50"
            )).get()
            parseSearchResults(result)
        } catch (e: Exception) {
            log.error("Error fetching all games: {}", e.message)
            emptyList()
        }
    }

    fun getTrendingMatches(): List<TrendingMatch> {
        return try {
            val result = client.customCommand(arrayOf(
                "FT.AGGREGATE", Keys.GAME_INDEX, "@status:{live}",
                "LOAD", "10", "@homeTeam", "@awayTeam", "@homeScore", "@awayScore",
                "@period", "@timeRemaining", "@status", "@viewers", "@homeShots", "@awayShots",
                "APPLY", "@viewers", "AS", "trendScore",
                "SORTBY", "2", "@trendScore", "DESC",
                "LIMIT", "0", "10"
            )).get()
            parseAggregateForTrending(result)
        } catch (e: Exception) {
            log.error("Error fetching trending matches: {}", e.message)
            emptyList()
        }
    }

    fun getWinProbabilities(): List<WinProbability> {
        return try {
            val games = getAllGames().filter { it.status != "pregame" }
            games.map { game -> calculateWinProbability(game) }
        } catch (e: Exception) {
            log.error("Error calculating win probabilities: {}", e.message)
            emptyList()
        }
    }

    /**
     * Excitement ranking using FT.AGGREGATE with a computed formula.
     * Demonstrates APPLY with arithmetic expressions computed server-side.
     *
     * Formula: closeness_score + shot_volume + viewer_factor
     *   - closeness = 10 - abs(homeScore - awayScore) * 3
     *   - shot_volume = (homeShots + awayShots) / 5
     *   - viewer_factor = viewers / 10000
     */
    fun getExcitementRanking(): List<Map<String, Any>> {
        return try {
            val result = client.customCommand(arrayOf(
                "FT.AGGREGATE", Keys.GAME_INDEX, "@status:{live|intermission}",
                "LOAD", "8", "@homeTeam", "@awayTeam", "@homeScore", "@awayScore",
                "@homeShots", "@awayShots", "@viewers", "@homeMomentum",
                "APPLY", "(10 - abs(@homeScore - @awayScore) * 3)", "AS", "closeness",
                "APPLY", "(@homeShots + @awayShots) / 5", "AS", "shotVolume",
                "APPLY", "@viewers / 10000", "AS", "viewerFactor",
                "APPLY", "(10 - abs(@homeScore - @awayScore) * 3) + (@homeShots + @awayShots) / 5 + @viewers / 10000", "AS", "excitement",
                "SORTBY", "2", "@excitement", "DESC",
                "LIMIT", "0", "8"
            )).get()
            parseAggregateToMaps(result)
        } catch (e: Exception) {
            log.error("Error fetching excitement ranking: {}", e.message)
            emptyList()
        }
    }

    /**
     * Per-period stats using FT.AGGREGATE with GROUPBY on period field.
     * Computes averages across all games for each period — used as a comparison baseline.
     */
    fun getPerPeriodStats(): List<Map<String, Any>> {
        return try {
            val result = client.customCommand(arrayOf(
                "FT.AGGREGATE", Keys.PERIOD_STATS_INDEX, "@period:[1 +inf]",
                "LOAD", "7", "@period", "@homeShots", "@awayShots", "@homeCorsi", "@awayCorsi", "@avgHomeMomentum", "@avgHomeZoneTime",
                "GROUPBY", "1", "@period",
                "REDUCE", "AVG", "1", "@homeShots", "AS", "avgHomeShots",
                "REDUCE", "AVG", "1", "@awayShots", "AS", "avgAwayShots",
                "REDUCE", "AVG", "1", "@homeCorsi", "AS", "avgHomeCorsi",
                "REDUCE", "AVG", "1", "@awayCorsi", "AS", "avgAwayCorsi",
                "REDUCE", "AVG", "1", "@avgHomeMomentum", "AS", "avgMomentum",
                "REDUCE", "AVG", "1", "@avgHomeZoneTime", "AS", "avgZoneTime",
                "REDUCE", "COUNT", "0", "AS", "gameCount",
                "SORTBY", "2", "@period", "ASC"
            )).get()
            parseAggregateToMaps(result)
        } catch (e: Exception) {
            log.error("Error fetching per-period stats: {}", e.message)
            emptyList()
        }
    }

    /** Read per-period stats for a specific game (direct hash reads) */
    fun getGamePeriodStats(gameId: String): List<Map<String, String>> {
        val periods = mutableListOf<Map<String, String>>()
        for (period in 1..3) {
            try {
                val result = client.customCommand(arrayOf(
                    "HGETALL", Keys.periodStats(gameId, period)
                )).get()
                val map = when (result) {
                    is Map<*, *> -> result.entries.associate { it.key.toString() to it.value.toString() }
                    is Array<*> -> fieldsToMap(result)
                    else -> null
                }
                if (map != null && map.isNotEmpty()) {
                    periods += map
                }
            } catch (e: Exception) {
                // Period hasn't started yet, skip
            }
        }
        return periods
    }

    @Suppress("UNCHECKED_CAST")
    private fun parseAggregateToMaps(result: Any?): List<Map<String, Any>> {
        if (result == null) return emptyList()
        val arr = result as? Array<*> ?: return emptyList()
        if (arr.isEmpty()) return emptyList()

        val maps = mutableListOf<Map<String, Any>>()

        // Glide 2.3.1 returns FT.AGGREGATE results as an array of maps directly
        // (no leading count element like the raw Redis protocol)
        for (element in arr) {
            if (element == null) continue
            val map: Map<String, String> = when (element) {
                is Map<*, *> -> element.entries.associate { it.key.toString() to it.value.toString() }
                is Array<*> -> parseStreamFieldArray(element)
                is Long -> continue  // skip count if present
                is Int -> continue
                else -> continue
            }
            if (map.isNotEmpty()) maps += map
        }
        return maps
    }

    /** Read recent events from a game's stream using XREVRANGE */
    fun getGameEvents(gameId: String, count: Int = 20): List<GameEvent> {
        return try {
            val result = client.customCommand(arrayOf(
                "XREVRANGE", Keys.events(gameId), "+", "-", "COUNT", count.toString()
            )).get()
            parseStreamEvents(gameId, result)
        } catch (e: Exception) {
            log.error("Error fetching events for game {}: {}", gameId, e.message)
            emptyList()
        }
    }

    /** Read recent events across all games */
    fun getAllRecentEvents(count: Int = 30): List<GameEvent> {
        return try {
            val games = getAllGames()
            val allEvents = mutableListOf<GameEvent>()
            for (game in games) {
                allEvents += getGameEvents(game.gameId, 10)
            }
            allEvents.sortedByDescending { it.timestamp }.take(count)
        } catch (e: Exception) {
            log.error("Error fetching all events: {}", e.message)
            emptyList()
        }
    }

    private fun calculateWinProbability(game: GameState): WinProbability {
        val scoreDiff = game.homeScore - game.awayScore
        val shotDiff = game.homeShots - game.awayShots
        val totalShots = (game.homeShots + game.awayShots).coerceAtLeast(1)
        val ppDiff = game.homePowerPlays - game.awayPowerPlays
        val corsiDiff = game.homeCorsi - game.awayCorsi
        val totalCorsi = (game.homeCorsi + game.awayCorsi).coerceAtLeast(1)
        val momentumDiff = game.homeMomentum - game.awayMomentum

        // Weighted factors (enhanced model with new stats)
        val scoreWeight = 0.40
        val shotWeight = 0.15
        val ppWeight = 0.08
        val homeIceWeight = 0.10
        val corsiWeight = 0.15
        val momentumWeight = 0.12

        val rawScore = (scoreDiff * scoreWeight) +
            (shotDiff.toDouble() / totalShots * shotWeight * 10) +
            (ppDiff * ppWeight) +
            homeIceWeight +
            (corsiDiff.toDouble() / totalCorsi * corsiWeight * 10) +
            (momentumDiff / 100.0 * momentumWeight * 5)

        val homeProbability = 1.0 / (1.0 + Math.exp(-rawScore))

        return WinProbability(
            gameId = game.gameId,
            homeTeam = game.homeTeam,
            awayTeam = game.awayTeam,
            homeProbability = (homeProbability * 100).let { "%.1f".format(it).toDouble() },
            awayProbability = ((1 - homeProbability) * 100).let { "%.1f".format(it).toDouble() },
            factors = mapOf(
                "scoreDiff" to scoreDiff.toDouble(),
                "shotDiff" to shotDiff.toDouble(),
                "ppDiff" to ppDiff.toDouble(),
                "corsiDiff" to corsiDiff.toDouble(),
                "momentumDiff" to momentumDiff
            )
        )
    }

    @Suppress("UNCHECKED_CAST")
    private fun parseStreamEvents(gameId: String, result: Any?): List<GameEvent> {
        if (result == null) return emptyList()
        val events = mutableListOf<GameEvent>()

        log.debug("XREVRANGE result type: {}", result.javaClass.name)

        when (result) {
            is Map<*, *> -> {
                for ((streamId, fields) in result) {
                    val fieldMap: Map<String, String> = when (fields) {
                        is Map<*, *> -> fields.entries.associate { it.key.toString() to it.value.toString() }
                        is Array<*> -> parseStreamFieldArray(fields)
                        else -> continue
                    }

                    val type = fieldMap["type"] ?: ""

                    val ts = try {
                        streamId.toString().split("-")[0].toLong()
                    } catch (e: Exception) { System.currentTimeMillis() }

                    events += GameEvent(
                        gameId = gameId,
                        type = type,
                        team = fieldMap["team"] ?: "",
                        period = fieldMap["period"]?.toIntOrNull() ?: 0,
                        time = fieldMap["time"] ?: "",
                        description = fieldMap["description"] ?: "",
                        timestamp = ts
                    )
                }
            }
            is Array<*> -> {
                for (entry in result) {
                    when (entry) {
                        is Array<*> -> {
                            if (entry.size >= 2) {
                                val streamId = entry[0]?.toString() ?: continue
                                val fields = entry[1]
                                val fieldMap = when (fields) {
                                    is Map<*, *> -> fields.entries.associate { it.key.toString() to it.value.toString() }
                                    is Array<*> -> fieldsToMap(fields)
                                    else -> continue
                                }
                                val ts = try {
                                    streamId.split("-")[0].toLong()
                                } catch (e: Exception) { System.currentTimeMillis() }

                                events += GameEvent(
                                    gameId = gameId,
                                    type = fieldMap["type"] ?: "",
                                    team = fieldMap["team"] ?: "",
                                    period = fieldMap["period"]?.toIntOrNull() ?: 0,
                                    time = fieldMap["time"] ?: "",
                                    description = fieldMap["description"] ?: "",
                                    timestamp = ts
                                )
                            }
                        }
                    }
                }
            }
        }
        return events
    }

    @Suppress("UNCHECKED_CAST")
    private fun parseSearchResults(result: Any?): List<GameState> {
        if (result == null) return emptyList()
        val arr = result as? Array<*> ?: return emptyList()
        if (arr.size < 2) return emptyList()

        val games = mutableListOf<GameState>()
        val resultsMap = arr[1] as? Map<*, *> ?: return emptyList()
        for ((key, value) in resultsMap) {
            val gameId = key.toString().removePrefix("game:")
            val fieldMap = value as? Map<*, *> ?: continue
            val stringMap = fieldMap.entries.associate { it.key.toString() to it.value.toString() }
            games += mapToGameState(gameId, stringMap)
        }
        return games
    }

    @Suppress("UNCHECKED_CAST")
    private fun parseAggregateForTrending(result: Any?): List<TrendingMatch> {
        if (result == null) return emptyList()
        val arr = result as? Array<*> ?: return emptyList()
        if (arr.isEmpty()) return emptyList()

        val matches = mutableListOf<TrendingMatch>()
        for (element in arr) {
            if (element == null) continue
            val map: Map<String, String> = when (element) {
                is Map<*, *> -> element.entries.associate { it.key.toString() to it.value.toString() }
                is Array<*> -> parseStreamFieldArray(element)
                is Long -> continue
                is Int -> continue
                else -> continue
            }
            if (map.isEmpty()) continue
            matches += TrendingMatch(
                gameId = map["__key"]?.removePrefix("game:") ?: "unknown",
                homeTeam = map["homeTeam"] ?: "",
                awayTeam = map["awayTeam"] ?: "",
                homeScore = map["homeScore"]?.toIntOrNull() ?: 0,
                awayScore = map["awayScore"]?.toIntOrNull() ?: 0,
                period = map["period"]?.toIntOrNull() ?: 0,
                timeRemaining = map["timeRemaining"] ?: "",
                status = map["status"] ?: "",
                viewers = map["viewers"]?.toLongOrNull() ?: 0,
                trendScore = map["trendScore"]?.toDoubleOrNull() ?: 0.0
            )
        }
        return matches
    }

    private fun fieldsToMap(fields: Array<*>): Map<String, String> {
        val map = mutableMapOf<String, String>()
        var k = 0
        while (k < fields.size - 1) {
            val field = fields[k]?.toString() ?: ""
            val value = fields[k + 1]?.toString() ?: ""
            map[field] = value
            k += 2
        }
        return map
    }

    /** Parse stream field arrays — handles both [[key,val],[key,val]] and [key,val,key,val] formats */
    private fun parseStreamFieldArray(fields: Array<*>): Map<String, String> {
        val map = mutableMapOf<String, String>()
        if (fields.isEmpty()) return map

        // Check if first element is itself an array (pairs format)
        val first = fields[0]
        if (first is Array<*> && first.size == 2) {
            // Format: [[key, val], [key, val], ...]
            for (pair in fields) {
                if (pair is Array<*> && pair.size >= 2) {
                    map[pair[0]?.toString() ?: ""] = pair[1]?.toString() ?: ""
                }
            }
        } else {
            // Format: [key, val, key, val, ...]
            var k = 0
            while (k < fields.size - 1) {
                map[fields[k]?.toString() ?: ""] = fields[k + 1]?.toString() ?: ""
                k += 2
            }
        }
        return map
    }

    private fun mapToGameState(gameId: String, map: Map<String, String>): GameState {
        return GameState(
            gameId = gameId,
            homeTeam = map["homeTeam"] ?: "",
            awayTeam = map["awayTeam"] ?: "",
            homeScore = map["homeScore"]?.toIntOrNull() ?: 0,
            awayScore = map["awayScore"]?.toIntOrNull() ?: 0,
            period = map["period"]?.toIntOrNull() ?: 0,
            timeRemaining = map["timeRemaining"] ?: "",
            status = map["status"] ?: "",
            homeShots = map["homeShots"]?.toIntOrNull() ?: 0,
            awayShots = map["awayShots"]?.toIntOrNull() ?: 0,
            homePowerPlays = map["homePowerPlays"]?.toIntOrNull() ?: 0,
            awayPowerPlays = map["awayPowerPlays"]?.toIntOrNull() ?: 0,
            homePenaltyMinutes = map["homePenaltyMinutes"]?.toIntOrNull() ?: 0,
            awayPenaltyMinutes = map["awayPenaltyMinutes"]?.toIntOrNull() ?: 0,
            homeFaceoffWins = map["homeFaceoffWins"]?.toIntOrNull() ?: 0,
            awayFaceoffWins = map["awayFaceoffWins"]?.toIntOrNull() ?: 0,
            homeHits = map["homeHits"]?.toIntOrNull() ?: 0,
            awayHits = map["awayHits"]?.toIntOrNull() ?: 0,
            homeCorsi = map["homeCorsi"]?.toIntOrNull() ?: 0,
            awayCorsi = map["awayCorsi"]?.toIntOrNull() ?: 0,
            homeMissedShots = map["homeMissedShots"]?.toIntOrNull() ?: 0,
            awayMissedShots = map["awayMissedShots"]?.toIntOrNull() ?: 0,
            homeBlockedShots = map["homeBlockedShots"]?.toIntOrNull() ?: 0,
            awayBlockedShots = map["awayBlockedShots"]?.toIntOrNull() ?: 0,
            homeSavePercentage = map["homeSavePercentage"]?.toDoubleOrNull() ?: 100.0,
            awaySavePercentage = map["awaySavePercentage"]?.toDoubleOrNull() ?: 100.0,
            homeZoneTime = map["homeZoneTime"]?.toDoubleOrNull() ?: 50.0,
            awayZoneTime = map["awayZoneTime"]?.toDoubleOrNull() ?: 50.0,
            homeMomentum = map["homeMomentum"]?.toDoubleOrNull() ?: 50.0,
            awayMomentum = map["awayMomentum"]?.toDoubleOrNull() ?: 50.0,
            homeTimeOnAttack = map["homeTimeOnAttack"]?.toIntOrNull() ?: 0,
            awayTimeOnAttack = map["awayTimeOnAttack"]?.toIntOrNull() ?: 0,
            viewers = map["viewers"]?.toLongOrNull() ?: 0,
            startTime = map["startTime"]?.toLongOrNull() ?: 0,
            lastUpdate = map["lastUpdate"]?.toLongOrNull() ?: 0
        )
    }
}
