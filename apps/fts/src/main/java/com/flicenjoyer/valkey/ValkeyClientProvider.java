package com.flicenjoyer.valkey;

import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import java.util.concurrent.ExecutionException;

/** Creates and manages the GlideClient connection to Valkey. */
public class ValkeyClientProvider implements AutoCloseable {

  private final GlideClient client;

  public ValkeyClientProvider(String host, int port)
      throws ExecutionException, InterruptedException {
    GlideClientConfiguration config =
        GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(port).build())
            .requestTimeout(5000)
            .build();
    this.client = GlideClient.createClient(config).get();
  }

  public GlideClient getClient() {
    return client;
  }

  @Override
  public void close() throws ExecutionException {
    client.close();
  }
}
