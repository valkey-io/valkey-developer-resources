# Getting Started with LangChain4j + Valkey

**Beginner** · Java · ~15 min

## What is LangChain4j + Valkey?

[LangChain4j](https://github.com/langchain4j/langchain4j) is the Java framework for building LLM-powered applications. It provides a unified `EmbeddingStore` interface for vector storage and retrieval. The `langchain4j-community-valkey` module implements this interface using Valkey's built-in vector search capabilities:

  * **Sub-millisecond similarity search** — HNSW indexing with configurable distance metrics
  * **Native JSON storage** — embeddings, text, and metadata stored as structured JSON documents
  * **Automatic index management** — creates the Valkey Search index on first use
  * **valkey-glide client** — the official high-performance Valkey client for Java

## Step 1: Start Valkey

Docker installed and Java 17+ required.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

The `valkey-bundle` image includes JSON and Search modules needed for vector indexing. Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Add the Dependency

**Maven:**

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-community-valkey</artifactId>
    <version>1.15.0-beta25</version>
</dependency>
```

**Gradle:**

```groovy
implementation 'dev.langchain4j:langchain4j-community-valkey:1.15.0-beta25'
```

This pulls in `valkey-glide` (the official Valkey Java client) transitively.

## Step 3: Connect and Create the Store

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

// 1. Create a GlideClient connection
GlideClientConfiguration config = GlideClientConfiguration.builder()
        .address(NodeAddress.builder().host("localhost").port(6379).build())
        .build();

GlideClient client = GlideClient.createClient(config).get();

// 2. Build the embedding store
ValkeyEmbeddingStore embeddingStore = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(384)          // Must match your embedding model's output dimension
        .indexName("my-index")   // Optional, defaults to "embedding-index"
        .prefix("docs:")         // Optional, defaults to "embedding:"
        .build();
```

**What happens:** On `build()`, the store checks if the index exists in Valkey. If not, it creates one with HNSW indexing and COSINE distance metric (the defaults).

## Step 4: Store Embeddings

```java
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;

// Store a single embedding with associated text
TextSegment segment = TextSegment.from("Valkey is an open-source in-memory data store.");
Embedding embedding = embeddingModel.embed(segment).content();

String id = embeddingStore.add(embedding, segment);
System.out.println("Stored with ID: " + id);
```

**Under the hood:** This executes `JSON.SET docs:<uuid> $ '{"vector":[...],"text":"..."}'` in Valkey.

## Step 5: Search by Similarity

```java
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import dev.langchain4j.store.embedding.EmbeddingMatch;

// Embed the query
Embedding queryEmbedding = embeddingModel.embed("What is Valkey?").content();

// Search for the 3 most similar documents
EmbeddingSearchRequest request = EmbeddingSearchRequest.builder()
        .queryEmbedding(queryEmbedding)
        .maxResults(3)
        .minScore(0.7)  // Only return results with score >= 0.7
        .build();

EmbeddingSearchResult<TextSegment> result = embeddingStore.search(request);

for (EmbeddingMatch<TextSegment> match : result.matches()) {
    System.out.printf("Score: %.3f | Text: %s%n",
            match.score(), match.embedded().text());
}
```

**Under the hood:** This executes `FT.SEARCH my-index "*=>[KNN 3 @vector $BLOB]"` with the query vector as a parameter.

## Step 6: Batch Ingestion

For multiple documents, use `addAll` for better throughput:

```java
List<TextSegment> segments = List.of(
        TextSegment.from("Valkey supports vector similarity search."),
        TextSegment.from("HNSW provides approximate nearest neighbor search."),
        TextSegment.from("Valkey stores data in memory for sub-millisecond access.")
);

List<Embedding> embeddings = embeddingModel.embedAll(segments).content();

List<String> ids = embeddingStore.addAll(embeddings, segments);
System.out.println("Stored " + ids.size() + " documents");
```

**Under the hood:** Each document is written concurrently via `JSON.SET` with `CompletableFuture` for maximum throughput.

## Step 7: Clean Up

```java
// Remove specific documents
embeddingStore.removeAll(ids);

// Or remove everything in the index
embeddingStore.removeAll();

// Close the client when done
embeddingStore.close();
```

## How It Works Under the Hood

| Operation | Valkey Command | Typical Latency |
|-----------|---------------|-----------------|
| Store embedding | `JSON.SET docs:<id> $ '{...}'` | ~0.2ms |
| Similarity search | `FT.SEARCH my-index "*=>[KNN 3 @vector $BLOB]"` | ~0.5ms |
| Check index exists | `FT._LIST` | ~0.1ms |
| Create index | `FT.CREATE my-index ON JSON PREFIX 1 docs: ...` | ~1ms |
| Remove by ID | `DEL docs:<id>` | ~0.1ms |
| Remove by filter | `FT.SEARCH` + `DEL` (batched) | varies |

## Complete Example

```java
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

public class ValkeyQuickStart {

    public static void main(String[] args) throws Exception {
        // 1. Connect to Valkey
        GlideClientConfiguration config = GlideClientConfiguration.builder()
                .address(NodeAddress.builder().host("localhost").port(6379).build())
                .build();
        GlideClient client = GlideClient.createClient(config).get();

        // 2. Use a local embedding model (384 dimensions)
        EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

        // 3. Create the store
        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .build();

        // 4. Ingest documents
        List<TextSegment> docs = List.of(
                TextSegment.from("Valkey is a high-performance in-memory data store."),
                TextSegment.from("Vector search finds similar items by embedding distance."),
                TextSegment.from("HNSW is an algorithm for approximate nearest neighbors.")
        );
        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        store.addAll(embeddings, docs);

        // 5. Query
        Embedding query = embeddingModel.embed("How does similarity search work?").content();
        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(2)
                        .minScore(0.5)
                        .build()
        );

        for (EmbeddingMatch<TextSegment> match : results.matches()) {
            System.out.printf("%.3f: %s%n", match.score(), match.embedded().text());
        }

        // 6. Cleanup
        store.close();
    }
}
```

**Source:** [`langchain4j-community-valkey`](https://github.com/langchain4j/langchain4j-community/tree/main/embedding-stores/langchain4j-community-valkey) — The official LangChain4j embedding store for Valkey.

[Next: 02 Metadata Filtering →](02-metadata-filtering.md)
