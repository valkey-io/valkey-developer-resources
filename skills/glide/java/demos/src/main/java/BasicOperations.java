import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.exceptions.RequestException;

import java.util.concurrent.ExecutionException;

public class BasicOperations {
    public static void main(String[] args) {
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .requestTimeout(10000)
            .build();

        // Async (non-blocking) - using CompletableFuture chaining
        GlideClient.createClient(config).thenCompose(client -> {
            // Set and get (async)
            return client.set("hello", "world")
                .thenCompose(ok -> client.get("hello"))
                .thenAccept(value -> System.out.println("GET hello: " + value))
                .thenCompose(v -> client.set("mykey", "string_value"))
                .thenCompose(ok -> client.lpop("mykey"))
                .exceptionally(e -> {
                    // Direct access to GLIDE exception, no unwrapping needed
                    if (e instanceof RequestException) {
                        System.out.println("Expected error: " + e.getClass().getSimpleName());
                        System.out.println("Error message: " + e.getMessage());
                    }
                    return null;
                })
                .thenRun(() -> System.out.println("Basic operations completed"))
                .whenComplete((v, e) -> {
                    try {
                        client.close();
                    } catch (ExecutionException ex) {
                        System.err.println("Error closing client: " + ex.getMessage());
                    }
                });
        }).join(); // Only block at the very end to keep main thread alive
    }
}
