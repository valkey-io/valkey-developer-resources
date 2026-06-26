package com.valkey.sports.webapp.controller

import com.valkey.sports.webapp.service.GameDataService
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import glide.api.GlideClient
import jakarta.annotation.PostConstruct
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Qualifier
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Server-Sent Events (SSE) controller for real-time browser updates,
 * driven by Valkey Pub/Sub notifications.
 *
 * ## How It Works (Event-Driven, No Polling)
 *
 * ### Valkey Pub/Sub → SSE Pipeline
 * 1. The **feeder** publishes a message to the `game:updates` channel (PUBLISH)
 *    after every simulation tick (every 2 seconds).
 * 2. A dedicated **subscriber client** (configured in ValkeyConfig) receives the message.
 *    A background thread polls the subscriber for incoming Pub/Sub messages.
 * 3. On receipt, this controller queries Valkey via GameDataService
 *    (FT.SEARCH + FT.AGGREGATE) to get the latest game state.
 * 4. The results are serialized to JSON and pushed to ALL connected browsers via SSE.
 *
 * ### Client Side (app.js)
 * 1. On page load, JavaScript creates: `new EventSource('/api/sse/games')`
 * 2. Listens for 'update' events via `addEventListener('update', ...)`
 * 3. Parses the JSON payload and updates the DOM:
 *    - `updateGames()` → refreshes the scoreboard cards
 *    - `updateTrending()` → refreshes the trending matches list
 *    - `updateWinProbabilities()` → refreshes the probability bars
 * 4. EventSource auto-reconnects if the connection drops
 *
 * ### Why Pub/Sub + SSE?
 * - **Pub/Sub** makes the pipeline event-driven: updates flow instantly when data changes,
 *   no wasted queries when nothing has changed.
 * - **SSE** is simpler than WebSockets for server→client push (no bidirectional needed).
 * - Native browser support via EventSource API — no library required.
 * - Auto-reconnection built into the SSE protocol.
 */
@RestController
@RequestMapping("/api/sse")
class SseController(
    private val gameDataService: GameDataService,
    @Qualifier("subscriberClient") private val subscriberClient: GlideClient
) {

    private val log = LoggerFactory.getLogger(SseController::class.java)
    private val mapper = jacksonObjectMapper()
    private val emitters = CopyOnWriteArrayList<SseEmitter>()

    @GetMapping("/games")
    fun streamGames(): SseEmitter {
        val emitter = SseEmitter(0L) // no timeout
        emitters.add(emitter)
        emitter.onCompletion { emitters.remove(emitter) }
        emitter.onTimeout { emitters.remove(emitter) }
        emitter.onError { emitters.remove(emitter) }
        log.debug("SSE client connected, total: {}", emitters.size)
        return emitter
    }

    /** Starts a background thread that listens for Pub/Sub messages
     *  from the feeder and pushes updates to SSE clients. */
    @PostConstruct
    fun startPubSubListener() {
        Thread({
            log.info("Pub/Sub listener started, waiting for game:updates messages...")
            while (!Thread.currentThread().isInterrupted) {
                try {
                    // Block until a message arrives on the game:updates channel.
                    // getPubSubMessage() is a blocking call — it waits for the next PUBLISH.
                    val message = subscriberClient.getPubSubMessage().get()
                    if (message != null) {
                        log.debug("Received Pub/Sub notification: {}", message.message)
                        pushUpdatesToClients()
                    }
                } catch (e: Exception) {
                    if (Thread.currentThread().isInterrupted) break
                    log.error("Pub/Sub listener error: {}", e.message)
                    Thread.sleep(1000) // back off briefly on error
                }
            }
        }, "pubsub-listener").apply {
            isDaemon = true
            start()
        }
    }

    private fun pushUpdatesToClients() {
        if (emitters.isEmpty()) return

        try {
            val games = gameDataService.getAllGames()
            val trending = gameDataService.getTrendingMatches()
            val winProbs = gameDataService.getWinProbabilities()
            val excitement = gameDataService.getExcitementRanking()
            val periodAverages = gameDataService.getPerPeriodStats()

            // Get period stats for each game
            val allPeriodStats = games.associate { it.gameId to gameDataService.getGamePeriodStats(it.gameId) }

            val payload = mapper.writeValueAsString(mapOf(
                "games" to games,
                "trending" to trending,
                "winProbabilities" to winProbs,
                "excitement" to excitement,
                "periodAverages" to periodAverages,
                "periodStats" to allPeriodStats
            ))

            val deadEmitters = mutableListOf<SseEmitter>()
            for (emitter in emitters) {
                try {
                    emitter.send(SseEmitter.event().name("update").data(payload))
                } catch (e: Exception) {
                    deadEmitters.add(emitter)
                }
            }
            emitters.removeAll(deadEmitters.toSet())
        } catch (e: Exception) {
            log.error("Error pushing SSE updates: {}", e.message)
        }
    }
}
