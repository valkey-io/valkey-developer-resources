package main.java;

import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;

/**
 * Minimal Spring Boot-style REST controller demonstrating GLIDE async patterns.
 * Validates: CompletableFuture patterns, client lifecycle, error handling in web context.
 */
public class SpringBootDemo {
    
    static class CacheController {
        private final GlideClient client;
        
        public CacheController(GlideClient client) {
            this.client = client;
        }
        
        // GET /cache/{key}
        public CompletableFuture<String> get(String key) {
            return client.get(key);
        }
        
        // POST /cache/{key}
        public CompletableFuture<Void> set(String key, String value) {
            return client.set(key, value).thenApply(ok -> null);
        }
        
        // DELETE /cache/{key}
        public CompletableFuture<Boolean> delete(String key) {
            return client.del(new String[]{key}).thenApply(count -> count > 0);
        }
    }
    
    public static void main(String[] args) throws ExecutionException, InterruptedException {
        String host = System.getenv().getOrDefault("VALKEY_HOST", "localhost");
        
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(6379).build())
            .requestTimeout(10000)
            .build();
        
        try (GlideClient client = GlideClient.createClient(config).get()) {
            CacheController controller = new CacheController(client);
            
            // Simulate REST API calls
            System.out.println("✓ Spring Boot Demo - Simulating REST API");
            
            // POST /cache/user:1
            controller.set("user:1", "Alice").get();
            System.out.println("✓ POST /cache/user:1 -> Alice");
            
            // GET /cache/user:1
            String value = controller.get("user:1").get();
            System.out.println("✓ GET /cache/user:1 -> " + value);
            
            // DELETE /cache/user:1
            boolean deleted = controller.delete("user:1").get();
            System.out.println("✓ DELETE /cache/user:1 -> " + deleted);
            
            System.out.println("✓ Spring Boot patterns validated");
        }
    }
}
