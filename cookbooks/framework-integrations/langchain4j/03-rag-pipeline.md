# RAG Pipeline with LangChain4j + Valkey

> Build a complete Retrieval-Augmented Generation pipeline: chunk documents, embed locally, store in Valkey, and answer questions with context-grounded responses.

**Intermediate** · Java · ~25 min

**Who is this for:** Java developers building question-answering systems who want Valkey as the vector store in a RAG architecture — without requiring paid API keys for the default path.

## Prerequisites

- Valkey running locally (see [01 Getting Started](01-getting-started.md))
- Java 17+, Maven 3.8+
- Completed cookbook 01 or equivalent familiarity with `ValkeyEmbeddingStore`
- (Optional) For cloud LLM path: AWS credentials with Bedrock access, or Ollama installed locally

## What You'll Build

A complete Retrieval-Augmented Generation pipeline:

1. **Chunk** documents into segments
2. **Embed** with a local model (AllMiniLmL6V2, 384 dimensions)
3. **Store** in Valkey with metadata
4. **Retrieve** relevant chunks via vector similarity
5. **Answer** questions using retrieved context

The default path runs entirely locally. An optional section shows how to swap in cloud models (Bedrock Titan + Claude) for production use.

## Step 1: Dependencies

```xml
<dependencies>
    <!-- LangChain4j core -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j</artifactId>
        <version>1.0.0</version>
    </dependency>

    <!-- Valkey embedding store -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-community-valkey</artifactId>
        <version>1.0.0-beta3</version>
    </dependency>

    <!-- Local embedding model (no API key needed) -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-embeddings-all-minilm-l6-v2</artifactId>
        <version>1.0.0-beta3</version>
    </dependency>
</dependencies>
```

> **Note:** The sample [`pom.xml`](sample/pom.xml) is the source of truth for tested version combinations. Core `langchain4j` uses the stable release track, while community and extension modules use the beta track.

## Step 2: Connect to Valkey and Set Up the Embedding Model

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

// Valkey connection
GlideClient client = GlideClient.createClient(
        GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .build()
).get();

// Local embedding model — 384 dimensions, runs in-process, no API key
EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();
```

## Step 3: Create the Embedding Store with Metadata

```java
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;

Map<String, FieldInfo> metadataConfig = Map.of(
        "source", new FieldInfo("$.source", "source", new TagField(',', true)),
        "chunk_index", new FieldInfo("$.chunk_index", "chunk_index", new NumericField())
);

ValkeyEmbeddingStore embeddingStore = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(384)
        .indexName("rag-docs")
        .prefix("rag:")
        .metadataConfig(metadataConfig)
        .build();
```

## Step 4: Chunk Documents

```java
import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import dev.langchain4j.data.document.splitter.DocumentSplitter;
import dev.langchain4j.data.segment.TextSegment;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

// Simulate loading documents (in production, use FileSystemDocumentLoader)
List<Document> documents = List.of(
        Document.from("Valkey supports TLS encryption. Configure tls-port, "
                + "tls-cert-file, and tls-key-file in valkey.conf to enable "
                + "encrypted connections. Clients must also be configured with "
                + "the CA certificate.", Metadata.from(Map.of("source", "security-guide"))),
        Document.from("For high availability, deploy Valkey with Sentinel. "
                + "Three sentinel instances monitor the primary and trigger "
                + "automatic failover. Configure sentinel monitor with quorum of 2.",
                Metadata.from(Map.of("source", "ha-guide"))),
        Document.from("Use HNSW indexes for vector search. Set M=16 and "
                + "EF_CONSTRUCTION=200 for a good balance of recall and indexing "
                + "speed. Higher M values improve recall but increase memory usage.",
                Metadata.from(Map.of("source", "vector-guide")))
);

// Split into chunks with overlap for context continuity
DocumentSplitter splitter = DocumentSplitters.recursive(300, 30);

List<TextSegment> segments = new ArrayList<>();
for (Document doc : documents) {
    List<TextSegment> chunks = splitter.split(doc);
    for (int i = 0; i < chunks.size(); i++) {
        TextSegment chunk = chunks.get(i);
        chunk.metadata().put("chunk_index", i);
        segments.add(chunk);
    }
}

System.out.println("Created " + segments.size() + " chunks from " + documents.size() + " documents");
```

## Step 5: Embed and Store

```java
import dev.langchain4j.data.embedding.Embedding;

// Embed all chunks (local model — fast, no network calls)
List<Embedding> embeddings = embeddingModel.embedAll(segments).content();

// Store in Valkey
List<String> ids = embeddingStore.addAll(embeddings, segments);
System.out.println("Stored " + ids.size() + " embeddings in Valkey");
```

## Step 6: Build the Content Retriever

LangChain4j provides `EmbeddingStoreContentRetriever` to wire the store into a retrieval chain:

```java
import dev.langchain4j.rag.content.retriever.EmbeddingStoreContentRetriever;
import dev.langchain4j.rag.content.retriever.ContentRetriever;

