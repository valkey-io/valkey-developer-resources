# RAG Pipeline with Spring AI and Valkey

> Build a complete Retrieval-Augmented Generation pipeline that ingests documents,
> stores embeddings in Valkey, and uses retrieved context to ground LLM responses.

**Intermediate** · Java · ~20 min

**Who is this for:** Developers building AI-powered applications that need accurate,
grounded answers from their own data — such as documentation chatbots, knowledge
bases, or customer support systems.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - Metadata Filtering](02-metadata-filtering.md)
- Valkey running with search module
- [Ollama](https://ollama.com/) running locally (or OpenAI API key for hosted inference)

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## What is RAG?

Retrieval-Augmented Generation combines vector search with LLM generation:

```text
┌──────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────┐
│  Query   │────▶│  Embed &    │────▶│  Valkey  │────▶│  LLM    │
│          │     │  Search     │     │  KNN     │     │  + ctx  │
└──────────┘     └─────────────┘     └──────────┘     └─────────┘
                                          │                  │
                                   retrieve top-K      generate answer
                                   relevant docs       grounded in docs
```

This prevents hallucination by giving the LLM relevant context from your own data.

## Step 1: Project Setup

Add these dependencies to `pom.xml`:

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-valkey-store</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-ollama-spring-boot-starter</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-pdf-document-reader</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-tika-document-reader</artifactId>
    </dependency>
</dependencies>
```

<details>
<summary>Optional: Using OpenAI instead of Ollama</summary>

Replace `spring-ai-ollama-spring-boot-starter` with:

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
</dependency>
```

Configure `spring.ai.openai.api-key=${OPENAI_API_KEY}` in your properties. Requires a
paid API key.

</details>

## Step 2: Configure the Vector Store for RAG

```java
@Configuration
public class RagConfig {

    @Bean
    public GlideClient glideClient() throws Exception {
        return GlideClient.createClient(
            GlideClientConfiguration.builder()
                .address(NodeAddress.builder()
                    .host("localhost")
                    .port(6379)
                    .build())
                .build()
        ).get();
    }

    @Bean
    public ValkeyVectorStore vectorStore(GlideClient client, EmbeddingModel embeddingModel) throws Exception {
        var store = ValkeyVectorStore.builder(client, embeddingModel)
            .indexName("rag-docs")
            .prefix("rag:")
            .vectorAlgorithm(ValkeyVectorStore.Algorithm.HNSW)
            .metadataFields(
                MetadataField.tag("source"),
                MetadataField.tag("doc_type"),
                MetadataField.numeric("chunk_index")
            )
            .initializeSchema(true)
            .build();
        store.afterPropertiesSet();
        return store;
    }
}
```

## Step 3: Document Ingestion with Chunking

Split documents into chunks for better retrieval granularity:

```java
import org.springframework.ai.document.Document;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;

@Service
public class DocumentIngestionService {

    private final VectorStore vectorStore;

    public DocumentIngestionService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }

    public void ingestText(String content, String source, String docType) {
        // Split into chunks of ~800 tokens with 100 token overlap
        var splitter = new TokenTextSplitter(800, 100, 5, 10000, true);

        var document = new Document(content,
            Map.of("source", source, "doc_type", docType));

        List<Document> chunks = splitter.apply(List.of(document));

        // Add chunk index metadata
        for (int i = 0; i < chunks.size(); i++) {
            chunks.get(i).getMetadata().put("chunk_index", i);
        }

        vectorStore.add(chunks);
    }

    public void ingestPdf(Resource pdfResource, String source) {
        var reader = new PagePdfDocumentReader(pdfResource);
        List<Document> pages = reader.get();

        var splitter = new TokenTextSplitter(800, 100, 5, 10000, true);
        List<Document> chunks = splitter.apply(pages);

        chunks.forEach(chunk -> {
            chunk.getMetadata().put("source", source);
            chunk.getMetadata().put("doc_type", "pdf");
        });

        vectorStore.add(chunks);
    }
}
```

## Step 4: Build the RAG Service

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.vectorstore.SearchRequest;

@Service
public class RagService {

    private final VectorStore vectorStore;
    private final ChatClient chatClient;

    private static final String SYSTEM_PROMPT = """
        You are a helpful assistant. Answer the user's question based ONLY on
        the provided context. If the context doesn't contain enough information
        to answer, say so clearly. Do not make up information.

        Context:
        {context}
        """;

    public RagService(VectorStore vectorStore, ChatClient.Builder chatClientBuilder) {
        this.vectorStore = vectorStore;
        this.chatClient = chatClientBuilder.build();
    }

    public String ask(String question) {
        // Retrieve relevant documents
        List<Document> relevantDocs = vectorStore.similaritySearch(
            SearchRequest.builder()
                .query(question)
                .topK(5)
                .similarityThreshold(0.7)
                .build()
        );

        if (relevantDocs.isEmpty()) {
            return "I don't have enough information to answer that question.";
        }

        // Build context from retrieved documents
        String context = relevantDocs.stream()
            .map(Document::getText)
            .collect(Collectors.joining("\n\n---\n\n"));

        // Generate answer with context
        return chatClient.prompt()
            .system(SYSTEM_PROMPT.replace("{context}", context))
            .user(question)
            .call()
            .content();
    }
}
```

## Step 5: Add a REST Controller

```java
@RestController
@RequestMapping("/api/rag")
public class RagController {

    private final RagService ragService;
    private final DocumentIngestionService ingestionService;

    public RagController(RagService ragService, DocumentIngestionService ingestionService) {
        this.ragService = ragService;
        this.ingestionService = ingestionService;
    }

    @PostMapping("/ingest")
    public ResponseEntity<String> ingest(@RequestBody IngestRequest request) {
        ingestionService.ingestText(request.content(), request.source(), request.docType());
        return ResponseEntity.ok("Ingested successfully");
    }

    @PostMapping("/ask")
    public ResponseEntity<AskResponse> ask(@RequestBody AskRequest request) {
        String answer = ragService.ask(request.question());
        return ResponseEntity.ok(new AskResponse(answer));
    }

    record IngestRequest(String content, String source, String docType) {}
    record AskRequest(String question) {}
    record AskResponse(String answer) {}
}
```

## Step 6: Filtered RAG (Scoped Retrieval)

Scope retrieval to specific document types or sources:

```java
public String askWithFilter(String question, String source) {
    var builder = new FilterExpressionBuilder();

    List<Document> relevantDocs = vectorStore.similaritySearch(
        SearchRequest.builder()
            .query(question)
            .topK(5)
            .similarityThreshold(0.7)
            .filterExpression(builder.eq("source", source).build())
            .build()
    );

    // ... same context building and LLM call
}
```

This is useful for multi-tenant RAG or when users should only see results from
specific document collections.

## Step 7: Docker Compose for Development

```yaml
services:
  valkey:
    image: valkey/valkey-bundle:8.1.1
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      - SPRING_AI_OLLAMA_BASE_URL=http://host.docker.internal:11434
    depends_on:
      valkey:
        condition: service_healthy
```

## Performance Considerations

### HNSW vs FLAT

| Algorithm | Best For | Trade-off |
| --- | --- | --- |
| HNSW | Large datasets (>10K docs) | Faster search, more memory, approximate |
| FLAT | Small datasets (<10K docs) | Exact results, slower on large sets |

### Chunking Strategy

- **Chunk size:** 500–1000 tokens works well for most use cases
- **Overlap:** 10–20% overlap prevents losing context at chunk boundaries
- **Too small:** Loses context; too large: dilutes relevance

### Embedding Model Choice

| Model | Dimensions | Speed | Quality |
| --- | --- | --- | --- |
| `text-embedding-3-small` | 1536 | Fast | Good |
| `text-embedding-3-large` | 3072 | Slower | Better |
| Ollama `nomic-embed-text` | 768 | Local | Good (no API cost) |

## Troubleshooting

### LLM answers don't reference retrieved context

- Print `relevantDocs` to verify retrieval is working
- Lower `similarityThreshold` if no documents are returned
- Check that the system prompt template correctly inserts context

### Slow search on large datasets

- Switch to HNSW algorithm if using FLAT
- Reduce `topK` to fetch fewer results
- Add metadata filters to narrow the search space

### Out of memory with many documents

- Monitor Valkey memory: `docker exec valkey-spring-ai valkey-cli INFO memory`
- Consider reducing embedding dimensions (use `text-embedding-3-small`)
- Set `maxmemory` in Valkey config with appropriate eviction policy

---

[← Back to Metadata Filtering](02-metadata-filtering.md) · [← Back to README](README.md)
