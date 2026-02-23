import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.exceptions.RequestException;
import glide.api.models.exceptions.TimeoutException;

import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;

public class AsyncExceptionHandling {
    public static void main(String[] args) {
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .requestTimeout(10000)
            .build();

        // Async (non-blocking) - catch specific exception and rethrow
        GlideClient.createClient(config).thenCompose(client -> {
            return client.set("mykey", "string_value")
                .thenCompose(ok -> {
                    System.out.println("Set completed, attempting lpop on string key...");
                    return client.lpop("mykey");  // Wrong type operation
                })
                .exceptionally(e -> {
                    // Exception may already be wrapped in CompletionException
                    Throwable cause = (e instanceof CompletionException && e.getCause() != null) 
                        ? e.getCause() 
                        : e;
                    
                    System.out.println("Handling exception: " + cause.getClass().getSimpleName());
                    
                    // Check for specific exception type
                    if (cause instanceof RequestException) {
                        RequestException re = (RequestException) cause;
                        System.out.println("Caught RequestException: " + re.getMessage());
                        // Rethrow to propagate up the chain
                        throw new CompletionException(re);
                    } else if (cause instanceof TimeoutException) {
                        System.out.println("Caught TimeoutException: " + cause.getMessage());
                        throw new CompletionException(cause);
                    }
                    // Unknown exception - rethrow as-is
                    System.out.println("Unknown exception, rethrowing");
                    throw new CompletionException(cause);
                })
                .whenComplete((v, e) -> {
                    try {
                        client.close();
                    } catch (ExecutionException ex) {
                        System.err.println("Error closing: " + ex.getMessage());
                    }
                    
                    // Handle the rethrown exception at the top level
                    if (e != null) {
                        System.out.println("Top-level handler caught: " + e.getClass().getSimpleName());
                        if (e.getCause() instanceof RequestException) {
                            System.out.println("Root cause: " + e.getCause().getMessage());
                        }
                    }
                });
        }).exceptionally(e -> {
            System.out.println("Outer exception handler: " + e.getClass().getSimpleName());
            return null;
        }).join();
    }
}
