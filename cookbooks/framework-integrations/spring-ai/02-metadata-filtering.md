# Metadata Filtering with Spring AI and Valkey

> Use TAG and NUMERIC metadata filters to scope similarity searches, enabling
> multi-tenant isolation, category-based retrieval, and time-range queries.

**Intermediate** · Java · ~15 min

**Who is this for:** Developers who have completed the Getting Started guide and need
to add structured filtering to their vector searches — such as limiting results to
a specific user, category, or date range.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with search module

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## How Metadata Filtering Works

ValkeyVectorStore supports two field types for filtering:

| Field Type | Use Case | Example |
| --- | --- | --- |
| `TAG` | Exact match on string values | category, source, user_id, status |
| `NUMERIC` | Range queries on numbers | year, price, rating, timestamp |

Filters are applied **before** the KNN search (pre-filtering), so only matching
documents participate in the similarity calculation.

## Step 1: Define Metadata Fields

Declare filterable fields when building the vector store:

```java
var vectorStore = ValkeyVectorStore.builder(client, embeddingModel)
    .indexName("filtered-docs")
    .prefix("doc:")
    .metadataFields(
        MetadataField.tag("category"),
        MetadataField.tag("author"),
        MetadataField.tag("status"),
        MetadataField.numeric("year"),
        MetadataField.numeric("rating")
    )
    .initializeSchema(true)
    .build();

vectorStore.afterPropertiesSet();
```

Each `MetadataField` maps to a JSON path in the stored document (`$.category`,
`$.year`, etc.) and creates a corresponding field in the FT index schema.

## Step 2: Store Documents with Metadata

```java
List<Document> documents = List.of(
    new Document("Introduction to vector databases and their applications",
        Map.of("category", "database", "author", "alice", "year", 2024, "rating", 4.5)),
    new Document("Building RAG pipelines with Spring AI",
        Map.of("category", "ai", "author", "bob", "year", 2025, "rating", 4.8)),
    new Document("Valkey architecture and performance characteristics",
        Map.of("category", "database", "author", "alice", "year", 2025, "rating", 4.2)),
    new Document("Fine-tuning LLMs for domain-specific tasks",
        Map.of("category", "ai", "author", "charlie", "year", 2024, "rating", 3.9)),
    new Document("Caching strategies for AI inference pipelines",
        Map.of("category", "infrastructure", "author", "bob", "year", 2025, "rating", 4.1))
);

vectorStore.add(documents);
```

## Step 3: Filter with Spring AI Expressions

Spring AI provides a `FilterExpressionBuilder` for type-safe filter construction:

### TAG filter (exact match)

```java
import org.springframework.ai.vectorstore.filter.FilterExpressionBuilder;

var builder = new FilterExpressionBuilder();

// Find AI-related documents only
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("vector search")
        .topK(5)
        .filterExpression(builder.eq("category", "ai").build())
        .build()
);
```

### NUMERIC filter (range query)

```java
// Documents from 2025 only
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("database performance")
        .topK(5)
        .filterExpression(builder.eq("year", 2025).build())
        .build()
);

// Documents with rating >= 4.0
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("AI applications")
        .topK(5)
        .filterExpression(builder.gte("rating", 4.0).build())
        .build()
);
```

### Combined filters (AND/OR)

```java
// AI docs from 2025 with high rating
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("machine learning")
        .topK(5)
        .filterExpression(
            builder.and(
                builder.eq("category", "ai"),
                builder.and(
                    builder.eq("year", 2025),
                    builder.gte("rating", 4.0)
                )
            ).build()
        )
        .build()
);
```

### NOT filter

```java
// Everything except infrastructure docs
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("system design")
        .topK(5)
        .filterExpression(builder.ne("category", "infrastructure").build())
        .build()
);
```

## Step 4: Multi-Tenant Isolation

Use TAG filters to isolate data per tenant:

```java
// Store with tenant metadata
vectorStore.add(List.of(
    new Document("Tenant A's proprietary knowledge",
        Map.of("tenant_id", "tenant-a", "category", "internal")),
    new Document("Tenant B's documentation",
        Map.of("tenant_id", "tenant-b", "category", "docs"))
));

// Search scoped to tenant A only
List<Document> tenantResults = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("knowledge base")
        .topK(10)
        .filterExpression(builder.eq("tenant_id", "tenant-a").build())
        .build()
);
```

For stronger isolation, combine tenant filters with separate prefixes:

```java
var tenantAStore = ValkeyVectorStore.builder(client, embeddingModel)
    .indexName("tenant-a-index")
    .prefix("tenant-a:")
    .metadataFields(MetadataField.tag("category"))
    .initializeSchema(true)
    .build();
```

## How Filters Map to Valkey Search

Spring AI filter expressions are converted to Valkey Search query syntax:

| Spring AI Expression | Valkey Search Query |
| --- | --- |
| `eq("category", "ai")` | `@category:{ai}` |
| `eq("year", 2025)` | `@year:[2025 2025]` |
| `gte("rating", 4.0)` | `@rating:[4.0 +inf]` |
| `lte("rating", 3.0)` | `@rating:[-inf 3.0]` |
| `ne("status", "draft")` | `-@status:{draft}` |
| `and(eq("a","x"), eq("b","y"))` | `(@a:{x} @b:{y})` |
| `or(eq("a","x"), eq("a","y"))` | `(@a:{x} \| @a:{y})` |

The full query sent to Valkey looks like:

```text
(filter_expression)=>[KNN 5 @embedding $BLOB AS vector_score]
```

## Important: Fields Must Be Declared

Only metadata fields declared in `metadataFields()` are indexed and filterable.
If you filter on an undeclared field, the search will fail with an error from
Valkey Search.

To add a new filterable field after the index exists:

1. Drop the existing index: `FT.DROPINDEX spring-ai-index`
2. Add the field to `metadataFields()`
3. Restart the application (index will be recreated with `initializeSchema(true)`)
4. Re-ingest documents (existing JSON docs retain their data, but the new field
   needs to be present in the JSON for filtering)

## Troubleshooting

### Filter returns no results but unfiltered search works

- Verify the field is declared in `metadataFields()` with the correct type
- Check that the metadata value was included when adding the document
- For TAG fields, values are case-sensitive: `"AI"` ≠ `"ai"`

### ResponseError: field not found

The field name in your filter doesn't match any indexed field. Check spelling and
ensure it's declared as a `MetadataField`.

### NUMERIC filter on string value

If you declared a field as `NUMERIC` but stored a string value (e.g., `"2025"` instead
of `2025`), the filter will not match. Ensure numeric metadata values are actual numbers.

---

[→ Next: RAG Pipeline](03-rag-pipeline.md) · [← Back to Getting Started](01-getting-started.md)
