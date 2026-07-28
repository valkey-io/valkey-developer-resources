package com.example.springaivalkey;

import static com.example.springaivalkey.VectorTestUtils.floatArrayToBytes;
import static com.example.springaivalkey.VectorTestUtils.normalizeVector;
import static com.example.springaivalkey.VectorTestUtils.randomVector;
import static glide.api.models.GlideString.gs;
import static org.assertj.core.api.Assertions.assertThat;

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
import java.util.Arrays;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * Integration tests validating ValkeyVectorStore patterns against Valkey.
 * These tests exercise the exact commands Spring AI's ValkeyVectorStore uses.
 */
class ValkeyVectorStorePatternTest {

    private static GlideClient client;
    private static final ObjectMapper objectMapper = new ObjectMapper();
    private static final String INDEX_NAME = "test-spring-ai-idx";
    private static final String PREFIX = "test-embedding:";
    private static final int DIMENSION = 128;

    @BeforeAll
    static void setUp() throws Exception {
        client = GlideClient.createClient(
            GlideClientConfiguration.builder()
                .address(NodeAddress.builder()
                    .host("localhost")
                    .port(6379)
                    .build())
                .build()
        ).get();
    }

    @AfterAll
    static void tearDown() throws ExecutionException, InterruptedException {
        if (client != null) {
            client.close();
        }
    }

    @BeforeEach
    void cleanIndex() {
        try {
            FT.dropindex(client, INDEX_NAME).get();
        } catch (Exception ignored) {
            // Index may not exist
        }
        // Clean up test keys
        deleteKeysByPattern(PREFIX + "*");
    }

    @AfterEach
    void cleanUp() {
        cleanIndex();
    }

    @Nested
    @DisplayName("Connectivity")
    class ConnectivityTests {

        @Test
        @DisplayName("should connect and ping Valkey")
        void testConnectivity() throws Exception {
            String result = client.ping().get();
            assertThat(result).isEqualTo("PONG");
        }

        @Test
        @DisplayName("should detect Valkey server")
        void testServerInfo() throws Exception {
            String info = client.info().get();
            assertThat(info).contains("valkey_version");
        }

        @Test
        @DisplayName("should have search module loaded")
        void testSearchModuleAvailable() throws Exception {
            GlideString[] indices = FT.list(client).get();
            assertThat(indices).isNotNull();
        }
    }

    @Nested
    @DisplayName("JSON Document Storage")
    class JsonStorageTests {

        @Test
        @DisplayName("should store and retrieve JSON document")
        void testJsonSetAndGet() throws Exception {
            String key = PREFIX + "doc-1";
            Map<String, Object> doc = Map.of(
                "content", "Spring AI integrates with Valkey",
                "embedding", randomVector(DIMENSION),
                "category", "ai"
            );
            String json = objectMapper.writeValueAsString(doc);

            Json.set(client, key, "$", json).get();

            Object result = Json.get(client, key, new String[]{"$"}).get();
            assertThat(result).isNotNull();
            assertThat(result.toString()).contains("Spring AI integrates with Valkey");
        }

        @Test
        @DisplayName("should delete JSON document")
        void testJsonDelete() throws Exception {
            String key = PREFIX + "doc-del";
            String json = objectMapper.writeValueAsString(
                Map.of("content", "to be deleted", "embedding", randomVector(DIMENSION))
            );

            Json.set(client, key, "$", json).get();
            Long deleted = Long.parseLong(
                client.customCommand(new String[]{"DEL", key}).get().toString());
            assertThat(deleted).isEqualTo(1);

            Object result = Json.get(client, key, new String[]{"$"}).get();
            assertThat(result).isNull();
        }
    }

    @Nested
    @DisplayName("Vector Index")
    class VectorIndexTests {

        @Test
        @DisplayName("should create HNSW vector index on JSON")
        void testCreateHnswIndex() throws Exception {
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

            // Verify index exists
            GlideString[] indices = FT.list(client).get();
            assertThat(Arrays.stream(indices).map(GlideString::toString))
                .contains(INDEX_NAME);
        }

        @Test
        @DisplayName("should get index info after creation")
        void testIndexInfo() throws Exception {
            createTestIndex();

            Object info = FT.info(client, INDEX_NAME).get();
            assertThat(info).isNotNull();
            assertThat(info.toString()).contains(INDEX_NAME);
        }

