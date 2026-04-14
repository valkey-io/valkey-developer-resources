package com.valkey.sports.webapp.controller

import com.valkey.sports.model.BenchmarkResult
import com.valkey.sports.webapp.service.GameDataService
import org.springframework.web.bind.annotation.*
/**
 * REST API controller for game data and performance benchmarking.
 *
 * ## Endpoints
 * - GET /api/games         — All games via FT.SEARCH
 * - GET /api/trending      — Trending games via FT.AGGREGATE
 * - GET /api/win-probability — Win odds from FT.SEARCH + sigmoid model
 * - GET /api/benchmark     — Runs each query N times and reports latency percentiles
 *
 * ## Benchmark
 * Measures round-trip latency (app → Valkey → app) for each query type.
 * Includes 10-iteration warmup, then reports avg, p50, p95, p99, and ops/sec.
 * This demonstrates ValkeySearch query performance under load.
 */
@RestController
@RequestMapping("/api")
class ApiController(private val gameDataService: GameDataService) {

    @GetMapping("/games")
    fun games() = gameDataService.getAllGames()

    @GetMapping("/trending")
    fun trending() = gameDataService.getTrendingMatches()

    @GetMapping("/win-probability")
    fun winProbability() = gameDataService.getWinProbabilities()

    @GetMapping("/events/{gameId}")
    fun gameEvents(@PathVariable gameId: String, @RequestParam(defaultValue = "20") count: Int) =
        gameDataService.getGameEvents(gameId, count)

    @GetMapping("/events")
    fun allEvents(@RequestParam(defaultValue = "30") count: Int) =
        gameDataService.getAllRecentEvents(count)

    @GetMapping("/excitement")
    fun excitementRanking() = gameDataService.getExcitementRanking()

    @GetMapping("/period-stats")
    fun periodStats() = gameDataService.getPerPeriodStats()

    @GetMapping("/period-stats-raw")
    fun periodStatsRaw(): Map<String, Any> {
        return try {
            val clientField = gameDataService.javaClass.getDeclaredField("client")
            clientField.isAccessible = true
            val client = clientField.get(gameDataService) as glide.api.GlideClient
            val result = client.customCommand(arrayOf(
                "FT.AGGREGATE", "idx:period-stats", "@period:[1 +inf]",
                "LOAD", "7", "@period", "@homeShots", "@awayShots", "@homeCorsi", "@awayCorsi", "@avgHomeMomentum", "@avgHomeZoneTime",
                "GROUPBY", "1", "@period",
                "REDUCE", "AVG", "1", "@homeShots", "AS", "avgHomeShots",
                "REDUCE", "AVG", "1", "@awayShots", "AS", "avgAwayShots",
                "REDUCE", "COUNT", "0", "AS", "gameCount",
                "SORTBY", "2", "@period", "ASC"
            )).get()
            val arr = result as? Array<*>
            mapOf<String, Any>(
                "type" to (result?.javaClass?.name ?: "null"),
                "size" to (arr?.size ?: -1),
                "elements" to (arr?.mapIndexed { i, el ->
                    mapOf<String, Any>(
                        "index" to i,
                        "type" to (el?.javaClass?.name ?: "null"),
                        "value" to (el?.toString() ?: "null")
                    )
                } ?: listOf<Map<String, Any>>())
            )
        } catch (e: Exception) {
            mapOf<String, Any>("error" to (e.message ?: "unknown"))
        }
    }

    @GetMapping("/period-stats/{gameId}")
    fun gamePeriodStats(@PathVariable gameId: String) = gameDataService.getGamePeriodStats(gameId)

    @GetMapping("/benchmark")
    fun benchmark(@RequestParam(defaultValue = "100") iterations: Int): List<BenchmarkResult> {
        val results = mutableListOf<BenchmarkResult>()

        results += runBenchmark("FT.SEARCH all games", iterations) {
            gameDataService.getAllGames()
        }
        results += runBenchmark("FT.SEARCH active games", iterations) {
            gameDataService.getActiveGames()
        }
        results += runBenchmark("FT.AGGREGATE trending", iterations) {
            gameDataService.getTrendingMatches()
        }
        results += runBenchmark("Win probability calc", iterations) {
            gameDataService.getWinProbabilities()
        }

        return results
    }

    private fun runBenchmark(name: String, iterations: Int, block: () -> Any): BenchmarkResult {
        val latencies = mutableListOf<Long>()

        // Warmup
        repeat(10) { block() }

        repeat(iterations) {
            val start = System.nanoTime()
            block()
            latencies += (System.nanoTime() - start) / 1_000_000 // ms
        }

        latencies.sort()
        val avg = latencies.average()
        val p50 = latencies[latencies.size / 2].toDouble()
        val p95 = latencies[(latencies.size * 0.95).toInt()].toDouble()
        val p99 = latencies[(latencies.size * 0.99).toInt()].toDouble()
        val throughput = if (avg > 0) 1000.0 / avg else 0.0

        return BenchmarkResult(name, iterations, avg, p50, p95, p99, throughput)
    }
}
