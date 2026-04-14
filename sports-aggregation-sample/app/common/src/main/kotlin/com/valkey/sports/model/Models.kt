package com.valkey.sports.model

data class Team(
    val abbreviation: String,
    val name: String,
    val city: String,
    val conference: String,  // Eastern / Western
    val division: String,
    val wins: Int = 0,
    val losses: Int = 0,
    val otLosses: Int = 0
)

data class GameState(
    val gameId: String,
    val homeTeam: String,       // team abbreviation
    val awayTeam: String,
    val homeScore: Int = 0,
    val awayScore: Int = 0,
    val period: Int = 1,        // 1, 2, 3, OT
    val timeRemaining: String = "20:00",
    val status: String = "pregame",  // pregame, live, intermission, final
    val homeShots: Int = 0,
    val awayShots: Int = 0,
    val homePowerPlays: Int = 0,
    val awayPowerPlays: Int = 0,
    val homePenaltyMinutes: Int = 0,
    val awayPenaltyMinutes: Int = 0,
    val homeFaceoffWins: Int = 0,
    val awayFaceoffWins: Int = 0,
    val homeHits: Int = 0,
    val awayHits: Int = 0,
    // New advanced stats
    val homeCorsi: Int = 0,         // shot attempts (shots + missed + blocked)
    val awayCorsi: Int = 0,
    val homeMissedShots: Int = 0,
    val awayMissedShots: Int = 0,
    val homeBlockedShots: Int = 0,
    val awayBlockedShots: Int = 0,
    val homeSavePercentage: Double = 100.0,
    val awaySavePercentage: Double = 100.0,
    val homeZoneTime: Double = 50.0,    // % of time in offensive zone
    val awayZoneTime: Double = 50.0,
    val homeMomentum: Double = 50.0,    // composite momentum score 0-100
    val awayMomentum: Double = 50.0,
    val homeTimeOnAttack: Int = 0,      // seconds spent in offensive zone
    val awayTimeOnAttack: Int = 0,
    val viewers: Long = 0,
    val startTime: Long = System.currentTimeMillis(),
    val lastUpdate: Long = System.currentTimeMillis()
)

data class GameEvent(
    val gameId: String,
    val type: String,           // goal, shot, penalty, hit, faceoff, blocked_shot, missed_shot, period_start, period_end
    val team: String,
    val period: Int,
    val time: String,
    val description: String,
    val timestamp: Long = System.currentTimeMillis()
)

data class TrendingMatch(
    val gameId: String,
    val homeTeam: String,
    val awayTeam: String,
    val homeScore: Int,
    val awayScore: Int,
    val period: Int,
    val timeRemaining: String,
    val status: String,
    val viewers: Long,
    val trendScore: Double       // computed by aggregation
)

data class WinProbability(
    val gameId: String,
    val homeTeam: String,
    val awayTeam: String,
    val homeProbability: Double,
    val awayProbability: Double,
    val factors: Map<String, Double> = emptyMap()
)

data class BenchmarkResult(
    val queryName: String,
    val iterations: Int,
    val avgLatencyMs: Double,
    val p50LatencyMs: Double,
    val p95LatencyMs: Double,
    val p99LatencyMs: Double,
    val throughputOpsPerSec: Double
)
