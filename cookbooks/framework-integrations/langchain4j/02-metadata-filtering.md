# Semantic Search with Metadata Filtering

**Intermediate** · Java · ~20 min

## Why Metadata Filtering?

Vector similarity alone isn't always enough. When you search for "deployment best practices," you probably want results from a specific category, within a date range, or from a particular source. Metadata filtering lets you combine vector similarity with structured constraints — Valkey evaluates both in a single query.

## Supported Filter Types

The `ValkeyEmbeddingStore` supports three metadata field types:

| Field Type | Operators | Example |
|-----------|-----------|---------|
| **TAG** | eq, neq, in, notIn | `category = "security"` |
| **NUMERIC** | eq, neq, gt, gte, lt, lte | `year >= 2024` |
| **TEXT** | eq, neq, in, notIn | `author = "Alice"` |

Logical operators `AND`, `OR`, and `NOT` can combine any of these.

## Step 1: Define Metadata Fields

When building the store, declare which metadata keys should be indexed and their types:

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.TextField;

import java.util.Map;

// Define metadata schema
Map<String, FieldInfo> metadataConfig = Map.of(
        "category", new FieldInfo("$.category", "category", new TagField(',', true)),
        "year",     new FieldInfo("$.year", "year", new NumericField()),
        "author",   new FieldInfo("$.author", "author", new TextField())
);

ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(384)
        .indexName("docs-with-metadata")
        .metadataConfig(metadataConfig)
        .build();
```

**Key points:**
- The first argument (`$.category`) is the JSON path in the stored document
- The second argument (`category`) is the field alias used in queries
- The third argument defines the field type and its options

### Shortcut: Tag-Only Metadata

If all your metadata fields are simple tags (exact match), use the convenience method:

```java
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(384)
        .metadataKeys(List.of("category", "source", "language"))
        .build();
```

This creates TAG fields for each key automatically.

## Step 2: Store Documents with Metadata

```java
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.segment.TextSegment;

List<TextSegment> segments = List.of(
        TextSegment.from(
                "Use TLS encryption for all Valkey connections in production.",
                Metadata.from(Map.of("category", "security", "year", 2025, "author", "Alice"))
        ),
        TextSegment.from(
                "HNSW indexes trade memory for faster approximate search.",
                Metadata.from(Map.of("category", "performance", "year", 2024, "author", "Bob"))
        ),
        TextSegment.from(
                "Set maxmemory-policy to allkeys-lru for cache workloads.",
                Metadata.from(Map.of("category", "operations", "year", 2025, "author", "Alice"))
        ),
        TextSegment.from(
                "Enable AUTH and ACL for multi-tenant deployments.",
                Metadata.from(Map.of("category", "security", "year", 2024, "author", "Charlie"))
        )
);

List<Embedding> embeddings = embeddingModel.embedAll(segments).content();
store.addAll(embeddings, segments);
```

**Under the hood:** Each document is stored as:
```json
{
  "vector": [0.12, -0.34, ...],
  "text": "Use TLS encryption for all Valkey connections in production.",
  "category": "security",
  "year": 2025,
  "author": "Alice"
}
```

## Step 3: Filter by Tag (Exact Match)

```java
import dev.langchain4j.store.embedding.filter.MetadataFilterBuilder;
import static dev.langchain4j.store.embedding.filter.MetadataFilterBuilder.metadataKey;

// Find security-related documents similar to the query
Filter securityFilter = metadataKey("category").isEqualTo("security");

EmbeddingSearchRequest request = EmbeddingSearchRequest.builder()
        .queryEmbedding(embeddingModel.embed("encryption best practices").content())
        .maxResults(5)
        .filter(securityFilter)
        .build();

EmbeddingSearchResult<TextSegment> results = store.search(request);
```

**Generated Valkey query:** `@category:{security}=>[KNN 5 @vector $BLOB]`

## Step 4: Filter by Numeric Range

```java
// Only documents from 2025 or later
Filter recentFilter = metadataKey("year").isGreaterThanOrEqualTo(2025);

EmbeddingSearchRequest request = EmbeddingSearchRequest.builder()
        .queryEmbedding(queryEmbedding)
        .maxResults(5)
        .filter(recentFilter)
        .build();
```

**Generated Valkey query:** `@year:[2025 inf]=>[KNN 5 @vector $BLOB]`

## Step 5: Combine Filters with AND / OR

```java
// Security docs from 2025+
Filter combined = metadataKey("category").isEqualTo("security")
        .and(metadataKey("year").isGreaterThanOrEqualTo(2025));

