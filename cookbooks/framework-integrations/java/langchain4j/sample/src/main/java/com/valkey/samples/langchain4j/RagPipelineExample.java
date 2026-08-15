package com.valkey.samples.langchain4j;

import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import dev.langchain4j.rag.content.retriever.EmbeddingStoreContentRetriever;
import dev.langchain4j.store.embedding.EmbeddingMatch;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.util.List;
import java.util.Map;

/**
 * Cookbook 03 - RAG Pipeline with LangChain4j + Valkey
 *
 * Demonstrates: the retrieval side of Retrieval-Augmented Generation using
 * a local embedding model, Valkey for vector storage, and context retrieval.
 *
 * This example runs entirely locally — no API keys or paid services required.
 * For a full RAG pipeline with answer generation, add a chat model (see the
 * "Optional: Using Cloud Models" section in 03-rag-pipeline.md).
 *
 * Prerequisites:
 *   docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.1
 */
public class RagPipelineExample {

    public static void main(String[] args) throws Exception {
        System.out.println("=== LangChain4j + Valkey: RAG Pipeline (Retrieval) ===\n");

        // 1. Connect to Valkey
        GlideClientConfiguration config = GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .build();
        GlideClient valkeyClient = GlideClient.createClient(config).get();
        System.out.println("Connected to Valkey");

        // 2. Local embedding model (384 dimensions, no API key needed)
        EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();
        System.out.println("Loaded local embedding model (384 dimensions)\n");

        // ---------------------------------------------------------
        // Optional: swap the local model for a cloud embedding model.
        // Vendor-neutral — OpenRouter fronts OpenAI, Anthropic, Google, Bedrock, Azure,
        // and more through one OpenAI-compatible endpoint. Set OPENROUTER_API_KEY.
        //
        // EmbeddingModel embeddingModel = OpenAiEmbeddingModel.builder()
        //         .baseUrl("https://openrouter.ai/api/v1")
        //         .apiKey(System.getenv("OPENROUTER_API_KEY"))
        //         .modelName("openai/text-embedding-3-small")
        //         .build();
        //
        // Note: update the store dimension below to match the model
        // (text-embedding-3-small = 1536).
        // ---------------------------------------------------------

        // 3. Create embedding store
        ValkeyEmbeddingStore valkeyStore = ValkeyEmbeddingStore.builder()
                .client(valkeyClient)
                .dimension(384)
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
        List<String> ids = valkeyStore.addAll(embeddings, docs);
        System.out.println("Ingested " + ids.size() + " documents into Valkey\n");

        // 5. Demonstrate retrieval (the "R" in RAG)
        System.out.println("--- Context retrieval for RAG ---\n");

        String[] questions = {
                "How do I set up TLS?",
                "What HNSW parameters should I use?",
                "How does Valkey handle high availability?"
        };

        for (String question : questions) {
            System.out.println("Q: " + question);

            Embedding queryEmb = embeddingModel.embed(question).content();
            EmbeddingSearchResult<TextSegment> results = valkeyStore.search(
                    EmbeddingSearchRequest.builder()
                            .queryEmbedding(queryEmb)
                            .maxResults(2)
                            .minScore(0.3)
                            .build()
            );

            System.out.println("Retrieved context:");
            for (EmbeddingMatch<TextSegment> match : results.matches()) {
                System.out.printf("  %.3f [%s]: %s%n",
                        match.score(),
                        match.embedded().metadata().getString("source"),
                        match.embedded().text().substring(0,
                                Math.min(80, match.embedded().text().length())) + "...");
            }
            System.out.println();
        }

        // ---------------------------------------------------------
        // Optional: Wire retrieval into an AI Service for answer generation.
        // Define the chat model here, at the point of use. Vendor-neutral via
        // OpenRouter (OpenAI-compatible) — swap baseUrl/modelName for any provider.
        //
        // ChatModel chatModel = OpenAiChatModel.builder()
        //         .baseUrl("https://openrouter.ai/api/v1")
        //         .apiKey(System.getenv("OPENROUTER_API_KEY"))
        //         .modelName("openai/gpt-4o-mini")
        //         .build();
        //
        // interface Assistant {
        //     String answer(String question);
        // }
        //
        // Assistant assistant = AiServices.builder(Assistant.class)
        //         .chatModel(chatModel)
        //         .contentRetriever(EmbeddingStoreContentRetriever.builder()
        //                 .embeddingStore(valkeyStore)
        //                 .embeddingModel(embeddingModel)
        //                 .maxResults(3)
        //                 .minScore(0.5)
        //                 .build())
        //         .build();
        //
        // System.out.println(assistant.answer("How do I enable TLS?"));
        // ---------------------------------------------------------

        // 6. Cleanup
        valkeyStore.removeAll(ids);
        // close() also closes the underlying GlideClient passed to the builder —
        // do not use `valkeyClient` after this point.
        valkeyStore.close();
        System.out.println("Done! Cleaned up and closed connection.");
    }
}
