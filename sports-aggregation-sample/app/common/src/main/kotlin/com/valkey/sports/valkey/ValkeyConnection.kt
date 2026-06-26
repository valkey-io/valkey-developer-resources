package com.valkey.sports.valkey

import glide.api.GlideClient
import glide.api.models.configuration.GlideClientConfiguration
import glide.api.models.configuration.NodeAddress

object ValkeyConnection {

    fun create(host: String = "localhost", port: Int = 6379): GlideClient {
        val config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(port).build())
            .build()
        return GlideClient.createClient(config).get()
    }
}
