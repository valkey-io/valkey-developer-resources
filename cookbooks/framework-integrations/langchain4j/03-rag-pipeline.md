# RAG Pipeline with LangChain4j + Valkey

**Intermediate** · Java · ~25 min

## What You'll Build

A complete Retrieval-Augmented Generation pipeline:

1. **Load** documents from files
2. **Chunk** them into segments
3. **Embed** with Amazon Bedrock Titan Embeddings
4. **Store** in Valkey with metadata
5. **Query** with an LLM (Claude via Bedrock) that uses retrieved context to answer questions

## Prerequisites

- Valkey running locally (see [01 Getting Started](01-getting-started.md))
- AWS credentials configured (`~/.aws/credentials` or environment variables)
- Access to Amazon Bedrock models (Titan Embeddings + Claude)

## Step 1: Dependencies

```xml
<dependencies>
    <!-- LangChain4j core -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j</artifactId>
        <version>1.15.0-beta25</version>
    </dependency>

    <!-- Valkey embedding store -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-community-valkey</artifactId>
        <version>1.15.0-beta25</version>
    </dependency>

    <!-- Amazon Bedrock for embeddings and chat -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-bedrock</artifactId>
        <version>1.15.0-beta25</version>
    </dependency>

    <!-- Document loading and splitting -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-document-parser-apache-tika</artifactId>
        <version>1.15.0-beta25</version>
    </dependency>
</dependencies>
```

## Step 2: Connect to Valkey and Bedrock

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.model.bedrock.BedrockTitanEmbeddingModel;
import dev.langchain4j.model.bedrock.BedrockChatModel;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

// Valkey connection
GlideClient client = GlideClient.createClient(
        GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .build()
).get();

// Bedrock Titan Embeddings (1024 dimensions)
BedrockTitanEmbeddingModel embeddingModel = BedrockTitanEmbeddingModel.builder()
        .model("amazon.titan-embed-text-v2:0")
        .region(Region.US_WEST_2)
        .dimensions(1024)
        .build();

// Claude for answering questions
BedrockChatModel chatModel = BedrockChatModel.builder()
        .modelId("us.anthropic.claude-sonnet-4-20250514-v1:0")
        .region(Region.US_WEST_2)
        .build();
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
        .dimension(1024)
        .indexName("rag-docs")
        .prefix("rag:")
        .metadataConfig(metadataConfig)
        .build();
```

## Step 4: Load and Chunk Documents

```java
import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.document.loader.FileSystemDocumentLoader;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import dev.langchain4j.data.document.splitter.DocumentSplitter;
import dev.langchain4j.data.segment.TextSegment;

import java.nio.file.Path;
import java.util.List;

// Load documents from a directory
List<Document> documents = FileSystemDocumentLoader.loadDocuments(
        Path.of("./docs"),
        glob("*.md")
);

// Split into chunks with overlap for context continuity
DocumentSplitter splitter = DocumentSplitters.recursive(500, 50);

List<TextSegment> segments = new ArrayList<>();
for (Document doc : documents) {
    List<TextSegment> chunks = splitter.split(doc);
    for (int i = 0; i < chunks.size(); i++) {
        // Add metadata to each chunk
        TextSegment chunk = chunks.get(i);
        chunk.metadata().put("source", doc.metadata().getString("file_name"));
        chunk.metadata().put("chunk_index", i);
        segments.add(chunk);
    }
}

System.out.println("Created " + segments.size() + " chunks from " + documents.size() + " documents");
```

## Step 5: Embed and Store

```java
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.model.output.Response;

// Embed all chunks (Bedrock Titan handles batching internally)
Response<List<Embedding>> embeddingResponse = embeddingModel.embedAll(segments);
List<Embedding> embeddings = embeddingResponse.content();

// Store in Valkey
List<String> ids = embeddingStore.addAll(embeddings, segments);
System.out.println("Stored " + ids.size() + " embeddings in Valkey");
```

## Step 6: Build the RAG Chain

LangChain4j provides `EmbeddingStoreContentRetriever` to wire the store into a retrieval chain:

```java
import dev.langchain4j.rag.content.retriever.EmbeddingStoreContentRetriever;
import dev.langchain4j.rag.content.retriever.ContentRetriever;

ContentRetriever contentRetriever = EmbeddingStoreContentRetriever.builder()
        .embeddingStore(embeddingStore)
        .embeddingModel(embeddingModel)
        .maxResults(5)
        .minScore(0.6)
        .build();
```

## Step 7: Query with an AI Service

The simplest way to wire RAG into a conversational interface:

```java
import dev.langchain4j.service.AiServices;

interface Assistant {
    String answer(String question);
}

Assistant assistant = AiServices.builder(Assistant.class)
        .chatModel(chatModel)
        .contentRetriever(contentRetriever)
        .build();

