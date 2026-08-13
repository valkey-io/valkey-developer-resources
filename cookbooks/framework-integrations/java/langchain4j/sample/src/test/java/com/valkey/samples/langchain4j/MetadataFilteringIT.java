package com.valkey.samples.langchain4j;

import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import dev.langchain4j.store.embedding.filter.Filter;
import glide.api.GlideClient;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static dev.langchain4j.store.embedding.filter.MetadataFilterBuilder.metadataKey;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for cookbook 02 (Metadata Filtering).
 * Requires a running Valkey instance on localhost:6379.
 */
class MetadataFilteringIT {

    private static final EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

    private GlideClient createClient() throws Exception {
        return GlideClient.createClient(
                GlideClientConfiguration.builder()
                        .address(NodeAddress.builder().host("localhost").port(6379).build())
                        .build()
        ).get();
    }

    @Test
    void shouldFilterByTag() throws Exception {
        GlideClient client = createClient();

        Map<String, FieldInfo> metadataConfig = Map.of(
                "category", new FieldInfo("$.category", "category", new TagField(',', true)),
                "year", new FieldInfo("$.year", "year", new NumericField())
        );

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("test-filter-tag")
                .prefix("test-ft:")
                .metadataConfig(metadataConfig)
                .build();

        List<TextSegment> docs = List.of(
                TextSegment.from("Enable TLS for production.",
                        Metadata.from(Map.of("category", "security", "year", 2025))),
                TextSegment.from("Use connection pooling.",
                        Metadata.from(Map.of("category", "performance", "year", 2024))),
                TextSegment.from("Configure ACLs for multi-tenant.",
                        Metadata.from(Map.of("category", "security", "year", 2024)))
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        List<String> ids = store.addAll(embeddings, docs);

        // When — filter by category=security
        Filter filter = metadataKey("category").isEqualTo("security");
        Embedding query = embeddingModel.embed("security best practices").content();

        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(5)
                        .filter(filter)
                        .build()
        );

        // Then — only security docs returned
        assertThat(results.matches()).allSatisfy(match ->
                assertThat(match.embedded().metadata().getString("category")).isEqualTo("security")
        );
        assertThat(results.matches()).hasSizeGreaterThanOrEqualTo(1);

        // Cleanup
        store.removeAll(ids);
        store.close();
    }

    @Test
    void shouldFilterByNumericRange() throws Exception {
        GlideClient client = createClient();

        Map<String, FieldInfo> metadataConfig = Map.of(
                "category", new FieldInfo("$.category", "category", new TagField(',', true)),
                "year", new FieldInfo("$.year", "year", new NumericField())
        );

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("test-filter-numeric")
                .prefix("test-fn:")
                .metadataConfig(metadataConfig)
                .build();

        List<TextSegment> docs = List.of(
                TextSegment.from("New feature in 2025.",
                        Metadata.from(Map.of("category", "features", "year", 2025))),
                TextSegment.from("Old practice from 2023.",
                        Metadata.from(Map.of("category", "operations", "year", 2023))),
                TextSegment.from("Recent update in 2025.",
                        Metadata.from(Map.of("category", "operations", "year", 2025)))
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        List<String> ids = store.addAll(embeddings, docs);

        // When — filter by year >= 2025
        Filter filter = metadataKey("year").isGreaterThanOrEqualTo(2025);
        Embedding query = embeddingModel.embed("recent changes").content();

        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(5)
                        .filter(filter)
                        .build()
        );

        // Then — only 2025 docs returned
        assertThat(results.matches()).hasSize(2);
        assertThat(results.matches()).allSatisfy(match ->
                assertThat(match.embedded().metadata().getInteger("year")).isGreaterThanOrEqualTo(2025)
        );

        // Cleanup
        store.removeAll(ids);
        store.close();
    }

    @Test
    void shouldCombineFiltersWithAnd() throws Exception {
        GlideClient client = createClient();

        Map<String, FieldInfo> metadataConfig = Map.of(
                "category", new FieldInfo("$.category", "category", new TagField(',', true)),
                "year", new FieldInfo("$.year", "year", new NumericField())
        );

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("test-filter-combined")
                .prefix("test-fc:")
                .metadataConfig(metadataConfig)
                .build();

        List<TextSegment> docs = List.of(
                TextSegment.from("TLS in 2025.",
                        Metadata.from(Map.of("category", "security", "year", 2025))),
                TextSegment.from("ACLs in 2024.",
                        Metadata.from(Map.of("category", "security", "year", 2024))),
                TextSegment.from("Pooling in 2025.",
                        Metadata.from(Map.of("category", "performance", "year", 2025)))
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        List<String> ids = store.addAll(embeddings, docs);

        // When — security AND 2025
        Filter filter = metadataKey("category").isEqualTo("security")
                .and(metadataKey("year").isGreaterThanOrEqualTo(2025));
        Embedding query = embeddingModel.embed("security").content();

        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(5)
                        .filter(filter)
                        .build()
        );

        // Then — only "TLS in 2025" matches both criteria
        assertThat(results.matches()).hasSize(1);
        assertThat(results.matches().get(0).embedded().text()).contains("TLS");

        // Cleanup
        store.removeAll(ids);
        store.close();
    }
}
