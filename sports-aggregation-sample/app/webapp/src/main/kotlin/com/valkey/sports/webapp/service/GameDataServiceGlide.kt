package com.valkey.sports.webapp.service

import com.valkey.sports.model.GameState
import com.valkey.sports.model.TrendingMatch
import com.valkey.sports.model.WinProbability
import com.valkey.sports.valkey.Keys
import glide.api.GlideClient
import glide.api.commands.servermodules.FT
import glide.api.models.GlideString
import glide.api.models.commands.FT.FTAggregateOptions
import glide.api.models.commands.FT.FTAggregateOptions.*
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortOrder
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortProperty
import glide.api.models.commands.FT.FTAggregateOptions.GroupBy.Reducer
import glide.api.models.commands.FT.FTSearchOptions
import org.slf4j.LoggerFactory

/**
 * Equivalent to [GameDataService] but using the typed Valkey Glide 2.4.0 API
 * instead of raw customCommand() calls.
 *
 * This demonstrates the idiomatic way to use valkey-glide's built-in FT module support.
 * The typed API provides:
 *   - Compile-time safety (no typos in command strings)
 *   - Builder pattern for complex queries
 *   - Structured return types (Map[] instead of raw Object[])
 *
 * Compare each method here with its counterpart in [GameDataService] to see
 * the difference between raw commands and the typed API.
 */
class GameDataServiceGlide(private val client: GlideClient) {

    private val log = LoggerFactory.getLogger(GameDataServiceGlide::class.java)

    // ─────────────────────────────────────────────────────────────────────────
    // FT.SEARCH — Filtered Document Retrieval
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Fetch all games using FT.SEARCH with the typed API.
     *
     * Raw equivalent:
     *   FT.SEARCH idx:games @startTime:[0 +inf] LIMIT 0 50
     */
    fun getAllGames(): List<GameState> {
        return try {
            val result = FT.search(
                client,
                Keys.GAME_INDEX,
                "@startTime:[0 +inf]",
                FTSearchOptions.builder()
                    .limit(0, 50)
                    .build()
            ).get()
            parseSearchResults(result)
        } catch (e: Exception) {
            log.error("Error fetching all games: {}", e.message)
            emptyList()
        }
    }

