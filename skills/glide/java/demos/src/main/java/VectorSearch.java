import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import glide.api.commands.servermodules.FT;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.VectorFieldFlat;
import glide.api.models.commands.FT.FTCreateOptions.DistanceMetric;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.GlideString;
import glide.api.models.exceptions.RequestException;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Map;
import java.util.concurrent.ExecutionException;

public class VectorSearch {
    public static void main(String[] args) {
        GlideClientConfiguration config = GlideClientConfiguration.builder()
            .address(NodeAddress.builder()
                .host(System.getenv("VALKEY_HOST"))
                .port(6379)
                .build())
            .requestTimeout(10000)
            .build();

        // Blocking (sync) for demo simplicity
        try (GlideClient client = GlideClient.createClient(config).get()) {
            String indexName = "vec_idx";
            
            // Delete index if exists
            try {
                FT.dropindex(client, indexName).get();
                System.out.println("Dropped existing index");
            } catch (ExecutionException e) {
                if (e.getCause() instanceof RequestException) {
                    System.out.println("No existing index to drop");
                } else {
                    throw e;
                }
            }

            // Create vector index
            FieldInfo[] schema = new FieldInfo[] {
                new FieldInfo("embedding", 
                    VectorFieldFlat.builder(DistanceMetric.COSINE, 3).build())
            };

            FT.create(client, indexName, schema).get();
            System.out.println("Created index: " + indexName);

            // Get index info
            Map<String, Object> info = FT.info(client, indexName).get();
            System.out.println("Index created");

            // Store documents with vectors
            float[] vec1 = {1.0f, 0.0f, 0.0f};
            float[] vec2 = {0.0f, 1.0f, 0.0f};
            
            // Use GlideString for binary vector data
            Map<GlideString, GlideString> doc1 = Map.of(
                GlideString.of("embedding"), GlideString.of(floatArrayToBytes(vec1)),
                GlideString.of("category"), GlideString.of("A")
            );
            client.hset(GlideString.of("doc:1"), doc1).get();
            
            Map<GlideString, GlideString> doc2 = Map.of(
                GlideString.of("embedding"), GlideString.of(floatArrayToBytes(vec2)),
                GlideString.of("category"), GlideString.of("B")
            );
            client.hset(GlideString.of("doc:2"), doc2).get();
            
            System.out.println("Stored 2 documents");

            // Search for similar vectors
            float[] queryVec = {0.9f, 0.1f, 0.0f};
            String query = "*=>[KNN 2 @embedding $vector AS score]";
            
            FTSearchOptions searchOpts = FTSearchOptions.builder()
                .params(Map.of(GlideString.of("vector"), GlideString.of(floatArrayToBytes(queryVec))))
                .build();

            Object[] results = FT.search(client, indexName, query, searchOpts).get();
            System.out.println("Search results count: " + results[0]);
            if (results.length > 1) {
                System.out.println("Search results: " + results[1]);
            }

            // Update document
            client.hset("doc:1", Map.of("category", "C")).get();
            System.out.println("Updated doc:1");

            // Cleanup
            FT.dropindex(client, indexName).get();
            client.del(new String[]{"doc:1", "doc:2"}).get();
            System.out.println("Cleanup completed");

        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private static byte[] floatArrayToBytes(float[] array) {
        ByteBuffer buffer = ByteBuffer.allocate(array.length * 4).order(ByteOrder.LITTLE_ENDIAN);
        for (float f : array) {
            buffer.putFloat(f);
        }
        return buffer.array();
    }
}
