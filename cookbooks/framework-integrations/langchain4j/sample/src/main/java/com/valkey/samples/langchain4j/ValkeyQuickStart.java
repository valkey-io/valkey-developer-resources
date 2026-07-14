package com.valkey.samples.langchain4j;

import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
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

import java.util.List;

/**
 * Cookbook 01 - Getting Started with LangChain4j + Valkey
 *
 * Demonstrates: connecting to Valkey, storing embeddings, and running similarity search.
 *
 * Prerequisites:
 *   docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.1
 */
public class ValkeyQuickStart {

    public static void main(String[] args) throws Exception {
        System.out.println("=== LangChain4j + Valkey Quick Start ===\n");

        // 1. Connect to Valkey
        GlideClientConfiguration config = GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .build();
        GlideClient client = GlideClient.createClient(config).get();
        System.out.println("Connected to Valkey");

        // 2. Use a local embedding model (384 dimensions, no API key needed)
        EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();
        System.out.println("Loaded embedding model (384 dimensions)");

        // 3. Create the embedding store
        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("quickstart-index")
                .prefix("quickstart:")
                .build();
        System.out.println("Created ValkeyEmbeddingStore\n");

        // 4. Ingest documents
        List<TextSegment> docs = List.of(
                TextSegment.from("Valkey is a high-performance in-memory data store."),
                TextSegment.from("Vector search finds similar items by embedding distance."),
                TextSegment.from("HNSW is an algorithm for approximate nearest neighbors."),
                TextSegment.from("Valkey supports JSON documents and full-text search."),
                TextSegment.from("LangChain4j provides a unified API for LLM applications in Java.")
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        List<String> ids = store.addAll(embeddings, docs);
        System.out.println("Stored " + ids.size() + " documents\n");

        // 5. Query
        String query = "How does similarity search work?";
        System.out.println("Query: \"" + query + "\"\n");

        Embedding queryEmbedding = embeddingModel.embed(query).content();
        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(queryEmbedding)
                        .maxResults(3)
                        .minScore(0.5)
                        .build()
        );

        System.out.println("Results:");
        for (EmbeddingMatch<TextSegment> match : results.matches()) {
            System.out.printf("  %.3f: %s%n", match.score(), match.embedded().text());
        }

        // 6. Cleanup
        store.removeAll(ids);
        store.close();
        System.out.println("\nDone! Cleaned up and closed connection.");
    }
}
