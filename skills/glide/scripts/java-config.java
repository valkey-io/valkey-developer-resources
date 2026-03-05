// Java GLIDE Configuration Template
// Optimized for production web applications

import glide.api.GlideClient;
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.GlideClusterClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.configuration.BackoffStrategy;
import glide.api.models.configuration.ReadFrom;

import java.util.concurrent.ExecutionException;

public class GlideConfig {
    
    // Standalone Client Configuration
    public static GlideClientConfiguration standaloneConfig() {
        return GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host("localhost")
                .port(6379)
                .build())
            
            // Request timeout (500ms recommended for web apps)
            .requestTimeout(500)
            
            // Connection retry strategy
            .reconnectStrategy(BackoffStrategy.builder()
                .numberOfRetries(10)
                .factor(500)        // Base delay in ms
                .exponentBase(2)    // Exponential backoff
                .build())
            
            // Client name for debugging
            .clientName("my-app-client")
            
            // Lazy connect for serverless/Lambda
            .lazyConnect(false)  // Set to true for Lambda
            
            // High-throughput configuration
            .inflightRequestsLimit(2000)  // Default: 1000
            .build();
    }
    
    // Cluster Client Configuration
    public static GlideClusterClientConfiguration clusterConfig() {
        return GlideClusterClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host("cluster.endpoint.cache.amazonaws.com")
                .port(6379)
                .build())
            
            // Request timeout
            .requestTimeout(500)
            
            // AZ Affinity for cost optimization (read-heavy workloads)
            .readFrom(ReadFrom.AZ_AFFINITY)
            .clientAZ("us-east-1a")  // Your application's AZ
            
            // Connection retry strategy
            .reconnectStrategy(BackoffStrategy.builder()
                .numberOfRetries(10)
                .factor(500)
                .exponentBase(2)
                .build())
            
            // Client name
            .clientName("my-app-cluster-client")
            
            // High-throughput configuration
            .inflightRequestsLimit(2000)
            .build();
    }
    
    // Create clients (do this once at application startup)
    public static class Clients {
        private final GlideClient standalone;
        private final GlideClusterClient cluster;
        
        public Clients() throws ExecutionException, InterruptedException {
            this.standalone = GlideClient.createClient(standaloneConfig()).get();
            this.cluster = GlideClusterClient.createClient(clusterConfig()).get();
        }
        
        public GlideClient getStandalone() {
            return standalone;
        }
        
        public GlideClusterClient getCluster() {
            return cluster;
        }
        
        // Graceful shutdown
        public void close() {
            try {
                standalone.close();
                cluster.close();
            } catch (Exception e) {
                // Log error
            }
        }
    }
}
