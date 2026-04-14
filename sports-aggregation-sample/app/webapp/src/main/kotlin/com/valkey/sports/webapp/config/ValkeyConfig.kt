package com.valkey.sports.webapp.config

import com.valkey.sports.valkey.Keys
import com.valkey.sports.valkey.ValkeyConnection
import glide.api.GlideClient
import glide.api.models.configuration.GlideClientConfiguration
import glide.api.models.configuration.NodeAddress
import glide.api.models.configuration.StandaloneSubscriptionConfiguration
import glide.api.models.configuration.StandaloneSubscriptionConfiguration.PubSubChannelMode
import glide.api.models.GlideString
import jakarta.annotation.PreDestroy
import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.context.annotation.Primary

@Configuration
class ValkeyConfig {

    private val log = LoggerFactory.getLogger(ValkeyConfig::class.java)

    @Value("\${valkey.host:localhost}")
    private lateinit var host: String

    @Value("\${valkey.port:6379}")
    private var port: Int = 6379

    private var client: GlideClient? = null
    private var subscriberClient: GlideClient? = null

    /** Primary client for commands (FT.SEARCH, FT.AGGREGATE, etc.) */
    @Bean
    @Primary
    fun glideClient(): GlideClient {
        val c = ValkeyConnection.create(host, port)
        this.client = c
        return c
    }

    /** Dedicated Pub/Sub subscriber client.
     *  Glide recommends a separate client for subscriptions to avoid
     *  latency interference with regular commands.
     *  Subscribes to the game:updates channel at connection time. */
    @Bean
    fun subscriberClient(): GlideClient {
        log.info("Creating Pub/Sub subscriber client for channel: {}", Keys.GAME_UPDATES_CHANNEL)
        val subConfig = StandaloneSubscriptionConfiguration.builder()
            .subscription(PubSubChannelMode.EXACT, GlideString.gs(Keys.GAME_UPDATES_CHANNEL))
            .build()
        val config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(port).build())
            .subscriptionConfiguration(subConfig)
            .build()
        val c = GlideClient.createClient(config).get()
        this.subscriberClient = c
        log.info("Pub/Sub subscriber connected")
        return c
    }

    @PreDestroy
    fun cleanup() {
        subscriberClient?.close()
        client?.close()
    }
}