// Security OR performance docs
Filter either = metadataKey("category").isEqualTo("security")
        .or(metadataKey("category").isEqualTo("performance"));
```

**Generated Valkey queries:**
- AND: `(@category:{security} @year:[2025 inf])=>[KNN 5 @vector $BLOB]`
- OR: `(@category:{security} | @category:{performance})=>[KNN 5 @vector $BLOB]`

## Step 6: IN / NOT IN Filters

```java
// Documents in any of these categories
Filter inFilter = metadataKey("category").isIn(List.of("security", "operations"));

// Documents NOT by a specific author
Filter notByBob = metadataKey("author").isNotEqualTo("Bob");
```

## Step 7: Remove by Filter

You can delete documents matching a filter without knowing their IDs:

```java
// Remove all documents from 2024
Filter oldDocs = metadataKey("year").isLessThan(2025);
store.removeAll(oldDocs);
```

**Under the hood:** This runs `FT.SEARCH` to find matching document keys, then `DEL` to remove them in batches.

## Complete Example

```java
import dev.langchain4j.community.store.embedding.valkey.ValkeyEmbeddingStore;
import dev.langchain4j.data.document.Metadata;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import dev.langchain4j.store.embedding.EmbeddingMatch;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingSearchResult;
import dev.langchain4j.store.embedding.filter.Filter;
import glide.api.GlideClient;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.configuration.GlideClientConfiguration;
import glide.api.models.configuration.NodeAddress;

import java.util.List;
import java.util.Map;

import static dev.langchain4j.store.embedding.filter.MetadataFilterBuilder.metadataKey;

public class MetadataFilteringExample {

    public static void main(String[] args) throws Exception {
        // Connect
        GlideClient client = GlideClient.createClient(
                GlideClientConfiguration.builder()
                        .address(NodeAddress.builder().host("localhost").port(6379).build())
                        .build()
        ).get();

        EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

        // Create store with typed metadata
        Map<String, FieldInfo> metadataConfig = Map.of(
                "category", new FieldInfo("$.category", "category", new TagField(',', true)),
                "year", new FieldInfo("$.year", "year", new NumericField())
        );

        ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
                .client(client)
                .dimension(384)
                .indexName("filtered-docs")
                .metadataConfig(metadataConfig)
                .build();

        // Ingest
        List<TextSegment> docs = List.of(
                TextSegment.from("Enable TLS for production Valkey.",
                        Metadata.from(Map.of("category", "security", "year", 2025))),
                TextSegment.from("Use connection pooling for throughput.",
                        Metadata.from(Map.of("category", "performance", "year", 2024))),
                TextSegment.from("Configure ACLs for multi-tenant access.",
                        Metadata.from(Map.of("category", "security", "year", 2024)))
        );
        List<Embedding> embeddings = embeddingModel.embedAll(docs).content();
        store.addAll(embeddings, docs);

        // Search: security docs from 2025+
        Filter filter = metadataKey("category").isEqualTo("security")
                .and(metadataKey("year").isGreaterThanOrEqualTo(2025));

        Embedding query = embeddingModel.embed("secure connections").content();
        EmbeddingSearchResult<TextSegment> results = store.search(
                EmbeddingSearchRequest.builder()
                        .queryEmbedding(query)
                        .maxResults(5)
                        .filter(filter)
                        .build()
        );

        for (EmbeddingMatch<TextSegment> match : results.matches()) {
            System.out.printf("%.3f: %s [%s]%n",
                    match.score(),
                    match.embedded().text(),
                    match.embedded().metadata().toMap());
        }

        store.close();
    }
}
```

## Filter Quick Reference

| LangChain4j Filter | Valkey Query Syntax |
|-------------------|---------------------|
| `isEqualTo("val")` (TAG) | `@field:{val}` |
| `isEqualTo(42)` (NUMERIC) | `@field:[42 42]` |
| `isNotEqualTo("val")` | `(-@field:{val})` |
| `isGreaterThan(10)` | `@field:[(10 inf]` |
| `isGreaterThanOrEqualTo(10)` | `@field:[10 inf]` |
| `isLessThan(10)` | `@field:[-inf (10]` |
| `isLessThanOrEqualTo(10)` | `@field:[-inf 10]` |
| `isIn(["a","b"])` (TAG) | `(@field:{a} \| @field:{b})` |
| `isNotIn(["a","b"])` (TAG) | `(-@field:{a}) (-@field:{b})` |
| `.and(...)` | `(left right)` |
| `.or(...)` | `(left \| right)` |

[← Previous: 01 Getting Started](01-getting-started.md) · [Next: 03 RAG Pipeline →](03-rag-pipeline.md)
