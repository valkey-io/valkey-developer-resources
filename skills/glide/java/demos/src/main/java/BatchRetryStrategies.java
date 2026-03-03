import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.ClusterBatch;
import glide.api.models.commands.batch.ClusterBatchOptions;
import glide.api.models.commands.batch.ClusterBatchRetryStrategy;

public class BatchRetryStrategies {
    public static void main(String[] args) {
        String host = System.getenv("VALKEY_HOST");
        if (host == null) host = "localhost";

        GlideClusterClientConfiguration config = GlideClusterClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(7000).build())
            .address(NodeAddress.builder().host(host).port(7001).build())
            .address(NodeAddress.builder().host(host).port(7002).build())
            .requestTimeout(10000)
            .build();

        try (GlideClusterClient client = GlideClusterClient.createClient(config).get()) {
            System.out.println("=== Batch Operation Retry Strategies ===\n");

            // Scenario 1: retryServerError - Cluster resharding/server load
            System.out.println("1. RETRY SERVER ERRORS (cluster resharding, server under load)");
            System.out.println("   Use when: Transient server errors, TRYAGAIN responses");
            System.out.println("   Trade-off: May reorder commands within batch\n");

            ClusterBatch batch1 = new ClusterBatch(false);
            batch1.set("{user:1}:name", "Alice");
            batch1.set("{user:1}:email", "alice@example.com");
            batch1.get("{user:1}:name");

            ClusterBatchOptions options1 = ClusterBatchOptions.builder()
                .retryStrategy(ClusterBatchRetryStrategy.builder()
                    .retryServerError(true)
                    .retryConnectionError(false)
                    .build())
                .build();

            Object[] results1 = client.exec(batch1, true, options1).get();
            System.out.println("   ✓ Results: " + java.util.Arrays.toString(results1) + "\n");

            // Scenario 2: retryConnectionError - Network instability
            System.out.println("2. RETRY CONNECTION ERRORS (network instability, failover)");
            System.out.println("   Use when: Network issues, cluster node failover");
            System.out.println("   Trade-off: May duplicate entire batch\n");

            ClusterBatch batch2 = new ClusterBatch(false);
            batch2.set("{user:2}:name", "Bob");
            batch2.set("{user:2}:email", "bob@example.com");
            batch2.get("{user:2}:name");

            ClusterBatchOptions options2 = ClusterBatchOptions.builder()
                .retryStrategy(ClusterBatchRetryStrategy.builder()
                    .retryServerError(false)
                    .retryConnectionError(true)
                    .build())
                .build();

            Object[] results2 = client.exec(batch2, true, options2).get();
            System.out.println("   ✓ Results: " + java.util.Arrays.toString(results2) + "\n");

            // Scenario 3: Both retries - Maximum resilience
            System.out.println("3. RETRY BOTH (maximum resilience)");
            System.out.println("   Use when: High availability required, idempotent operations");
            System.out.println("   Trade-off: Possible reordering + duplication\n");

            ClusterBatch batch3 = new ClusterBatch(false);
            batch3.set("{user:3}:name", "Charlie");
            batch3.set("{user:3}:email", "charlie@example.com");
            batch3.get("{user:3}:name");

            ClusterBatchOptions options3 = ClusterBatchOptions.builder()
                .retryStrategy(ClusterBatchRetryStrategy.builder()
                    .retryServerError(true)
                    .retryConnectionError(true)
                    .build())
                .build();

            Object[] results3 = client.exec(batch3, true, options3).get();
            System.out.println("   ✓ Results: " + java.util.Arrays.toString(results3) + "\n");

            // Scenario 4: No retries - Strict latency requirements
            System.out.println("4. NO RETRIES (strict latency, non-idempotent)");
            System.out.println("   Use when: SLA-bound operations, already have app-level retry");
            System.out.println("   Trade-off: Fail fast on any error\n");

            ClusterBatch batch4 = new ClusterBatch(false);
            batch4.set("{user:4}:name", "Diana");
            batch4.set("{user:4}:email", "diana@example.com");
            batch4.get("{user:4}:name");

            ClusterBatchOptions options4 = ClusterBatchOptions.builder()
                .retryStrategy(ClusterBatchRetryStrategy.builder()
                    .retryServerError(false)
                    .retryConnectionError(false)
                    .build())
                .build();

            Object[] results4 = client.exec(batch4, true, options4).get();
            System.out.println("   ✓ Results: " + java.util.Arrays.toString(results4) + "\n");

            System.out.println("=== Summary ===");
            System.out.println("✓ retryServerError: Cluster resharding, server load");
            System.out.println("✓ retryConnectionError: Network issues, failover");
            System.out.println("✓ Both: Maximum resilience (idempotent ops)");
            System.out.println("✓ Neither: Strict latency, non-idempotent, app-level retry");

        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
