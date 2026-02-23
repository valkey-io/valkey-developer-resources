import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.Batch;

public class BatchPipeline {
    public static void main(String[] args) {
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .requestTimeout(10000)
            .build();

        // Blocking (sync) - using .get() on CompletableFuture
        try (GlideClient client = GlideClient.createClient(config).get()) {
            // Pipeline (non-atomic): bulk independent operations
            Batch pipeline = new Batch(false);
            pipeline.set("user:1", "Alice");
            pipeline.set("user:2", "Bob");
            pipeline.get("user:1");
            pipeline.get("user:2");
            
            // Execute pipeline (blocking)
            Object[] results = client.exec(pipeline, true).get();
            System.out.println("Pipeline results: " + java.util.Arrays.toString(results));

            // Transaction (atomic): consistent multi-key update
            Batch transaction = new Batch(true);
            transaction.set("counter", "0");
            transaction.incr("counter");
            transaction.incr("counter");
            transaction.get("counter");
            
            // Execute transaction (blocking)
            results = client.exec(transaction, true).get();
            System.out.println("Transaction results: " + java.util.Arrays.toString(results));

            System.out.println("Batch/pipeline operations completed");
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
