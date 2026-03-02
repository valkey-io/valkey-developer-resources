import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.models.configuration.ServerCredentials;
import glide.api.models.configuration.TlsAdvancedConfiguration;
import glide.api.models.configuration.AdvancedGlideClientConfiguration;

import java.util.concurrent.ExecutionException;

/**
 * Java GLIDE TLS + Authentication Test
 * 
 * Tests TLS connectivity with password authentication on port 6479.
 * 
 * Usage:
 *   export VALKEY_HOST=localhost
 *   ./gradlew run -PmainClass=TlsAuthTest
 */
public class TlsAuthTest {
    
    public static void main(String[] args) {
        System.out.println("Java GLIDE TLS + Authentication Testing\n");
        
        try {
            testTlsWithAuth();
        } catch (Exception e) {
            System.err.println("✗ TLS test error: " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    private static void testTlsWithAuth() throws ExecutionException, InterruptedException {
        System.out.println("=== Testing TLS + Authentication (Port 6479) ===");
        
        String host = System.getenv().getOrDefault("VALKEY_HOST", "localhost");
        
        // For self-signed certificates (testing only)
        // ⚠️ WARNING: useInsecureTLS disables certificate verification
        // In production, use proper CA-signed certificates
        TlsAdvancedConfiguration tlsConfig = TlsAdvancedConfiguration.builder()
            .useInsecureTLS(true)
            .build();
        
        AdvancedGlideClientConfiguration advancedConfig = AdvancedGlideClientConfiguration.builder()
            .tlsAdvancedConfiguration(tlsConfig)
            .build();
        
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(host)
                .port(6479)
                .build())
            .useTLS(true)  // Enable TLS
            .credentials(ServerCredentials.builder()
                .password("mypassword")
                .build())
            .advancedConfiguration(advancedConfig)
            .requestTimeout(5000)
            .build();
        
        try (GlideClient client = GlideClient.createClient(config).get()) {
            // Test operations
            client.set("tls_test_java", "Hello with TLS!").get();
            String value = client.get("tls_test_java").get();
            System.out.println("✓ TLS works: " + value);
            
            // Cleanup
            client.del(new String[]{"tls_test_java"}).get();
        }
        
        System.out.println("\n=== Testing Complete ===");
    }
}
