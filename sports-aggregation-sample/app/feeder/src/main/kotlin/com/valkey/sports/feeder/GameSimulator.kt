package com.valkey.sports.feeder

import com.valkey.sports.model.GameEvent
import com.valkey.sports.model.GameState
import com.valkey.sports.model.GhlTeams
import org.slf4j.LoggerFactory
import kotlin.random.Random

/**
 * Simulates a single GHL game, generating realistic events
 * (goals, shots, penalties, hits, faceoffs, blocked shots, missed shots)
 * as the game progresses. Tracks advanced stats including Corsi,
 * save percentage, zone time, and momentum.
 */
class GameSimulator(
    private val gameId: String,
    private val homeTeam: String,
    private val awayTeam: String,
    private val baseViewers: Long = Random.nextLong(8_000, 45_000)
) {
    private val log = LoggerFactory.getLogger(GameSimulator::class.java)

    var state = GameState(
        gameId = gameId,
        homeTeam = homeTeam,
        awayTeam = awayTeam,
        viewers = baseViewers
    )
        private set

    private var secondsElapsedInPeriod = 0
    private val periodLengthSeconds = 1200 // 20 minutes

    // Momentum tracking (rolling window)
    private var homeRecentEvents = 0
    private var awayRecentEvents = 0
    private var ticksSinceReset = 0

    // Period-start snapshots for computing per-period deltas
    private var periodStartHomeShots = 0
    private var periodStartAwayShots = 0
    private var periodStartHomeCorsi = 0
    private var periodStartAwayCorsi = 0
    private var periodStartHomeHits = 0
    private var periodStartAwayHits = 0
    private var periodStartHomeFaceoffWins = 0
    private var periodStartAwayFaceoffWins = 0
    private var periodStartHomeScore = 0
    private var periodStartAwayScore = 0
    private var periodMomentumSum = 0.0
    private var periodZoneTimeSum = 0.0
    private var periodTickCount = 0

    /** Get per-period stats (delta from period start) */
    fun getPeriodStats(): Map<String, String> {
        return mapOf(
            "gameId" to gameId,
            "period" to state.period.toString(),
            "homeTeam" to state.homeTeam,
            "awayTeam" to state.awayTeam,
            "homeGoals" to (state.homeScore - periodStartHomeScore).toString(),
            "awayGoals" to (state.awayScore - periodStartAwayScore).toString(),
            "homeScoreCum" to state.homeScore.toString(),
            "awayScoreCum" to state.awayScore.toString(),
            "homeShots" to (state.homeShots - periodStartHomeShots).toString(),
            "awayShots" to (state.awayShots - periodStartAwayShots).toString(),
            "homeCorsi" to (state.homeCorsi - periodStartHomeCorsi).toString(),
            "awayCorsi" to (state.awayCorsi - periodStartAwayCorsi).toString(),
            "homeHits" to (state.homeHits - periodStartHomeHits).toString(),
            "awayHits" to (state.awayHits - periodStartAwayHits).toString(),
            "homeFaceoffWins" to (state.homeFaceoffWins - periodStartHomeFaceoffWins).toString(),
            "awayFaceoffWins" to (state.awayFaceoffWins - periodStartAwayFaceoffWins).toString(),
            "avgHomeMomentum" to if (periodTickCount > 0) "%.1f".format(periodMomentumSum / periodTickCount) else "50.0",
            "avgHomeZoneTime" to if (periodTickCount > 0) "%.1f".format(periodZoneTimeSum / periodTickCount) else "50.0",
            "status" to state.status
        )
    }

    private fun snapshotPeriodStart() {
        periodStartHomeShots = state.homeShots
        periodStartAwayShots = state.awayShots
        periodStartHomeCorsi = state.homeCorsi
        periodStartAwayCorsi = state.awayCorsi
        periodStartHomeHits = state.homeHits
        periodStartAwayHits = state.awayHits
        periodStartHomeFaceoffWins = state.homeFaceoffWins
        periodStartAwayFaceoffWins = state.awayFaceoffWins
        periodStartHomeScore = state.homeScore
        periodStartAwayScore = state.awayScore
        periodMomentumSum = 0.0
        periodZoneTimeSum = 0.0
        periodTickCount = 0
    }

    /** Advance the game by one tick and return any events generated. */
    fun tick(): List<GameEvent> {
        if (state.status == "final") return emptyList()

        val events = mutableListOf<GameEvent>()

        if (state.status == "pregame") {
            state = state.copy(status = "live", lastUpdate = System.currentTimeMillis())
            snapshotPeriodStart()
            events += GameEvent(gameId, "period_start", "", 1, "20:00", "Period 1 starts")
            log.info("Game {} started: {} vs {}", gameId,
                GhlTeams.displayName(homeTeam), GhlTeams.displayName(awayTeam))
            return events
        }

        if (state.status == "intermission") {
            // Move to next period
            val nextPeriod = state.period + 1
            if (nextPeriod > 3 && state.homeScore != state.awayScore) {
                state = state.copy(status = "final", lastUpdate = System.currentTimeMillis())
                log.info("Game {} final: {} {} - {} {}", gameId,
                    homeTeam, state.homeScore, awayTeam, state.awayScore)
                return events
            }
            secondsElapsedInPeriod = 0
            val periodLabel = if (nextPeriod > 3) "OT" else "Period $nextPeriod"
            state = state.copy(
                period = nextPeriod,
                status = "live",
                timeRemaining = if (nextPeriod > 3) "5:00" else "20:00",
                lastUpdate = System.currentTimeMillis()
            )
            snapshotPeriodStart()
            events += GameEvent(gameId, "period_start", "", nextPeriod, state.timeRemaining, "$periodLabel starts")
            return events
        }

        // Advance clock (each tick = ~15 game seconds)
        secondsElapsedInPeriod += 15
        val maxSeconds = if (state.period > 3) 300 else periodLengthSeconds
        val remaining = (maxSeconds - secondsElapsedInPeriod).coerceAtLeast(0)
        val minutes = remaining / 60
        val seconds = remaining % 60
        val timeStr = "%d:%02d".format(minutes, seconds)

        // Decay momentum tracking every 15 ticks (~30 seconds game time)
        ticksSinceReset++
        if (ticksSinceReset >= 15) {
            homeRecentEvents = (homeRecentEvents * 0.7).toInt()
            awayRecentEvents = (awayRecentEvents * 0.7).toInt()
            ticksSinceReset = 0
        }

        // Generate random events
        val team = if (Random.nextBoolean()) homeTeam else awayTeam
        val isHome = team == homeTeam

        // Zone time simulation (slight random drift)
        val zoneShift = Random.nextDouble(-2.0, 2.0)
        var homeZone = (state.homeZoneTime + zoneShift).coerceIn(25.0, 75.0)
        var awayZone = 100.0 - homeZone

        // Time on attack accumulation
        val homeAttackDelta = if (homeZone > 50) (15 * (homeZone - 50) / 50).toInt() else 0
        val awayAttackDelta = if (awayZone > 50) (15 * (awayZone - 50) / 50).toInt() else 0

        // Shot on goal (~40% chance per tick)
        if (Random.nextDouble() < 0.40) {
            state = if (isHome) state.copy(homeShots = state.homeShots + 1, homeCorsi = state.homeCorsi + 1)
            else state.copy(awayShots = state.awayShots + 1, awayCorsi = state.awayCorsi + 1)
            if (isHome) homeRecentEvents++ else awayRecentEvents++
            events += GameEvent(gameId, "shot", team, state.period, timeStr, "${GhlTeams.displayName(team)} shot on goal")

            // Goal (~8% of shots)
            if (Random.nextDouble() < 0.08) {
                state = if (isHome) state.copy(homeScore = state.homeScore + 1)
                else state.copy(awayScore = state.awayScore + 1)
                if (isHome) homeRecentEvents += 5 else awayRecentEvents += 5
                // Boost zone time for scoring team
                if (isHome) { homeZone = (homeZone + 3.0).coerceAtMost(75.0); awayZone = 100.0 - homeZone }
                else { awayZone = (awayZone + 3.0).coerceAtMost(75.0); homeZone = 100.0 - awayZone }
                events += GameEvent(gameId, "goal", team, state.period, timeStr,
                    "GOAL! ${GhlTeams.displayName(team)} scores!")
                log.info("Game {} GOAL by {} ({}-{})", gameId, team, state.homeScore, state.awayScore)
            }
        }

        // Missed shot (~20% chance)
        if (Random.nextDouble() < 0.20) {
            state = if (isHome) state.copy(homeMissedShots = state.homeMissedShots + 1, homeCorsi = state.homeCorsi + 1)
            else state.copy(awayMissedShots = state.awayMissedShots + 1, awayCorsi = state.awayCorsi + 1)
            events += GameEvent(gameId, "missed_shot", team, state.period, timeStr, "${GhlTeams.displayName(team)} shot missed")
        }

        // Blocked shot (~15% chance)
        if (Random.nextDouble() < 0.15) {
            // The blocking team gets credit, but the shooting team gets Corsi
            val shootingTeam = if (Random.nextBoolean()) homeTeam else awayTeam
            val blockingTeam = if (shootingTeam == homeTeam) awayTeam else homeTeam
            val shooterIsHome = shootingTeam == homeTeam
            state = if (shooterIsHome)
                state.copy(homeCorsi = state.homeCorsi + 1, awayBlockedShots = state.awayBlockedShots + 1)
            else
                state.copy(awayCorsi = state.awayCorsi + 1, homeBlockedShots = state.homeBlockedShots + 1)
            events += GameEvent(gameId, "blocked_shot", blockingTeam, state.period, timeStr,
                "${GhlTeams.displayName(blockingTeam)} blocks shot")
        }

        // Hit (~25% chance)
        if (Random.nextDouble() < 0.25) {
            state = if (isHome) state.copy(homeHits = state.homeHits + 1)
            else state.copy(awayHits = state.awayHits + 1)
            if (isHome) homeRecentEvents++ else awayRecentEvents++
            events += GameEvent(gameId, "hit", team, state.period, timeStr, "${GhlTeams.displayName(team)} hit")
        }

        // Faceoff (~15% chance)
        if (Random.nextDouble() < 0.15) {
            state = if (isHome) state.copy(homeFaceoffWins = state.homeFaceoffWins + 1)
            else state.copy(awayFaceoffWins = state.awayFaceoffWins + 1)
        }

        // Penalty (~3% chance)
        if (Random.nextDouble() < 0.03) {
            val pim = if (Random.nextDouble() < 0.9) 2 else 5
            state = if (isHome) state.copy(
                homePenaltyMinutes = state.homePenaltyMinutes + pim
            ) else state.copy(
                awayPenaltyMinutes = state.awayPenaltyMinutes + pim
            )
            // Give power play to the other team
            state = if (isHome) state.copy(awayPowerPlays = state.awayPowerPlays + 1)
            else state.copy(homePowerPlays = state.homePowerPlays + 1)
            events += GameEvent(gameId, "penalty", team, state.period, timeStr,
                "${GhlTeams.displayName(team)} penalty ($pim min)")
        }

        // Calculate save percentage
        val homeSavePct = if (state.awayShots > 0)
            ((state.awayShots - state.awayScore).toDouble() / state.awayShots * 100.0) else 100.0
        val awaySavePct = if (state.homeShots > 0)
            ((state.homeShots - state.homeScore).toDouble() / state.homeShots * 100.0) else 100.0

        // Calculate momentum (composite of recent events, Corsi differential, zone time)
        val totalRecent = (homeRecentEvents + awayRecentEvents).coerceAtLeast(1)
        val recentRatio = homeRecentEvents.toDouble() / totalRecent
        val totalCorsi = (state.homeCorsi + state.awayCorsi).coerceAtLeast(1)
        val corsiRatio = state.homeCorsi.toDouble() / totalCorsi
        val homeMomentum = (recentRatio * 40 + corsiRatio * 30 + homeZone / 100.0 * 30).coerceIn(10.0, 90.0)
        val awayMomentum = (100.0 - homeMomentum).coerceIn(10.0, 90.0)

        // Fluctuate viewers
        val viewerDelta = Random.nextLong(-500, 1500)
        val scoreDiff = kotlin.math.abs(state.homeScore - state.awayScore)
        val excitementBoost = if (scoreDiff <= 1 && state.period >= 3) 2000L else 0L

        state = state.copy(
            timeRemaining = timeStr,
            homeZoneTime = homeZone,
            awayZoneTime = awayZone,
            homeTimeOnAttack = state.homeTimeOnAttack + homeAttackDelta,
            awayTimeOnAttack = state.awayTimeOnAttack + awayAttackDelta,
            homeSavePercentage = homeSavePct,
            awaySavePercentage = awaySavePct,
            homeMomentum = homeMomentum,
            awayMomentum = awayMomentum,
            viewers = (state.viewers + viewerDelta + excitementBoost).coerceAtLeast(1000),
            lastUpdate = System.currentTimeMillis()
        )

        // Accumulate period averages
        periodMomentumSum += state.homeMomentum
        periodZoneTimeSum += state.homeZoneTime
        periodTickCount++

        // End of period
        if (remaining <= 0) {
            state = state.copy(status = "intermission", lastUpdate = System.currentTimeMillis())
            events += GameEvent(gameId, "period_end", "", state.period, "0:00",
                "End of period ${state.period}")

            // OT sudden death - if someone scored, game over
            if (state.period > 3 && state.homeScore != state.awayScore) {
                state = state.copy(status = "final", lastUpdate = System.currentTimeMillis())
            }
        }

        return events
    }
}