    /**
     * Fetch only active (non-final) games.
     *
     * Raw equivalent:
     *   FT.SEARCH idx:games @status:{live|pregame|intermission} LIMIT 0 50
     */
    fun getActiveGames(): List<GameState> {
        return try {
            val result = FT.search(
                client,
                Keys.GAME_INDEX,
                "@status:{live|pregame|intermission}",
                FTSearchOptions.builder()
                    .limit(0, 50)
                    .build()
            ).get()
            parseSearchResults(result)
        } catch (e: Exception) {
            log.error("Error fetching active games: {}", e.message)
            emptyList()
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // FT.AGGREGATE — Server-Side Analytics
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Trending matches — sorted by viewer count (server-side).
     *
     * Raw equivalent:
     *   FT.AGGREGATE idx:games @status:{live}
     *     LOAD 10 @homeTeam @awayTeam @homeScore @awayScore @period @timeRemaining @status @viewers @homeShots @awayShots
     *     APPLY @viewers AS trendScore
     *     SORTBY 2 @trendScore DESC
     *     LIMIT 0 10
     */
    fun getTrendingMatches(): List<TrendingMatch> {
        return try {
            val options = FTAggregateOptions.builder()
                .loadFields(arrayOf(
                    "@homeTeam", "@awayTeam", "@homeScore", "@awayScore",
                    "@period", "@timeRemaining", "@status", "@viewers",
                    "@homeShots", "@awayShots"
                ))
                .addClause(Apply("@viewers", "trendScore"))
                .addClause(SortBy(arrayOf(
                    SortProperty("@trendScore", SortOrder.DESC)
                )))
                .addClause(Limit(0, 10))
                .build()

            val result = FT.aggregate(client, Keys.GAME_INDEX, "@status:{live}", options).get()
            parseAggregateForTrending(result)
        } catch (e: Exception) {
            log.error("Error fetching trending matches: {}", e.message)
            emptyList()
        }
    }

    /**
     * Excitement ranking — computed formula run entirely server-side.
     *
     * Formula: closeness + shot_volume + viewer_factor
     *   - closeness = 10 - abs(homeScore - awayScore) * 3
     *   - shot_volume = (homeShots + awayShots) / 5
     *   - viewer_factor = viewers / 10000
     *
     * Raw equivalent:
     *   FT.AGGREGATE idx:games @status:{live|intermission}
     *     LOAD 8 @homeTeam @awayTeam @homeScore @awayScore @homeShots @awayShots @viewers @homeMomentum
     *     APPLY (10 - abs(@homeScore - @awayScore) * 3) AS closeness
     *     APPLY (@homeShots + @awayShots) / 5 AS shotVolume
     *     APPLY @viewers / 10000 AS viewerFactor
     *     APPLY (10 - abs(@homeScore - @awayScore) * 3) + (@homeShots + @awayShots) / 5 + @viewers / 10000 AS excitement
     *     SORTBY 2 @excitement DESC
     *     LIMIT 0 8
     */
    fun getExcitementRanking(): List<Map<String, Any>> {
        return try {
            val options = FTAggregateOptions.builder()
                .loadFields(arrayOf(
                    "@homeTeam", "@awayTeam", "@homeScore", "@awayScore",
                    "@homeShots", "@awayShots", "@viewers", "@homeMomentum"
                ))
                .addClause(Apply("(10 - abs(@homeScore - @awayScore) * 3)", "closeness"))
                .addClause(Apply("(@homeShots + @awayShots) / 5", "shotVolume"))
                .addClause(Apply("@viewers / 10000", "viewerFactor"))
                .addClause(Apply(
                    "(10 - abs(@homeScore - @awayScore) * 3) + (@homeShots + @awayShots) / 5 + @viewers / 10000",
                    "excitement"
                ))
                .addClause(SortBy(arrayOf(
                    SortProperty("@excitement", SortOrder.DESC)
                )))
                .addClause(Limit(0, 8))
                .build()

            val result = FT.aggregate(client, Keys.GAME_INDEX, "@status:{live|intermission}", options).get()
            result.map { entry ->
                entry.entries.associate { it.key.toString() to (it.value?.toString() ?: "") as Any }
            }
        } catch (e: Exception) {
            log.error("Error fetching excitement ranking: {}", e.message)
            emptyList()
        }
    }

    /**
     * Per-period league averages — GROUPBY with multiple REDUCE AVG operations.
     *
     * Raw equivalent:
     *   FT.AGGREGATE idx:period-stats @period:[1 +inf]
     *     LOAD 7 @period @homeShots @awayShots @homeCorsi @awayCorsi @avgHomeMomentum @avgHomeZoneTime
     *     GROUPBY 1 @period
     *       REDUCE AVG 1 @homeShots AS avgHomeShots
     *       REDUCE AVG 1 @awayShots AS avgAwayShots
     *       REDUCE AVG 1 @homeCorsi AS avgHomeCorsi
     *       REDUCE AVG 1 @awayCorsi AS avgAwayCorsi
     *       REDUCE AVG 1 @avgHomeMomentum AS avgMomentum
     *       REDUCE AVG 1 @avgHomeZoneTime AS avgZoneTime
     *       REDUCE COUNT 0 AS gameCount
     *     SORTBY 2 @period ASC
     */
    fun getPerPeriodStats(): List<Map<String, Any>> {
        return try {
            val options = FTAggregateOptions.builder()
                .loadFields(arrayOf(
                    "@period", "@homeShots", "@awayShots",
                    "@homeCorsi", "@awayCorsi", "@avgHomeMomentum", "@avgHomeZoneTime"
                ))
                .addClause(GroupBy(
                    arrayOf("@period"),
                    arrayOf(
                        Reducer("AVG", arrayOf("@homeShots"), "avgHomeShots"),
                        Reducer("AVG", arrayOf("@awayShots"), "avgAwayShots"),
                        Reducer("AVG", arrayOf("@homeCorsi"), "avgHomeCorsi"),
                        Reducer("AVG", arrayOf("@awayCorsi"), "avgAwayCorsi"),
                        Reducer("AVG", arrayOf("@avgHomeMomentum"), "avgMomentum"),
                        Reducer("AVG", arrayOf("@avgHomeZoneTime"), "avgZoneTime"),
                        Reducer("COUNT", arrayOf<String>(), "gameCount")
                    )
                ))
                .addClause(SortBy(arrayOf(
                    SortProperty("@period", SortOrder.ASC)
                )))
                .build()

            val result = FT.aggregate(client, Keys.PERIOD_STATS_INDEX, "@period:[1 +inf]", options).get()
            result.map { entry ->
                entry.entries.associate { it.key.toString() to (it.value?.toString() ?: "") as Any }
            }
        } catch (e: Exception) {
            log.error("Error fetching per-period stats: {}", e.message)
            emptyList()
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Parsing helpers
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Parse FT.search results from the typed API.
     *
     * The typed API returns Object[] where:
     *   [0] = Long (document count)
     *   [1] = Map<GlideString, Map<GlideString, GlideString>> (documents)
     */
    @Suppress("UNCHECKED_CAST")
    private fun parseSearchResults(result: Array<Any?>?): List<GameState> {
        if (result == null || result.size < 2) return emptyList()
        val games = mutableListOf<GameState>()
        val resultsMap = result[1] as? Map<*, *> ?: return emptyList()
        for ((key, value) in resultsMap) {
            val gameId = key.toString().removePrefix("game:")
            val fieldMap = value as? Map<*, *> ?: continue
            val stringMap = fieldMap.entries.associate { it.key.toString() to it.value.toString() }
            games += mapToGameState(gameId, stringMap)
        }
        return games
    }

    @Suppress("UNCHECKED_CAST")
    private fun parseAggregateForTrending(result: Array<Map<GlideString, Any>>?): List<TrendingMatch> {
        if (result == null) return emptyList()
        return result.mapNotNull { entry ->
            val map = entry.entries.associate { it.key.toString() to it.value.toString() }
            if (map.isEmpty()) return@mapNotNull null
            TrendingMatch(
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
