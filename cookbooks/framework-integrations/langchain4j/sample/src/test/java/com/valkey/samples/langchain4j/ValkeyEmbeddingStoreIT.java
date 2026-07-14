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
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for cookbook 01 (Getting Started) and basic embedding store operations.
 * Requires a running Valkey instance on localhost:6379.
 *
 * Run with: mvn verify (starts via failsafe plugin)
 */
class ValkeyEmbeddingStoreIT {

    private static final EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

    private GlideClient createClient() throws Exception {
        return GlideClient.createClient(
                GlideClientConfiguration.builder()
                        .address(NodeAddress.builder().host("localhost").port(6379).build())
                        .build()
        ).get();
    }

    @Test
    void shouldStoreAndSearchEmbeddings() throws Exception {
        GlideClient client = createClient();

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("test-quickstart")
                .prefix("test-qs:")
                .build();

        List<TextSegment> docs = List.of(
                TextSegment.from("Valkey is a high-performance in-memory data store."),
                TextSegment.from("Vector search finds similar items by embedding distance."),
                TextSegment.from("HNSW is an algorithm for approximate nearest neighbors.")
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();

        // When
        List<String> ids = store.addAll(embeddings, docs);

        // Then
        assertThat(ids).hasSize(3);

        // Search
        Embedding query = embeddingModel.embed("How does similarity search work?").content();
        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(2)
                        .minScore(0.3)
                        .build()
        );

        assertThat(results.matches()).isNotEmpty();
        assertThat(results.matches().get(0).score()).isGreaterThan(0.3);
        assertThat(results.matches().get(0).embedded().text()).isNotBlank();

        // Cleanup
        store.removeAll(ids);
        store.close();
    }

    @Test
    void shouldAddAndRemoveSingleEmbedding() throws Exception {
        GlideClient client = createClient();

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("test-single")
                .prefix("test-single:")
                .build();

        TextSegment segment = TextSegment.from("Valkey supports JSON and Search modules.");
        Embedding embedding = embeddingModel.embed(segment).content();

        // When
        String id = store.add(embedding, segment);

        // Then
        assertThat(id).isNotBlank();

        // Search should find it
        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(embedding)
                        .maxResults(1)
                        .build()
        );
        assertThat(results.matches()).hasSize(1);
        assertThat(results.matches().get(0).embedded().text())
                .isEqualTo("Valkey supports JSON and Search modules.");

        // Remove and verify
        store.removeAll(List.of(id));
        store.close();
    }
}
