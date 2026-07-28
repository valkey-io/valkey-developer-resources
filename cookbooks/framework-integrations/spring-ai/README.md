# Spring AI + Valkey Cookbook

> Build AI applications with Spring AI's ValkeyVectorStore — a native vector store
> implementation using Valkey Glide for semantic search, RAG pipelines, and document retrieval.

## Cookbooks

| # | Title | Description | Level |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure ValkeyVectorStore, add documents, and run similarity searches. | Beginner, ~15 min, Java |
| 02 | <nobr>[Metadata Filtering](02-metadata-filtering.md)</nobr> | Use TAG and NUMERIC filters to scope searches by metadata fields. | Intermediate, ~15 min, Java |
| 03 | <nobr>[RAG Pipeline](03-rag-pipeline.md)</nobr> | Build a Retrieval-Augmented Generation pipeline with Spring AI and Valkey. | Intermediate, ~20 min, Java |

## Prerequisites

- Java 17 or newer
- Maven 3.9+
- Docker (for Valkey)
- Valkey 8.1+ with search module (`valkey/valkey-bundle`)
- An embedding model provider (OpenAI, Ollama, or other Spring AI-supported model)

## How Spring AI Uses Valkey

Spring AI's `ValkeyVectorStore` stores documents as JSON in Valkey and leverages
valkey-search for vector similarity:

- **JSON document storage** — Each document is stored via `JSON.SET` with content,
  embedding, and metadata fields
- **Vector indexing** — `FT.CREATE` with HNSW or FLAT algorithm on JSON paths
- **KNN search** — `FT.SEARCH` with `KNN` queries and `DIALECT 2`
- **Filter expressions** — TAG and NUMERIC field filtering in search queries
- **Distance metrics** — COSINE (default), L2, and Inner Product with score normalization
- **Native client** — Uses `valkey-glide` (Java) for direct Valkey communication

## Quick Start

```java
// Configure the vector store
var client = GlideClient.createClient(
    GlideClientConfiguration.builder()
        .address(NodeAddress.builder().host("localhost").port(6379).build())
        .build()
).get();

var vectorStore = ValkeyVectorStore.builder(client, embeddingModel)
    .indexName("my-index")
    .prefix("doc:")
    .metadataFields(
        MetadataField.tag("category"),
        MetadataField.numeric("year")
    )
    .initializeSchema(true)
    .build();

vectorStore.afterPropertiesSet();

// Add documents
vectorStore.add(List.of(
    new Document("Spring AI integrates with Valkey for vector search",
        Map.of("category", "ai", "year", 2025))
));

// Search
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder().query("vector database").topK(5).build()
);
```

## Upstream PR Status

> **Note:** [spring-projects/spring-ai#5471](https://github.com/spring-projects/spring-ai/pull/5471)
> is an open PR that adds the `spring-ai-valkey-store` module. It uses `valkey-glide` 2.2.5
> and targets Spring AI 2.0.0. Until merged, build from the PR branch or use a snapshot
> repository if available.

## References

- [Spring AI Documentation](https://docs.spring.io/spring-ai/reference/)
- [Valkey Search Commands](https://github.com/valkey-io/valkey-search/blob/main/COMMANDS.md)
- [Valkey Glide Java Client](https://github.com/valkey-io/valkey-glide)
- [PR #5471 — Add Valkey Vector Store module](https://github.com/spring-projects/spring-ai/pull/5471)

---

[← Back to Valkey Samples](../../../README.md)
