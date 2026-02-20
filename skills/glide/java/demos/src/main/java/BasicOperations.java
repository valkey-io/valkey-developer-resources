import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.util.concurrent.ExecutionException;

public class BasicOperations {
    public static void main(String[] args) {
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .requestTimeout(10000)
            .build();

        try (GlideClient client = GlideClient.createClient(config).get()) {
            // Set and get
            client.set("hello", "world").get();
            String value = client.get("hello").get();
            System.out.println("GET hello: " + value);

            // Error handling - wrong type operation
            client.set("mykey", "string_value").get();
            try {
                client.lpop("mykey").get();
            } catch (ExecutionException e) {
                System.out.println("Expected error: " + e.getCause().getClass().getSimpleName());
            }

            System.out.println("Basic operations completed");
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
