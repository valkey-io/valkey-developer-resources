package com.valkey.sports.feeder

import com.valkey.sports.valkey.ValkeyConnection
import org.slf4j.LoggerFactory

fun main(args: Array<String>) {
    val log = LoggerFactory.getLogger("feeder")

    val host = System.getenv("VALKEY_HOST") ?: "localhost"
    val port = (System.getenv("VALKEY_PORT") ?: "6379").toInt()
    val numGames = (System.getenv("NUM_GAMES") ?: "8").toInt()
    val tickMs = (System.getenv("TICK_INTERVAL_MS") ?: "2000").toLong()

    log.info("Feeder config: host={}, port={}, games={}, tickMs={}", host, port, numGames, tickMs)

    val client = ValkeyConnection.create(host, port)
    log.info("Connected to Valkey")

    // Flush previous game data
    client.customCommand(arrayOf("FLUSHDB")).get()
    log.info("Flushed previous data")

    val feeder = FeederService(client, numGames, tickMs)
    feeder.initialize()
    feeder.run()

    client.close()
}
