package com.example.springaivalkey;

import static com.example.springaivalkey.VectorTestUtils.floatArrayToBytes;
import static com.example.springaivalkey.VectorTestUtils.normalizeVector;
import static com.example.springaivalkey.VectorTestUtils.randomVector;
import static glide.api.models.GlideString.gs;

import com.fasterxml.jackson.databind.ObjectMapper;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.commands.servermodules.Json;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.DataType;
import glide.api.models.commands.FT.FTCreateOptions.DistanceMetric;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.VectorFieldHnsw;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import java.util.Map;

/**
 * Simulates Spring AI's ValkeyVectorStore patterns using valkey-glide directly.
 *
 * <p>Demonstrates: JSON.SET document storage, FT.CREATE index creation,
 * FT.SEARCH with KNN queries, TAG/NUMERIC filtering, and backend detection.
 */
public class SimulateValkeyVectorStore {

    private static final String INDEX_NAME = "demo-spring-ai-idx";
    private static final String PREFIX = "demo:";
    private static final int DIMENSION = 128;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        System.out.println("=== Spring AI ValkeyVectorStore Pattern Simulation ===\n");

        GlideClient client = GlideClient.createClient(
            GlideClientConfiguration.builder()
                .address(NodeAddress.builder()
                    .host("localhost")
                    .port(6379)
                    .build())
                .build()
        ).get();

