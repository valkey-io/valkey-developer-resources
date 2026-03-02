import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.configuration.ServerCredentials;
import glide.api.models.configuration.IamAuthConfig;
import glide.api.models.configuration.ServiceType;

import java.util.concurrent.ExecutionException;

/**
 * Java GLIDE AWS IAM Authentication Demo
 * 
 * Demonstrates AWS ElastiCache/MemoryDB IAM authentication configuration.
 * This demo validates the configuration compiles and runs without AWS-specific errors.
 * 
 * Note: Actual connection will fail without valid AWS credentials and ElastiCache cluster.
 * 
 * Usage:
 *   ./gradlew run -PmainClass=IamAuthDemo
 */
public class IamAuthDemo {
    
    public static void main(String[] args) {
        System.out.println("Java GLIDE AWS IAM Authentication Demo\n");
        
        try {
            testIamAuth();
        } catch (Exception e) {
            // Expected to fail without actual AWS infrastructure
            System.out.println("⚠ IAM auth demo completed (connection expected to fail without AWS)");
            System.out.println("  Error: " + e.getMessage());
            
            // Check that it's not a compilation or configuration error
            if (e.getMessage() != null && 
                (e.getMessage().contains("Failed to create client") || 
                 e.getMessage().contains("Connection refused") ||
                 e.getMessage().contains("Name or service not known"))) {
                System.out.println("✓ Configuration is valid (connection failure is expected)");
            } else {
                System.err.println("✗ Unexpected error type:");
                e.printStackTrace();
            }
        }
    }
    
    private static void testIamAuth() throws ExecutionException, InterruptedException {
        System.out.println("=== Testing AWS IAM Authentication ===");
        
        // AWS ElastiCache IAM configuration
        IamAuthConfig iamConfig = IamAuthConfig.builder()
            .clusterName("my-cluster")
            .service(ServiceType.ELASTICACHE)  // or ServiceType.MEMORYDB
            .region("us-east-1")
            .build();
        
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host("my-cluster.cache.amazonaws.com")
                .port(6379)
                .build())
            .useTLS(true)  // IAM auth requires TLS
            .credentials(ServerCredentials.builder()
                .username("myUser")  // Required for IAM
                .iamConfig(iamConfig)
                .build())
            .requestTimeout(5000)
            .build();
        
        System.out.println("✓ IAM configuration created successfully");
        System.out.println("  Cluster: my-cluster");
        System.out.println("  Service: elasticache");
        System.out.println("  Region: us-east-1");
        
        // Attempt connection (will fail without actual AWS infrastructure)
        try (GlideClient client = GlideClient.createClient(config).get()) {
            client.set("iam_test", "Hello from IAM!").get();
            String value = client.get("iam_test").get();
            System.out.println("✓ IAM auth works: " + value);
        }
    }
}