ContentRetriever contentRetriever = EmbeddingStoreContentRetriever.builder()
        .embeddingStore(embeddingStore)
        .embeddingModel(embeddingModel)
        .maxResults(3)
        .minScore(0.5)
        .build();
```

## Step 7: Query (Retrieval Only)

Without a chat model, you can still use the retriever to find relevant context:

```java
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import dev.langchain4j.store.embedding.EmbeddingMatch;

Embedding queryEmb = embeddingModel.embed("How do I enable TLS?").content();

EmbeddingSearchResult<TextSegment> results = embeddingStore.search(
        EmbeddingSearchRequest.builder()
                .queryEmbedding(queryEmb)
                .maxResults(3)
                .minScore(0.5)
                .build()
);

System.out.println("Retrieved context:");
for (EmbeddingMatch<TextSegment> match : results.matches()) {
    System.out.printf("  %.3f [%s]: %s%n",
            match.score(),
            match.embedded().metadata().getString("source"),
            match.embedded().text());
}
```

This is the core of RAG — retrieving relevant context from Valkey. The next step wires this into an LLM for answer generation.

## Step 8: Wire into an AI Service (with a Chat Model)

To generate natural-language answers, you need a chat model. LangChain4j supports many providers. Here's the pattern:

```java
import dev.langchain4j.service.AiServices;

interface Assistant {
    String answer(String question);
}

// chatModel can be any LangChain4j ChatLanguageModel implementation
Assistant assistant = AiServices.builder(Assistant.class)
        .chatModel(chatModel)
        .contentRetriever(contentRetriever)
        .build();

String answer = assistant.answer("How do I configure TLS for Valkey?");
System.out.println(answer);
```

**What happens under the hood:**
1. The question is embedded using your embedding model
2. `FT.SEARCH rag-docs "*=>[KNN 3 @vector $BLOB]"` finds the top 3 relevant chunks
3. Retrieved chunks are injected into the prompt as context
4. The chat model generates an answer grounded in the retrieved documents

## Step 9: Query with Metadata Filters

Combine RAG with metadata filtering for scoped retrieval:

```java
import dev.langchain4j.store.embedding.filter.Filter;
import static dev.langchain4j.store.embedding.filter.MetadataFilterBuilder.metadataKey;

// Only retrieve from a specific source document
Filter sourceFilter = metadataKey("source").isEqualTo("security-guide");

ContentRetriever scopedRetriever = EmbeddingStoreContentRetriever.builder()
        .embeddingStore(embeddingStore)
        .embeddingModel(embeddingModel)
        .maxResults(3)
        .minScore(0.5)
        .filter(sourceFilter)
        .build();
```

## Architecture

```text
User Question
     │
     ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Embed Query    │────▶│  Valkey Search    │────▶│  Top-K Docs │
│  (local model)  │     │  FT.SEARCH + KNN │     │  Retrieved  │
└─────────────────┘     └──────────────────┘     └──────┬──────┘
                                                         │
                                                         ▼
                                                 ┌──────────────┐
                                                 │  Chat Model  │
                                                 │  + Context   │
                                                 └──────┬───────┘
                                                        │
                                                        ▼
                                                  Final Answer
```

## Optional: Using Cloud Models (AWS Bedrock)

> **Note:** This section requires AWS credentials with Amazon Bedrock access. [Amazon Bedrock](https://aws.amazon.com/bedrock/) is an AWS service. The default path above runs entirely locally.

For production workloads with larger embedding dimensions and higher-quality answers, swap in Bedrock Titan (embeddings) and Claude (chat):

```xml
<!-- Add to pom.xml -->
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-bedrock</artifactId>
    <version>1.0.0</version>
</dependency>
```

```java
import dev.langchain4j.model.bedrock.BedrockTitanEmbeddingModel;
import dev.langchain4j.model.bedrock.BedrockChatModel;
import software.amazon.awssdk.regions.Region;

// Titan Embeddings (1024 dimensions — rebuild store with dimension=1024)
BedrockTitanEmbeddingModel embeddingModel = BedrockTitanEmbeddingModel.builder()
        .model("amazon.titan-embed-text-v2:0")
        .region(Region.US_WEST_2)
        .dimensions(1024)
        .build();

// Claude for answer generation
BedrockChatModel chatModel = BedrockChatModel.builder()
        .modelId("us.anthropic.claude-sonnet-4-20250514-v1:0")
        .region(Region.US_WEST_2)
        .build();
```

When switching embedding models, remember to update:
- `dimension` in `ValkeyEmbeddingStore.builder()` (384 → 1024)
- Re-ingest all documents (embeddings from different models are not compatible)

## Complete Example

See [`sample/src/main/java/.../RagPipelineExample.java`](sample/src/main/java/com/valkey/samples/langchain4j/RagPipelineExample.java) for the full runnable version (uses the local model path by default).

---

[← 02 Metadata Filtering](02-metadata-filtering.md) | [04 Production Patterns →](04-production.md)
