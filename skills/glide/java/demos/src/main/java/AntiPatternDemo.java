import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.exceptions.RequestException;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.CompletableFuture;

/**
 * Demonstrates Java anti-patterns and their correct alternatives.
 * Based on: https://www.ayokoding.com/en/learn/software-engineering/programming-languages/java/in-the-field/anti-patterns/
 */
public class AntiPatternDemo {

    // ============================================================================
    // ANTI-PATTERN 1: Resource Leak - Not Closing Client
    // ============================================================================
    
    public static void resourceLeakAntiPattern() {
        System.out.println("\n=== ANTI-PATTERN: Resource Leak ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try {
            GlideClient client = GlideClient.createClient(config).get();
            client.set("leak:test", "value").get();
            System.out.println("Set value (client NOT closed - RESOURCE LEAK!)");
            // PROBLEM: Client never closed, connection leaked
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    public static void resourceLeakCorrect() {
        System.out.println("\n=== CORRECT: Try-With-Resources ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            client.set("correct:test", "value").get();
            System.out.println("Set value (client auto-closed via try-with-resources)");
            // SOLUTION: try-with-resources guarantees cleanup
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    // ============================================================================
    // ANTI-PATTERN 2: Swallowing InterruptedException
    // ============================================================================
    
    public static void swallowInterruptAntiPattern() {
        System.out.println("\n=== ANTI-PATTERN: Swallowing InterruptedException ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            CompletableFuture<String> future = client.get("key");
            try {
                String value = future.get();
                System.out.println("Value: " + value);
            } catch (InterruptedException e) {
                // PROBLEM: Swallowing interruption, thread can't be stopped
                System.out.println("Interrupted (but ignoring it - ANTI-PATTERN!)");
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    public static void handleInterruptCorrect() {
        System.out.println("\n=== CORRECT: Restore Interrupt Status ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            CompletableFuture<String> future = client.get("key");
            try {
                String value = future.get();
                System.out.println("Value: " + value);
            } catch (InterruptedException e) {
                // SOLUTION: Restore interrupt status
                Thread.currentThread().interrupt();
                System.out.println("Interrupted (status restored - thread can terminate)");
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    // ============================================================================
    // ANTI-PATTERN 3: Unwrapping ExecutionException Incorrectly
    // ============================================================================
    
    public static void wrongExceptionHandling() {
        System.out.println("\n=== ANTI-PATTERN: Wrong Exception Handling ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            client.set("string:key", "value").get();
            try {
                client.lpop("string:key").get();
            } catch (RequestException e) {
                // PROBLEM: This never catches - RequestException wrapped in ExecutionException
                System.out.println("Caught RequestException (NEVER REACHED!)");
            }
        } catch (Exception e) {
            System.out.println("Caught generic exception: " + e.getClass().getSimpleName());
        }
    }

    public static void correctExceptionHandling() {
        System.out.println("\n=== CORRECT: Unwrap ExecutionException ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            client.set("string:key", "value").get();
            try {
                client.lpop("string:key").get();
            } catch (ExecutionException e) {
                // SOLUTION: Check getCause() for actual exception
                if (e.getCause() instanceof RequestException) {
                    System.out.println("Caught RequestException via getCause(): " + e.getCause().getMessage());
                }
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    // ============================================================================
    // ANTI-PATTERN 4: Primitive Obsession - Using Strings for Domain Concepts
    // ============================================================================
    
    public static void primitiveObsessionAntiPattern() {
        System.out.println("\n=== ANTI-PATTERN: Primitive Obsession ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            // PROBLEM: Using raw strings, no type safety
            String userId = "user:123";
            String sessionId = "session:456";
            
            // Easy to swap parameters - compiles but wrong!
            storeUserData(client, sessionId, userId);  // WRONG ORDER!
            
            System.out.println("Stored with primitives (no type safety)");
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    private static void storeUserData(GlideClient client, String userId, String sessionId) 
            throws ExecutionException, InterruptedException {
        client.set(userId, sessionId).get();
    }

    // Value objects for type safety
    static class UserId {
        private final String value;
        public UserId(String value) {
            if (value == null || !value.startsWith("user:")) {
                throw new IllegalArgumentException("Invalid user ID");
            }
            this.value = value;
        }
        public String getValue() { return value; }
    }

    static class SessionId {
        private final String value;
        public SessionId(String value) {
            if (value == null || !value.startsWith("session:")) {
                throw new IllegalArgumentException("Invalid session ID");
            }
            this.value = value;
        }
        public String getValue() { return value; }
    }

    public static void valueObjectsCorrect() {
        System.out.println("\n=== CORRECT: Value Objects ===");
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            // SOLUTION: Type-safe value objects
            UserId userId = new UserId("user:123");
            SessionId sessionId = new SessionId("session:456");
            
            // Compiler prevents parameter swap!
            storeUserDataTypeSafe(client, userId, sessionId);
            
            System.out.println("Stored with value objects (type-safe)");
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    private static void storeUserDataTypeSafe(GlideClient client, UserId userId, SessionId sessionId) 
            throws ExecutionException, InterruptedException {
        client.set(userId.getValue(), sessionId.getValue()).get();
    }

    // ============================================================================
    // Main - Run All Demos
    // ============================================================================
    
    public static void main(String[] args) {
        System.out.println("Java GLIDE Anti-Pattern Demonstrations");
        System.out.println("=======================================");

        // 1. Resource Management
        resourceLeakAntiPattern();
        resourceLeakCorrect();

        // 2. Concurrency
        swallowInterruptAntiPattern();
        handleInterruptCorrect();

        // 3. Exception Handling
        wrongExceptionHandling();
        correctExceptionHandling();

        // 4. Design Patterns
        primitiveObsessionAntiPattern();
        valueObjectsCorrect();

        System.out.println("\n=== All demonstrations completed ===");
    }
}
