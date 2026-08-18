# Getting Started with LangChain4j + Valkey

> Connect to Valkey, store vector embeddings with a local model, and run your first similarity search — all in Java with zero API keys.

**Beginner** · Java · ~15 min

**Who is this for:** Java developers exploring vector search who want a local, self-contained introduction to storing and querying embeddings in Valkey using LangChain4j.

LangChain4j provides a unified `EmbeddingStore` interface for vector storage.
The `langchain4j-community-valkey` module implements it using Valkey's built-in vector search —
HNSW indexing, native JSON storage, and automatic index management via the official valkey-glide client.

## Prerequisites

- Docker installed
- Java 17+
- Maven 3.8+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.2
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

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
    <version>1.17.2-beta27</version>
</dependency>
```

**Gradle:**

```groovy
implementation 'dev.langchain4j:langchain4j-community-valkey:1.17.2-beta27'
```

> **Note:** The sample [`pom.xml`](sample/pom.xml) is the source of truth for tested version combinations.
> The core `langchain4j` artifact uses a separate release track from the community modules.
> See the pom.xml `<properties>` block for details.
>
> `langchain4j-community` modules are always published with a `-beta` suffix — that is their
> standard release label for community-supported modules, not a pre-release or unstable marker.
> `1.17.2-beta27` is a stable, released artifact available on Maven Central.

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

GlideClient valkeyClient = GlideClient.createClient(config).get();

// 2. Build the embedding store
ValkeyEmbeddingStore embeddingStore = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
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

## Step 7: Clean Up

```java
// Remove specific documents
embeddingStore.removeAll(ids);

// Or remove everything in the index
embeddingStore.removeAll();

// Close the client when done
embeddingStore.close();
```

## How It Works

| Component | Role |
|-----------|------|
| `GlideClient` | Official Valkey Java client — manages connection and command execution |
| `ValkeyEmbeddingStore` | LangChain4j interface implementation — translates store/search operations into Valkey commands |
| `AllMiniLmL6V2EmbeddingModel` | Local ONNX embedding model (384 dimensions) — no API key or network calls |
| Valkey Search | Server-side HNSW index — executes KNN queries over JSON-stored vectors |
| Valkey JSON | Server-side JSON storage — stores embeddings, text, and metadata as structured documents |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `client` | ✓ | — | `GlideClient` instance connected to Valkey |
| `dimension` | ✓ | — | Vector dimension (must match embedding model output) |
| `indexName` | — | `"embedding-index"` | Name of the Valkey Search index |
| `prefix` | — | `"embedding:"` | Key prefix for stored JSON documents |
| `distanceMetric` | — | `COSINE` | Distance metric: `COSINE`, `IP`, or `L2` |
| `algorithm` | — | `HNSW` | Index algorithm: `HNSW` or `FLAT` |
| `metadataKeys` | — | `[]` | List of metadata keys to index as TAG fields |
| `metadataConfig` | — | `{}` | Advanced: typed metadata field definitions |

## Complete Example

See [`sample/src/main/java/.../ValkeyQuickStart.java`](sample/src/main/java/com/valkey/samples/langchain4j/ValkeyQuickStart.java) for the full runnable version.

**Source:** [`langchain4j-community-valkey`](https://github.com/langchain4j/langchain4j-community/tree/main/embedding-stores/langchain4j-community-valkey)
— The official LangChain4j embedding store for Valkey.

---

[Next: 02 Metadata Filtering →](02-metadata-filtering.md)
