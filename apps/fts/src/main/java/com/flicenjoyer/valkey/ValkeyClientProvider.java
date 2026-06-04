package com.flicenjoyer.valkey;

import glide.api.GlideClient;
import glide.api.models.configuration.BackoffStrategy;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import java.util.concurrent.ExecutionException;

/** Creates and manages the GlideClient connection to Valkey. */
public class ValkeyClientProvider implements AutoCloseable {

  private final GlideClient client;
  private final ValkeyClient wrapped;

  public ValkeyClientProvider(String host, int port)
      throws ExecutionException, InterruptedException {
    GlideClientConfiguration config =
        GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(port).build())
            .requestTimeout(30000)
            .reconnectStrategy(
                BackoffStrategy.builder().numOfRetries(5).factor(500).exponentBase(2).build())
            .build();
    this.client = GlideClient.createClient(config).get();
    this.wrapped = new GlideValkeyClient(client);
  }

  /** Raw client for benchmarks — no wrapper overhead. */
  public GlideClient getClient() {
    return client;
  }

  /** Wrapped client for services — mockable in tests. */
  public ValkeyClient getValkeyClient() {
    return wrapped;
  }

  @Override
  public void close() throws ExecutionException {
    client.close();
  }
}
