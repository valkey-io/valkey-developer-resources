import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.ClusterBatch;
import glide.api.models.exceptions.RequestException;

import java.util.concurrent.ExecutionException;

/**
 * Demonstrates cluster operations with GlideClusterClient.
 */
public class ClusterOperations {
    public static void main(String[] args) {
        GlideClusterClientConfiguration config = GlideClusterClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(7000)
                .build())
            .requestTimeout(10000)
            .build();

        // Blocking (sync) for demo simplicity
        try (GlideClusterClient client = GlideClusterClient.createClient(config).get()) {
            System.out.println("Connected to cluster");

            // Hash tags ensure same slot: {user}:1 and {user}:2
            ClusterBatch atomicBatch = new ClusterBatch(true);
            atomicBatch.set("{user}:1", "Alice");
            atomicBatch.set("{user}:2", "Bob");
            atomicBatch.get("{user}:1");
            
            Object[] results = client.exec(atomicBatch, true).get();
            System.out.println("Atomic batch (same slot): " + java.util.Arrays.toString(results));

            // Atomic batch with different slots fails with CROSSSLOT
            ClusterBatch crossSlotBatch = new ClusterBatch(true);
            crossSlotBatch.set("key1", "value1");  // Different slot
            crossSlotBatch.set("key2", "value2");  // Different slot
            
            try {
                client.exec(crossSlotBatch, true).get();
                System.out.println("ERROR: Should have failed with CROSSSLOT");
            } catch (ExecutionException e) {
                if (e.getCause() instanceof RequestException) {
                    System.out.println("Expected CROSSSLOT error: " + e.getCause().getMessage());
                } else {
                    throw e;
                }
            }

            // Non-atomic batch can span multiple slots
            ClusterBatch pipeline = new ClusterBatch(false);
            pipeline.set("key1", "value1");
            pipeline.set("key2", "value2");
            pipeline.get("key1");
            pipeline.get("key2");
            
            results = client.exec(pipeline, true).get();
            System.out.println("Pipeline (multi-slot): " + java.util.Arrays.toString(results));

            // Cleanup using non-atomic batch for multi-slot delete
            ClusterBatch cleanupBatch = new ClusterBatch(false);
            cleanupBatch.del(new String[]{"{user}:1", "{user}:2"});
            cleanupBatch.del(new String[]{"key1"});
            cleanupBatch.del(new String[]{"key2"});
            
            results = client.exec(cleanupBatch, true).get();
            System.out.println("Cleanup batch results: " + java.util.Arrays.toString(results));
            System.out.println("Cluster operations completed");

        } catch (ExecutionException e) {
            if (e.getCause() instanceof RequestException) {
                System.err.println("Request error: " + e.getCause().getMessage());
            } else {
                System.err.println("Error: " + e.getMessage());
            }
            e.printStackTrace();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            System.err.println("Interrupted: " + e.getMessage());
        }
    }
}
