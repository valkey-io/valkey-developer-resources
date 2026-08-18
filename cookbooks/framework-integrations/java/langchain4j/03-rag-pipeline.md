# RAG Pipeline with LangChain4j + Valkey

> Use Valkey as the vector store in a RAG pipeline: chunk documents, embed locally, store them in Valkey, and retrieve the most relevant context by vector similarity. Generation — turning that context into an answer with an LLM — is a short hand-off shown at the end; Valkey's role is the retrieval half.

**Intermediate** · Java · ~25 min

**Who is this for:** Java developers building question-answering systems who want Valkey as the vector store in a RAG architecture — without requiring paid API keys for the default path.

## Prerequisites

- Valkey running locally — start it with `docker compose -f sample/docker-compose.yml up -d --wait` (see [01 Getting Started](01-getting-started.md) for what the bundle image provides)
- Java 17+, Maven 3.8+
- Completed cookbook 01 or equivalent familiarity with `ValkeyEmbeddingStore`
- (Optional) To use a hosted embedder instead of the local model: an `OPENROUTER_API_KEY` (OpenRouter is OpenAI-compatible and vendor-neutral)

## What You'll Build

A retrieval pipeline backed by Valkey:

1. **Chunk** documents into segments
2. **Embed** with a local model (AllMiniLmL6V2, 384 dimensions)
3. **Store** in Valkey with metadata
4. **Retrieve** relevant chunks via vector similarity

Everything runs locally with no API keys. Valkey's role in RAG is exactly this
retrieval half — turning retrieved context into a natural-language answer is a
short hand-off to any LLM (shown at the end, [Generating Answers](#generating-answers-beyond-valkey)),
and doesn't involve Valkey. An optional section also covers swapping the local
embedder for a hosted one.

## Step 1: Dependencies

```xml
<dependencies>
    <!-- LangChain4j core -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j</artifactId>
        <version>1.17.2</version>
    </dependency>

    <!-- Valkey embedding store -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-community-valkey</artifactId>
        <version>1.17.2-beta27</version>
    </dependency>

    <!-- Local embedding model (no API key needed) -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-embeddings-all-minilm-l6-v2</artifactId>
        <version>1.17.2-beta27</version>
    </dependency>
</dependencies>
```

> **Note:** The sample [`pom.xml`](sample/pom.xml) is the source of truth for tested version combinations.
> Core `langchain4j` uses the stable release track, while community and extension modules use the beta track.

## Step 2: Connect to Valkey and Set Up the Embedding Model

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

// Valkey connection
GlideClient valkeyClient = GlideClient.createClient(
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
        .client(valkeyClient)
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

This is the core of RAG — and the whole of Valkey's role in it: retrieving the
most relevant context by vector similarity. Turning that context into an answer
is a hand-off to an LLM (see [Generating Answers](#generating-answers-beyond-valkey) below).

## Step 8: Query with Metadata Filters

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

## Generating Answers (beyond Valkey)

Valkey's job ends once you've retrieved the relevant context. To turn that
context into a natural-language answer, pass this store's retriever to a
LangChain4j [`AiServices`](https://docs.langchain4j.dev/tutorials/ai-services)
with any chat model — for example a local Ollama model, or a hosted one via
OpenRouter. That step is pure LLM/framework territory and doesn't involve Valkey,
so it's out of scope for this cookbook; see the
[LangChain4j RAG documentation](https://docs.langchain4j.dev/tutorials/rag) for
the `contentRetriever(...)` wiring.

## Architecture

```text
User Question
     │
     ▼
┌─────────────────┐     ┌──────────────────┐      ┌─────────────┐
│  Embed Query    │────▶│  Valkey Search    │────▶│  Top-K Docs │
│  (local model)  │     │  FT.SEARCH + KNN │      │  Retrieved  │
└─────────────────┘     └──────────────────┘      └──────┬──────┘
                                                         │
                                                         ▼
                                                 hand off to your LLM
                                              (generation — outside Valkey)
```

## Optional: Using a Hosted Embedding Model (via OpenRouter)

> **Note:** This section requires an `OPENROUTER_API_KEY`. [OpenRouter](https://openrouter.ai/) exposes an OpenAI-compatible endpoint that fronts OpenAI, Anthropic, Google, Bedrock, Azure, and more — so one dependency and one code path stay vendor-neutral. The default path above runs entirely locally.

If you'd rather not run embeddings locally, swap the local embedder for a hosted
one through OpenRouter. This is the one model choice that affects Valkey: the
embedder's output dimension determines the store's index dimension.

```xml
<!-- Add to pom.xml -->
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-open-ai</artifactId>
    <version>1.17.2</version>
</dependency>
```

```java
import dev.langchain4j.model.openai.OpenAiEmbeddingModel;

// Hosted embeddings (dimensions vary by model — rebuild the store to match)
EmbeddingModel embeddingModel = OpenAiEmbeddingModel.builder()
        .baseUrl("https://openrouter.ai/api/v1")
        .apiKey(System.getenv("OPENROUTER_API_KEY"))
        .modelName("openai/text-embedding-3-small")
        .build();
```

When switching embedding models, remember to update:

- `dimension` in `ValkeyEmbeddingStore.builder()` to match the hosted model's output
- Re-ingest all documents (embeddings from different models are not compatible)

## Complete Example

See [`sample/src/main/java/.../RagPipelineExample.java`](sample/src/main/java/com/valkey/samples/langchain4j/RagPipelineExample.java) for the full runnable version (uses the local model path by default).

---

[← 02 Metadata Filtering](02-metadata-filtering.md) | [04 Production Patterns →](04-production.md)
