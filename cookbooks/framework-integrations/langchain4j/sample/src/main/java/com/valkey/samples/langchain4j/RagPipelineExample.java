package com.valkey.samples.langchain4j;

import dev.langchain4j.model.bedrock.BedrockChatModel;
import dev.langchain4j.model.bedrock.BedrockTitanEmbeddingModel;
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.rag.content.retriever.EmbeddingStoreContentRetriever;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.store.embedding.EmbeddingMatch;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import software.amazon.awssdk.regions.Region;

import java.util.List;
import java.util.Map;

/**
 * Cookbook 03 - RAG Pipeline with LangChain4j + Valkey
 *
 * Demonstrates: end-to-end Retrieval-Augmented Generation using
 * Bedrock Titan for embeddings, Valkey for vector storage, and Claude for answers.
 *
 * Prerequisites:
 *   - docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
 *   - AWS credentials configured with Bedrock access (Titan Embeddings + Claude)
 *   - Region: us-west-2 (adjust below if needed)
 */
public class RagPipelineExample {

    /**
     * AI Service interface — LangChain4j generates the implementation at runtime.
     */
    interface Assistant {
        String answer(String question);
    }

    public static void main(String[] args) throws Exception {
        System.out.println("=== LangChain4j + Valkey: RAG Pipeline ===\n");

        // 1. Connect to Valkey
        GlideClient client = GlideClient.createClient(
                GlideClientConfiguration.builder()
                        .address(NodeAddress.builder().host("localhost").port(6379).build())
                        .build()
        ).get();
        System.out.println("Connected to Valkey");

        // 2. Set up Bedrock models
        BedrockTitanEmbeddingModel embeddingModel = BedrockTitanEmbeddingModel.builder()
                .model("amazon.titan-embed-text-v2:0")
                .region(Region.US_WEST_2)
                .dimensions(1024)
                .build();
        System.out.println("Initialized Titan Embeddings (1024 dimensions)");

        BedrockChatModel chatModel = BedrockChatModel.builder()
                .modelId("us.anthropic.claude-sonnet-4-20250514-v1:0")
                .region(Region.US_WEST_2)
                .build();
        System.out.println("Initialized Claude chat model\n");

        // 3. Create embedding store
        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(1024)
                .indexName("rag-demo")
                .prefix("rag:")
                .metadataKeys(List.of("source"))
                .build();
        System.out.println("Created ValkeyEmbeddingStore (index: rag-demo)\n");

        // 4. Ingest sample knowledge base
        List<TextSegment> docs = List.of(
                TextSegment.from(
                        "Valkey supports TLS encryption. Configure tls-port, tls-cert-file, "
                                + "and tls-key-file in valkey.conf to enable encrypted connections. "
                                + "Clients must also be configured with the CA certificate.",
                        Metadata.from(Map.of("source", "security-guide"))),
                TextSegment.from(
                        "For high availability, deploy Valkey with Sentinel. Three sentinel "
                                + "instances monitor the primary and trigger automatic failover. "
                                + "Configure sentinel monitor with quorum of 2.",
                        Metadata.from(Map.of("source", "ha-guide"))),
                TextSegment.from(
                        "Use HNSW indexes for vector search. Set M=16 and EF_CONSTRUCTION=200 "
                                + "for a good balance of recall and indexing speed. Higher M values "
                                + "improve recall but increase memory usage.",
                        Metadata.from(Map.of("source", "vector-guide"))),
                TextSegment.from(
                        "Valkey cluster distributes data across multiple shards using hash slots. "
                                + "Each shard holds a subset of the 16384 hash slots. Use CLUSTER NODES "
                                + "to inspect the topology.",
                        Metadata.from(Map.of("source", "cluster-guide"))),
                TextSegment.from(
                        "Set maxmemory and maxmemory-policy in valkey.conf. For cache workloads, "
                                + "use allkeys-lru. For persistent data, use volatile-lru or noeviction.",
                        Metadata.from(Map.of("source", "operations-guide")))
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        List<String> ids = store.addAll(embeddings, docs);
        System.out.println("Ingested " + ids.size() + " documents into Valkey\n");

        // 5. Demonstrate raw retrieval first
        System.out.println("--- Raw vector search (no LLM) ---");
        Embedding queryEmb = embeddingModel.embed("How do I set up TLS?").content();
        EmbeddingSearchResult<TextSegment> rawResults = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(queryEmb)
                        .maxResults(3)
                        .minScore(0.5)
                        .build()
        );
        for (EmbeddingMatch<TextSegment> match : rawResults.matches()) {
            System.out.printf("  %.3f [%s]: %s%n",
                    match.score(),
                    match.embedded().metadata().getString("source"),
                    match.embedded().text().substring(0, Math.min(80, match.embedded().text().length())) + "...");
        }
        System.out.println();

        // 6. Build RAG assistant
        Assistant assistant = AiServices.builder(Assistant.class)
                .chatModel(chatModel)
                .contentRetriever(EmbeddingStoreContentRetriever.builder()
                        .embeddingStore(store)
                        .embeddingModel(embeddingModel)
                        .maxResults(3)
                        .minScore(0.5)
                        .build())
                .build();
        System.out.println("--- RAG-powered Q&A ---\n");

        // 7. Ask questions
        String[] questions = {
                "How do I enable TLS in Valkey?",
                "What HNSW parameters should I use for vector search?",
                "How does Valkey handle high availability?"
        };

        for (String question : questions) {
            System.out.println("Q: " + question);
            String answer = assistant.answer(question);
            System.out.println("A: " + answer);
            System.out.println();
        }

        // 8. Cleanup
        store.removeAll(ids);
        store.close();
        System.out.println("Done! Cleaned up and closed connection.");
    }
}
