package main.java;

import glide.api.GlideClient;
import glide.api.models.Batch;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.ExecutionException;

/**
 * Batch processing CLI tool demonstrating pipeline patterns.
 * Validates: try-with-resources, batch/pipeline usage, blocking patterns.
 */
public class BatchImporter {
    
    public static void main(String[] args) throws Exception {
        String host = System.getenv().getOrDefault("VALKEY_HOST", "localhost");
        
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder().host(host).port(6379).build())
            .requestTimeout(10000)
            .build();
        
        // Try-with-resources pattern from skill
        try (GlideClient client = GlideClient.createClient(config).get()) {
            System.out.println("✓ Batch Importer Demo");
            
            // Create sample data
            String[] sampleData = {
                "product:1,Widget",
                "product:2,Gadget",
                "product:3,Doohickey",
                "product:4,Thingamajig",
                "product:5,Whatchamacallit"
            };
            
            // Non-atomic batch (pipeline) pattern from skill
            Batch batch = new Batch(false);
            
            for (String line : sampleData) {
                String[] parts = line.split(",");
                batch.set(parts[0], parts[1]);
            }
            
            System.out.println("✓ Importing " + sampleData.length + " records...");
            
            // Execute batch - blocking pattern
            Object[] results = client.exec(batch, true).get();
            System.out.println("✓ Imported " + results.length + " records");
            
            // Verify imports
            System.out.println("✓ Verifying imports:");
            for (String line : sampleData) {
                String key = line.split(",")[0];
                String value = client.get(key).get();
                System.out.println("  " + key + " -> " + value);
            }
            
            // Cleanup
            Batch cleanup = new Batch(false);
            for (String line : sampleData) {
                String key = line.split(",")[0];
                cleanup.del(new String[]{key});
            }
            client.exec(cleanup, true).get();
            
            System.out.println("✓ Batch processing patterns validated");
        }
    }
}
