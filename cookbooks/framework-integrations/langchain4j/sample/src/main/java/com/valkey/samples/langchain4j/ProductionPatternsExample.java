package com.valkey.samples.langchain4j;

import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import dev.langchain4j.store.embedding.EmbeddingMatch;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Cookbook 04 - Production Patterns for LangChain4j + Valkey
 *
 * Demonstrates: batch ingestion with concurrent writes, connection management,
 * error handling, index management, and shared client patterns.
 *
 * Prerequisites:
 *   docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.1
 */
public class ProductionPatternsExample {

    public static void main(String[] args) throws Exception {
        System.out.println("=== LangChain4j + Valkey: Production Patterns ===\n");

        // 1. Connect to Valkey
        // Use a longer request timeout for batch operations (default may be too short
        // when writing many vectors concurrently into an HNSW index)
        GlideClientConfiguration config = GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .requestTimeout(10000) // 10 seconds
                .build();
        GlideClient client = GlideClient.createClient(config).get();
        System.out.println("Connected to Valkey");

        EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

        // ============================================================
        // SECTION 1: Create Store with metadata
        // ============================================================
        System.out.println("\n--- Section 1: Create Store ---");

        // The store creates an HNSW index with COSINE distance on first use.
        // For custom HNSW tuning (M, EF_CONSTRUCTION), pre-create the index
        // with FT.CREATE before building the store (see cookbook 04 docs).
        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .indexName("production-index")
                .prefix("prod:")
                .dimension(384)
                .metadataKeys(List.of("category", "doc_id"))
                .build();
        System.out.println("Created ValkeyEmbeddingStore (HNSW, COSINE, 384 dims)");

        // ============================================================
        // SECTION 2: Batch ingestion
        // ============================================================
        System.out.println("\n--- Section 2: Batch Ingestion ---");

        // Generate sample documents
        List<TextSegment> allSegments = generateSampleDocs(50);
        List<Embedding> allEmbeddings = embeddingModel.embedAll(allSegments).content();

        // Ingest in batches — keeps concurrent inflight requests manageable
        int batchSize = 10;
        long startTime = System.currentTimeMillis();

        for (int i = 0; i < allSegments.size(); i += batchSize) {
            int end = Math.min(i + batchSize, allSegments.size());
            List<TextSegment> batch = allSegments.subList(i, end);
            List<Embedding> batchEmbeddings = allEmbeddings.subList(i, end);

            store.addAll(batchEmbeddings, batch);
            System.out.printf("  Ingested %d/%d documents%n", end, allSegments.size());
        }

        long elapsed = System.currentTimeMillis() - startTime;
        System.out.printf("Batch ingestion complete: %d docs in %dms (%.0f docs/sec)%n",
                allSegments.size(), elapsed, allSegments.size() * 1000.0 / elapsed);

        // ============================================================
        // SECTION 3: Concurrent ingestion with thread pool
        // ============================================================
        System.out.println("\n--- Section 3: Concurrent Ingestion ---");

        // Generate more docs
        List<TextSegment> moreSegments = generateSampleDocs(50);
        List<Embedding> moreEmbeddings = embeddingModel.embedAll(moreSegments).content();

        ExecutorService executor = Executors.newFixedThreadPool(2);
        startTime = System.currentTimeMillis();

        List<CompletableFuture<Void>> futures = new ArrayList<>();
        try {
            for (int i = 0; i < moreSegments.size(); i += batchSize) {
                int start = i;
                int end = Math.min(i + batchSize, moreSegments.size());
                futures.add(CompletableFuture.runAsync(() -> {
                    List<TextSegment> batch = moreSegments.subList(start, end);
                    List<Embedding> embs = moreEmbeddings.subList(start, end);
                    store.addAll(embs, batch);
                }, executor));
            }

            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
        } finally {
            executor.shutdown();
        }

        elapsed = System.currentTimeMillis() - startTime;
        System.out.printf("Concurrent ingestion: %d docs in %dms (%.0f docs/sec)%n",
                moreSegments.size(), elapsed, moreSegments.size() * 1000.0 / elapsed);

        // ============================================================
        // SECTION 4: Search with the index
        // ============================================================
        System.out.println("\n--- Section 4: Search Performance ---");

        Embedding queryEmbedding = embeddingModel.embed("vector search performance").content();

        // Warm up
        store.search(EmbeddingSearchRequest.builder()
                .queryEmbedding(queryEmbedding).maxResults(5).build());

        // Measure search latency
        int searchIterations = 100;
        startTime = System.currentTimeMillis();
        EmbeddingSearchResult<TextSegment> lastResult = null;

        for (int i = 0; i < searchIterations; i++) {
            lastResult = store.search(EmbeddingSearchRequest.builder()
                    .queryEmbedding(queryEmbedding)
                    .maxResults(5)
                    .minScore(0.3)
                    .build());
        }

        elapsed = System.currentTimeMillis() - startTime;
        System.out.printf("Search latency: %.2fms avg over %d queries%n",
                (double) elapsed / searchIterations, searchIterations);
        System.out.println("Top results:");
        for (EmbeddingMatch<TextSegment> match : lastResult.matches()) {
            System.out.printf("  %.3f: %s%n", match.score(),
                    match.embedded().text().substring(0, Math.min(70, match.embedded().text().length())) + "...");
        }

        // ============================================================
        // SECTION 5: Index management
        // ============================================================
        System.out.println("\n--- Section 5: Index Management ---");

        // Check index info
        Object indexInfo = client.customCommand(new String[]{"FT.INFO", "production-index"}).get();
        System.out.println("FT.INFO returned successfully (index is healthy)");

        // List all indexes
        Object indexes = client.customCommand(new String[]{"FT._LIST"}).get();
        System.out.println("Active indexes: " + indexes);

        // ============================================================
        // SECTION 6: Error handling pattern
        // ============================================================
        System.out.println("\n--- Section 6: Error Handling ---");

        // Demonstrate graceful degradation on search
        try {
            EmbeddingSearchResult<TextSegment> results = store.search(
                    EmbeddingSearchRequest.builder()
                            .queryEmbedding(queryEmbedding)
                            .maxResults(3)
                            .build()
            );
            System.out.println("Search succeeded: " + results.matches().size() + " results");
        } catch (Exception e) {
            System.out.println("Search failed gracefully: " + e.getMessage());
            // In production: return empty results, serve from cache, etc.
        }

        // ============================================================
        // SECTION 7: Shared client across multiple stores
        // ============================================================
        System.out.println("\n--- Section 7: Shared Client ---");

        ValkeyEmbeddingStore ragStore = ValkeyEmbeddingStore.builder()
                .client(client)
                .indexName("rag-store")
                .prefix("rag:")
                .dimension(384)
                .build();

        ValkeyEmbeddingStore cacheStore = ValkeyEmbeddingStore.builder()
                .client(client)
                .indexName("cache-store")
                .prefix("cache:")
                .dimension(384)
                .build();

        System.out.println("Created 2 stores sharing the same GlideClient connection");
        System.out.println("  - rag-store (prefix: rag:)");
        System.out.println("  - cache-store (prefix: cache:)");

        // ============================================================
        // Cleanup
        // ============================================================
        System.out.println("\n--- Cleanup ---");

        // Remove data first, then drop indexes, then close
        try {
            store.removeAll();
        } catch (Exception e) { /* best-effort */ }
        try {
            ragStore.close();
        } catch (Exception e) { /* best-effort */ }
        try {
            cacheStore.close();
        } catch (Exception e) { /* best-effort */ }

        try {
            client.customCommand(new String[]{"FT.DROPINDEX", "production-index"}).get();
            client.customCommand(new String[]{"FT.DROPINDEX", "rag-store"}).get();
            client.customCommand(new String[]{"FT.DROPINDEX", "cache-store"}).get();
        } catch (Exception e) { /* best-effort */ }

        // close() on the store closes the shared client — call last
        store.close();

        System.out.println("\nDone! All production patterns demonstrated.");
    }

    /**
     * Generate sample documents for ingestion testing.
     */
    private static List<TextSegment> generateSampleDocs(int count) {
        String[] topics = {"vector search", "caching", "replication", "clustering", "persistence",
                "memory management", "security", "monitoring", "performance", "indexing"};
        String[] categories = {"operations", "security", "performance", "architecture"};

        List<TextSegment> segments = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            String topic = topics[i % topics.length];
            String category = categories[i % categories.length];
            String text = String.format("Document %d about %s: This covers best practices for %s "
                    + "in production Valkey deployments including configuration and tuning.", i, topic, topic);
            segments.add(TextSegment.from(text,
                    Metadata.from(Map.of("category", category, "doc_id", String.valueOf(i)))));
        }
        return segments;
    }
}