// Ask a question — the assistant retrieves context from Valkey automatically
String answer = assistant.answer("How do I configure TLS for Valkey?");
System.out.println(answer);
```

**What happens under the hood:**
1. The question is embedded using Titan
2. `FT.SEARCH rag-docs "*=>[KNN 5 @vector $BLOB]"` finds the top 5 relevant chunks
3. Retrieved chunks are injected into the prompt as context
4. Claude generates an answer grounded in the retrieved documents

## Step 8: Query with Metadata Filters

Combine RAG with metadata filtering for scoped retrieval:

```java
import dev.langchain4j.store.embedding.filter.Filter;
import static dev.langchain4j.store.embedding.filter.MetadataFilterBuilder.metadataKey;

// Only retrieve from a specific source document
Filter sourceFilter = metadataKey("source").isEqualTo("deployment-guide.md");

ContentRetriever scopedRetriever = EmbeddingStoreContentRetriever.builder()
        .embeddingStore(embeddingStore)
        .embeddingModel(embeddingModel)
        .maxResults(5)
        .minScore(0.6)
        .filter(sourceFilter)
        .build();

Assistant scopedAssistant = AiServices.builder(Assistant.class)
        .chatModel(chatModel)
        .contentRetriever(scopedRetriever)
        .build();

String answer = scopedAssistant.answer("What are the deployment steps?");
```

## Complete Example

```java
import dev.langchain4j.model.bedrock.BedrockChatModel;
import dev.langchain4j.model.bedrock.BedrockTitanEmbeddingModel;
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.rag.content.retriever.EmbeddingStoreContentRetriever;
import dev.langchain4j.service.AiServices;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import software.amazon.awssdk.regions.Region;

import java.util.List;
import java.util.Map;

public class RagPipelineExample {

    interface Assistant {
        String answer(String question);
    }

    public static void main(String[] args) throws Exception {
        // 1. Connect to Valkey
        GlideClient client = GlideClient.createClient(
                GlideClientConfiguration.builder()
                        .address(NodeAddress.builder().host("localhost").port(6379).build())
                        .build()
        ).get();

        // 2. Models
        BedrockTitanEmbeddingModel embeddingModel = BedrockTitanEmbeddingModel.builder()
                .model("amazon.titan-embed-text-v2:0")
                .region(Region.US_WEST_2)
                .dimensions(1024)
                .build();

        BedrockChatModel chatModel = BedrockChatModel.builder()
                .modelId("us.anthropic.claude-sonnet-4-20250514-v1:0")
                .region(Region.US_WEST_2)
                .build();

        // 3. Embedding store
        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(1024)
                .indexName("rag-demo")
                .metadataKeys(List.of("source"))
                .build();

        // 4. Ingest sample documents
        List<TextSegment> docs = List.of(
                TextSegment.from(
                        "Valkey supports TLS encryption. Configure tls-port, tls-cert-file, "
                        + "and tls-key-file in valkey.conf to enable encrypted connections.",
                        Metadata.from(Map.of("source", "security-guide"))),
                TextSegment.from(
                        "For high availability, deploy Valkey with Sentinel. Three sentinel "
                        + "instances monitor the primary and trigger automatic failover.",
                        Metadata.from(Map.of("source", "ha-guide"))),
                TextSegment.from(
                        "Use HNSW indexes for vector search. Set M=16 and EF_CONSTRUCTION=200 "
                        + "for a good balance of recall and indexing speed.",
                        Metadata.from(Map.of("source", "vector-guide")))
        );

        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        store.addAll(embeddings, docs);

        // 5. Build RAG assistant
        Assistant assistant = AiServices.builder(Assistant.class)
                .chatModel(chatModel)
                .contentRetriever(EmbeddingStoreContentRetriever.builder()
                        .embeddingStore(store)
                        .embeddingModel(embeddingModel)
                        .maxResults(3)
                        .minScore(0.5)
                        .build())
                .build();

        // 6. Ask questions
        System.out.println(assistant.answer("How do I enable TLS in Valkey?"));
        System.out.println(assistant.answer("What HNSW parameters should I use?"));

        // 7. Cleanup
        store.close();
    }
}
```

## Architecture

```text
User Question
     │
     ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Embed Query │────▶│  Valkey Search    │────▶│  Top-K Docs │
│ (Titan)     │     │  FT.SEARCH + KNN │     │  Retrieved  │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                     │
                                                     ▼
                                             ┌──────────────┐
                                             │ Claude (LLM) │
                                             │ + Context    │
                                             └──────┬───────┘
                                                    │
                                                    ▼
                                              Final Answer
```

[← Previous: 02 Metadata Filtering](02-metadata-filtering.md) · [Next: 04 Production Patterns →](04-production.md)