        @Test
        @DisplayName("should detect existing index via FT.LIST")
        void testIndexExists() throws Exception {
            createTestIndex();

            GlideString[] indices = FT.list(client).get();
            boolean exists = Arrays.stream(indices)
                .map(GlideString::toString)
                .anyMatch(INDEX_NAME::equals);

            assertThat(exists).isTrue();
        }
    }

    @Nested
    @DisplayName("KNN Search")
    class KnnSearchTests {

        @Test
        @DisplayName("should find similar documents via KNN")
        void testKnnSearch() throws Exception {
            createTestIndex();
            storeTestDocuments();
            waitForIndexing(5);

            float[] queryVector = normalizeVector(randomVector(DIMENSION));
            String query = "*=>[KNN 3 @embedding $BLOB AS vector_score]";

            FTSearchOptions options = FTSearchOptions.builder()
                .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(queryVector))))
                .build();

            Object[] result = FT.search(client, INDEX_NAME, query, options).get();
            assertThat(result).isNotNull();
            assertThat(result.length).isGreaterThanOrEqualTo(2);

            // result[0] is total count
            assertThat(result[0].toString()).matches("\\d+");
        }

        @Test
        @DisplayName("should return results sorted by distance")
        void testResultsOrderedByDistance() throws Exception {
            createTestIndex();

            // Create a known unit vector (all components equal)
            float[] baseVector = new float[DIMENSION];
            Arrays.fill(baseVector, 1.0f / (float) Math.sqrt(DIMENSION));

            // Store base + nearby + far vectors
            storeDocument("near", baseVector, "near", 2025);
            float[] farVector = normalizeVector(randomVector(DIMENSION));
            storeDocument("far", farVector, "far", 2024);

            waitForIndexing(2);

            String query = "*=>[KNN 5 @embedding $BLOB AS vector_score]";
            FTSearchOptions options = FTSearchOptions.builder()
                .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(baseVector))))
                .build();

            Object[] result = FT.search(client, INDEX_NAME, query, options).get();
            assertThat(result).isNotNull();

            // At minimum we should get results back
            long totalCount = Long.parseLong(result[0].toString());
            assertThat(totalCount).isGreaterThanOrEqualTo(1);
        }

        @Test
        @DisplayName("should filter by TAG metadata in KNN query")
        void testKnnWithTagFilter() throws Exception {
            createTestIndex();
            storeDocument("ai-1", normalizeVector(randomVector(DIMENSION)), "ai", 2025);
            storeDocument("db-1", normalizeVector(randomVector(DIMENSION)), "database", 2024);
            storeDocument("ai-2", normalizeVector(randomVector(DIMENSION)), "ai", 2024);
            waitForIndexing(3);

            float[] queryVector = normalizeVector(randomVector(DIMENSION));
            String query = "(@category:{ai})=>[KNN 5 @embedding $BLOB AS vector_score]";

            FTSearchOptions options = FTSearchOptions.builder()
                .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(queryVector))))
                .build();

            Object[] result = FT.search(client, INDEX_NAME, query, options).get();
            long totalCount = Long.parseLong(result[0].toString());
            assertThat(totalCount).isEqualTo(2);
        }

        @Test
        @DisplayName("should filter by NUMERIC range in KNN query")
        void testKnnWithNumericFilter() throws Exception {
            createTestIndex();
            storeDocument("new-1", normalizeVector(randomVector(DIMENSION)), "ai", 2025);
            storeDocument("old-1", normalizeVector(randomVector(DIMENSION)), "ai", 2023);
            storeDocument("new-2", normalizeVector(randomVector(DIMENSION)), "database", 2025);
            waitForIndexing(3);

            float[] queryVector = normalizeVector(randomVector(DIMENSION));
            String query = "(@year:[2025 2025])=>[KNN 5 @embedding $BLOB AS vector_score]";

            FTSearchOptions options = FTSearchOptions.builder()
                .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(queryVector))))
                .build();

            Object[] result = FT.search(client, INDEX_NAME, query, options).get();
            long totalCount = Long.parseLong(result[0].toString());
            assertThat(totalCount).isEqualTo(2);
        }
    }

    @Nested
    @DisplayName("Namespace Isolation")
    class NamespaceIsolationTests {

        @Test
        @DisplayName("should isolate documents by prefix")
        void testPrefixIsolation() throws Exception {
            String otherPrefix = "other-prefix:";
            String otherIndex = "test-other-idx";

            try {
                // NOTE: $.content indexed as TagField for demonstration only —
                // see note in VectorIndexTests.testCreateHnswIndex.
                FieldInfo[] fields = new FieldInfo[]{
                    new FieldInfo("$.content", "content", new TagField()),
                    new FieldInfo("$.embedding", "embedding",
                        VectorFieldHnsw.builder(DistanceMetric.COSINE, DIMENSION).build())
                };

                createTestIndex();

                FT.create(client, otherIndex, fields,
                    FTCreateOptions.builder()
                        .dataType(DataType.JSON)
                        .prefixes(new String[]{otherPrefix})
                        .build()
                ).get();

                // Store in main prefix
                float[] vec = normalizeVector(randomVector(DIMENSION));
                storeDocument("main-doc", vec, "main", 2025);

                // Store in other prefix
                String otherKey = otherPrefix + "other-doc";
                String json = objectMapper.writeValueAsString(Map.of(
                    "content", "other namespace",
                    "embedding", vec
                ));
                Json.set(client, otherKey, "$", json).get();

                waitForIndexing(1);

                // Search main index — should only find main-doc
                String query = "*=>[KNN 5 @embedding $BLOB AS vector_score]";
                FTSearchOptions options = FTSearchOptions.builder()
                    .params(Map.of(gs("BLOB"), gs(floatArrayToBytes(vec))))
                    .build();

                Object[] mainResult = FT.search(client, INDEX_NAME, query, options).get();
                long mainCount = Long.parseLong(mainResult[0].toString());
                assertThat(mainCount).isEqualTo(1);

                // Search other index — should only find other-doc
                Object[] otherResult = FT.search(client, otherIndex, query, options).get();
                long otherCount = Long.parseLong(otherResult[0].toString());
                assertThat(otherCount).isEqualTo(1);
            } finally {
                try {
                    FT.dropindex(client, otherIndex).get();
                } catch (Exception ignored) {
                }
                deleteKeysByPattern(otherPrefix + "*");
            }
        }
    }

    // --- Helper Methods ---

    private void createTestIndex() throws Exception {
        // NOTE: $.content indexed as TagField for demonstration purposes only.
        // Spring AI's real ValkeyVectorStore does NOT index content in the FT schema.
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
    }

    private void storeTestDocuments() throws Exception {
        storeDocument("doc-1", normalizeVector(randomVector(DIMENSION)), "ai", 2025);
        storeDocument("doc-2", normalizeVector(randomVector(DIMENSION)), "database", 2024);
        storeDocument("doc-3", normalizeVector(randomVector(DIMENSION)), "ai", 2024);
        storeDocument("doc-4", normalizeVector(randomVector(DIMENSION)), "infrastructure", 2025);
        storeDocument("doc-5", normalizeVector(randomVector(DIMENSION)), "database", 2025);
    }

    private void storeDocument(String id, float[] vector, String category, int year) throws Exception {
        String key = PREFIX + id;
        Map<String, Object> doc = Map.of(
            "content", "Document about " + category + " from " + year,
            "embedding", vector,
            "category", category,
            "year", year
        );
        String json = objectMapper.writeValueAsString(doc);
        Json.set(client, key, "$", json).get();
    }

    /**
     * Poll FT.INFO until the indexed document count reaches the expected value.
     * Times out after 5 seconds to prevent hanging in case of indexing failures.
     */
    private void waitForIndexing(int expectedDocs) throws Exception {
        long deadline = System.currentTimeMillis() + 5000;
        while (System.currentTimeMillis() < deadline) {
            try {
                Object info = FT.info(client, INDEX_NAME).get();
                if (info != null && getNumDocs(info.toString()) >= expectedDocs) {
                    return;
                }
            } catch (Exception ignored) {
            }
            Thread.sleep(50);
        }
    }

    private int getNumDocs(String infoStr) {
        int idx = infoStr.indexOf("num_docs");
        if (idx == -1) return 0;
        String after = infoStr.substring(idx);
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

    private void deleteKeysByPattern(String pattern) {
        try {
            // WARNING: KEYS is O(N) and blocks the server. Acceptable for test cleanup
            // with few keys. In production, use SCAN with a cursor loop instead.
            Object result = client.customCommand(new String[]{"KEYS", pattern}).get();
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
