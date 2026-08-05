# Getting Started with Spring AI and Valkey

> Configure Spring AI's ValkeyVectorStore to store document embeddings in Valkey and
> perform semantic similarity searches using valkey-search.

**Beginner** · Java · ~15 min

**Who is this for:** Java developers using Spring Boot who want to add vector search
capabilities to their applications using Valkey as the backend store.

## Prerequisites

- Java 17+
- Maven 3.9+
- Docker
- [Ollama](https://ollama.com/) running locally with an embedding model (e.g., `nomic-embed-text`)

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Step 1: Start Valkey with Search Module

```bash
docker run -d --name valkey-spring-ai \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:8.1.1
```

Verify the search module is loaded:

```bash
docker exec valkey-spring-ai valkey-cli MODULE LIST
```

You should see `search` in the output.

## Step 2: Create a Spring Boot Project

Add these dependencies to your `pom.xml`:

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
</dependencies>

<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-bom</artifactId>
            <version>2.0.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

<details>
<summary>Optional: Using OpenAI instead of Ollama</summary>

Replace the Ollama starter with:

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
</dependency>
```

And configure your API key in `application.properties`:

```properties
spring.ai.openai.api-key=${OPENAI_API_KEY}
spring.ai.openai.embedding.options.model=text-embedding-3-small
```

This requires a paid API key and sends data to OpenAI's servers.

</details>

## Step 3: Configure the Vector Store

```java
import glide.api.GlideClient;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;
import org.springframework.ai.vectorstore.valkey.ValkeyVectorStore;
import org.springframework.ai.vectorstore.valkey.ValkeyVectorStore.MetadataField;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ValkeyConfig {

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
            .indexName("spring-ai-index")
            .prefix("embedding:")
            .initializeSchema(true)
            .build();
        store.afterPropertiesSet();
        return store;
    }
}
```

Set your Ollama embedding model in `application.properties`:

```properties
spring.ai.ollama.embedding.options.model=nomic-embed-text
spring.ai.ollama.base-url=http://localhost:11434
```

## Step 4: Add Documents

```java
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import java.util.List;
import java.util.Map;

@Service
public class DocumentService {

    private final VectorStore vectorStore;

    public DocumentService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }

    public void ingestDocuments() {
        List<Document> documents = List.of(
            new Document("Valkey is a high-performance key-value store",
                Map.of("source", "docs", "year", 2024)),
            new Document("Spring AI provides a unified API for AI models",
                Map.of("source", "blog", "year", 2025)),
            new Document("Vector search enables semantic similarity matching",
                Map.of("source", "tutorial", "year", 2025))
        );

        vectorStore.add(documents);
    }
}
```

## Step 5: Search for Similar Documents

```java
import org.springframework.ai.vectorstore.SearchRequest;

public List<Document> search(String query) {
    return vectorStore.similaritySearch(
        SearchRequest.builder()
            .query(query)
            .topK(5)
            .similarityThreshold(0.7)
            .build()
    );
}
```

Each result includes:

- `document.getText()` — the original content
- `document.getMetadata()` — metadata fields plus distance score
- `document.getScore()` — normalized similarity score (0.0–1.0)

## How It Works

```text
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Your App   │────▶│  Spring AI   │────▶│      Valkey      │
│             │     │  ValkeyStore │     │  (valkey-bundle) │
└─────────────┘     └──────────────┘     └──────────────────┘
                           │                       │
                    embed query              FT.SEARCH KNN
                    via EmbeddingModel       on HNSW index
                           │                       │
                    ┌──────▼──────┐         ┌──────▼──────┐
                    │   Ollama /  │         │  JSON docs  │
                    │   OpenAI    │         │  + vectors  │
                    └─────────────┘         └─────────────┘
```

1. Documents are embedded via the configured `EmbeddingModel`
2. Embeddings + content + metadata stored as JSON in Valkey via `JSON.SET`
3. `FT.CREATE` builds an HNSW index on the vector field
4. Queries are embedded, then `FT.SEARCH` runs a KNN lookup
5. Results are scored and filtered by similarity threshold

## Configuration Reference

| Property | Default | Description |
| --- | --- | --- |
| `indexName` | `spring-ai-index` | Name of the FT index in Valkey |
| `prefix` | `embedding:` | Key prefix for stored documents |
| `contentFieldName` | `content` | JSON field name for document text |
| `embeddingFieldName` | `embedding` | JSON field name for vector data |
| `vectorAlgorithm` | `HNSW` | Index algorithm (`HNSW` or `FLAT`) |
| `distanceMetric` | `COSINE` | Distance metric (`COSINE`, `L2`, `IP`) |
| `initializeSchema` | `false` | Auto-create index on startup |
| `metadataFields` | `[]` | Metadata fields to index for filtering |

## Troubleshooting

### Connection refused on port 6379

Ensure Valkey is running:

```bash
docker ps | grep valkey-spring-ai
```

If not running, start it with the command from Step 1.

### Index already exists error

The `initializeSchema` option skips creation if the index already exists. To recreate:

```bash
docker exec valkey-spring-ai valkey-cli FT.DROPINDEX spring-ai-index
```

### Empty search results

- Verify documents were stored: `docker exec valkey-spring-ai valkey-cli KEYS "embedding:*"`
- Check the index: `docker exec valkey-spring-ai valkey-cli FT.INFO spring-ai-index`
- Lower the `similarityThreshold` (default filtering may be too strict)

---

[→ Next: Metadata Filtering](02-metadata-filtering.md) · [← Back to README](README.md)