        try {
            // Step 1: Health check
            System.out.println("1. Connectivity check");
            String pong = client.ping().get();
            System.out.println("   PING: " + pong);

            String info = client.info().get();
            if (info.contains("valkey_version")) {
                System.out.println("   Backend: Valkey ✓");
            }

            // Step 2: Check search module
            System.out.println("\n2. Search module check");
            GlideString[] indices = FT.list(client).get();
            System.out.println("   FT._LIST returned " + indices.length + " indices");
            System.out.println("   Search module: available ✓");

            // Step 3: Create index (like ValkeyVectorStore.afterPropertiesSet)
            System.out.println("\n3. Creating HNSW vector index");
            cleanupIndex(client);

            // NOTE: $.content is indexed as TagField here for demonstration purposes only.
            // Spring AI's real ValkeyVectorStore does NOT index content in the FT schema —
            // it only stores content in the JSON document for retrieval after KNN search.
            FieldInfo[] fields = new FieldInfo[]{
                new FieldInfo("$.content", "content", new TagField()),
                new FieldInfo("$.embedding", "embedding",
                    VectorFieldHnsw.builder(DistanceMetric.COSINE, DIMENSION).build()),
                new FieldInfo("$.category", "category", new TagField()),
                new FieldInfo("$.year", "year", new NumericField())
            };

            FT.create(client, INDEX_NAME, fields,
                FTCreateOptions.builder()
                    .dataType(DataType.JSON)
                    .prefixes(new String[]{PREFIX})
                    .build()
            ).get();
            System.out.println("   Index '" + INDEX_NAME + "' created ✓");

            // Step 4: Store documents (like ValkeyVectorStore.doAdd)
            System.out.println("\n4. Storing documents via JSON.SET");
            String[] contents = {
                "Valkey is a high-performance key-value store",
                "Spring AI provides a unified API for AI models",
                "Vector search enables semantic similarity matching",
                "HNSW algorithm provides fast approximate nearest neighbors",
                "Metadata filtering narrows search results by category"
            };
            String[] categories = {"database", "ai", "search", "algorithm", "search"};
            int[] years = {2024, 2025, 2025, 2023, 2025};

            for (int i = 0; i < contents.length; i++) {
                String key = PREFIX + "doc-" + i;
                float[] vector = normalizeVector(randomVector(DIMENSION));
                Map<String, Object> doc = Map.of(
                    "content", contents[i],
                    "embedding", vector,
                    "category", categories[i],
                    "year", years[i]
                );
                Json.set(client, key, "$", objectMapper.writeValueAsString(doc)).get();
            }
            System.out.println("   Stored " + contents.length + " documents ✓");

            // Wait for indexing
            waitForIndexing(client, contents.length);

            // Step 5: KNN search (like ValkeyVectorStore.doSimilaritySearch)
            System.out.println("\n5. KNN similarity search");
            float[] queryVector = normalizeVector(randomVector(DIMENSION));
            String query = "*=>[KNN 3 @embedding $BLOB AS vector_score]";

            FTSearchOptions options = FTSearchOptions.builder()
                .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(queryVector))))
                .build();

            Object[] result = FT.search(client, INDEX_NAME, query, options).get();
            System.out.println("   Query: *=>[KNN 3 @embedding $BLOB AS vector_score]");
            System.out.println("   Results: " + result[0] + " matches found ✓");

            // Step 6: Filtered search
            System.out.println("\n6. Filtered KNN search (TAG filter)");
            String filteredQuery = "(@category:{search})=>[KNN 3 @embedding $BLOB AS vector_score]";

            Object[] filteredResult = FT.search(client, INDEX_NAME, filteredQuery, options).get();
            System.out.println("   Filter: @category:{search}");
            System.out.println("   Results: " + filteredResult[0] + " matches ✓");

            // Step 7: Numeric range filter
            System.out.println("\n7. Filtered KNN search (NUMERIC range)");
            String numericQuery = "(@year:[2025 2025])=>[KNN 5 @embedding $BLOB AS vector_score]";

            Object[] numericResult = FT.search(client, INDEX_NAME, numericQuery, options).get();
            System.out.println("   Filter: @year:[2025 2025]");
            System.out.println("   Results: " + numericResult[0] + " matches ✓");

            // Step 8: Index info
            System.out.println("\n8. Index info (FT.INFO)");
            Object indexInfo = FT.info(client, INDEX_NAME).get();
            System.out.println("   FT.INFO returned successfully ✓");

            // Cleanup
            System.out.println("\n9. Cleanup");
            cleanupIndex(client);
            System.out.println("   Index dropped ✓");

            System.out.println("\n=== All patterns validated successfully ===");
        } finally {
            client.close();
        }
    }

    private static void waitForIndexing(GlideClient client, int expectedDocs) throws Exception {
        long deadline = System.currentTimeMillis() + 5000;
        while (System.currentTimeMillis() < deadline) {
            try {
                Object info = FT.info(client, INDEX_NAME).get();
                if (info.toString().contains("num_docs") &&
                    getNumDocs(info.toString()) >= expectedDocs) {
                    return;
                }
            } catch (Exception ignored) {
            }
            Thread.sleep(50);
        }
    }

    private static int getNumDocs(String infoStr) {
        // FT.INFO output contains "num_docs" followed by the count
        int idx = infoStr.indexOf("num_docs");
        if (idx == -1) return 0;
        String after = infoStr.substring(idx);
        // Find first number after "num_docs"
        StringBuilder num = new StringBuilder();
        boolean foundDigit = false;
        for (char c : after.toCharArray()) {
            if (Character.isDigit(c)) {
                num.append(c);
                foundDigit = true;
            } else if (foundDigit) {
                break;
            }
        }
        return num.isEmpty() ? 0 : Integer.parseInt(num.toString());
    }

    private static void cleanupIndex(GlideClient client) {
        try {
            FT.dropindex(client, INDEX_NAME).get();
        } catch (Exception ignored) {
        }
        try {
            // WARNING: KEYS is O(N) and blocks the server. Acceptable for demo cleanup
            // with few keys. In production, use SCAN with a cursor loop instead.
            Object result = client.customCommand(new String[]{"KEYS", PREFIX + "*"}).get();
            if (result instanceof Object[] keys && keys.length > 0) {
                String[] delArgs = new String[keys.length + 1];
                delArgs[0] = "DEL";
                for (int i = 0; i < keys.length; i++) {
                    delArgs[i + 1] = keys[i].toString();
                }
                client.customCommand(delArgs).get();
            }
        } catch (Exception ignored) {
        }
    }
}
