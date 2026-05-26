# Production Patterns for LangChain4j + Valkey

**Advanced** · Java · ~20 min

## Overview

This cookbook covers the decisions and configurations that matter when moving from a demo to production: index algorithm selection, distance metrics, batch ingestion, connection management, error handling, and scaling.

## Index Algorithms: HNSW vs FLAT

The `ValkeyEmbeddingStore` uses HNSW by default. Here's when to choose each:

| | HNSW (default) | FLAT |
|---|---|---|
| **Search type** | Approximate nearest neighbor | Exact nearest neighbor |
| **Speed** | O(log n) — sub-millisecond at scale | O(n) — linear scan |
| **Recall** | ~95-99% (tunable) | 100% |
| **Memory** | Higher (graph structure overhead) | Lower (vectors only) |
| **Best for** | > 10K documents, latency-sensitive | < 10K documents, recall-critical |

### Configuring HNSW Parameters

The schema builder doesn't expose HNSW tuning directly, but you can control the algorithm choice:

```java
// Default: HNSW with COSINE distance
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(1024)
        .build();
```

For advanced HNSW tuning (M, EF_CONSTRUCTION), create the index manually before building the store:

```java
// Pre-create the index with custom HNSW parameters
client.customCommand(new String[]{"FT.CREATE", "my-index", "ON", "JSON",
        "PREFIX", "1", "embedding:",
        "SCHEMA",
        "$.vector", "AS", "vector", "VECTOR", "HNSW", "10",
        "TYPE", "FLOAT32", "DIM", "1024", "DISTANCE_METRIC", "COSINE",
        "M", "32", "EF_CONSTRUCTION", "400",
        "$.text", "AS", "text", "TEXT"}).get();

// Now build the store — it detects the existing index
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(client)
        .indexName("my-index")
        .prefix("embedding:")
        .build();
```

**HNSW parameter guide:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| M | 16 | Connections per node. Higher = better recall, more memory |
| EF_CONSTRUCTION | 200 | Build-time search width. Higher = better graph quality, slower indexing |

**Note:** `EF_RUNTIME` is a query-time parameter, not an index creation parameter. It controls the search width at query time and is set per-query.

**Rules of thumb:**
- For 100K–1M documents: M=16, EF_CONSTRUCTION=200
- For 1M–10M documents: M=32, EF_CONSTRUCTION=400
- For maximum recall: M=64, EF_CONSTRUCTION=500

## Distance Metrics

Choose based on your embedding model's training objective:

| Metric | When to Use | Score Range |
|--------|-------------|-------------|
| **COSINE** (default) | Most text embedding models (Titan, OpenAI, Cohere) | [0, 1] |
| **IP** (Inner Product) | Models trained with dot-product similarity | (-∞, 1] |
| **L2** (Euclidean) | Image embeddings, spatial data | (0, 1] |

The metric is set at index creation time and cannot be changed without recreating the index.

## Batch Ingestion Performance

### Concurrent Writes

`addAll()` already uses `CompletableFuture` internally for concurrent writes. For large ingestion jobs, batch your calls:

```java
int batchSize = 500;
for (int i = 0; i < segments.size(); i += batchSize) {
    int end = Math.min(i + batchSize, segments.size());
    List<TextSegment> batch = segments.subList(i, end);
    List<Embedding> batchEmbeddings = embeddings.subList(i, end);

    store.addAll(batchEmbeddings, batch);

    System.out.printf("Ingested %d/%d%n", end, segments.size());
}
```

### Embedding Model Throughput

The embedding step is usually the bottleneck, not Valkey. For Bedrock Titan:
- Single request: ~50ms for one document
- Batch: use `embedAll()` which handles batching per the model's limits
- For very large corpora: parallelize embedding calls across threads

```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

ExecutorService executor = Executors.newFixedThreadPool(4);

// Split work across threads for embedding
List<CompletableFuture<Void>> futures = new ArrayList<>();
for (int i = 0; i < segments.size(); i += batchSize) {
    int start = i;
    int end = Math.min(i + batchSize, segments.size());
    futures.add(CompletableFuture.runAsync(() -> {
        List<TextSegment> batch = segments.subList(start, end);
        List<Embedding> embs = embeddingModel.embedAll(batch).content();
        store.addAll(embs, batch);
    }, executor));
}

CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
executor.shutdown();
```

## Connection Management

### Client Lifecycle

The `GlideClient` is thread-safe and should be shared across your application:

```java
// Create once at application startup
GlideClient client = GlideClient.createClient(config).get();

// Share across multiple stores if needed
ValkeyEmbeddingStore ragStore = ValkeyEmbeddingStore.builder()
        .client(client)
        .indexName("rag-index")
        .dimension(1024)
        .build();

ValkeyEmbeddingStore cacheStore = ValkeyEmbeddingStore.builder()
        .client(client)
        .indexName("cache-index")
        .dimension(1024)
        .build();

// Close at application shutdown
// Note: close() on the store closes the client — only call it on the last store
// or manage the client lifecycle separately
Runtime.getRuntime().addShutdownHook(new Thread(client::close));
```

> **Warning:** Calling `close()` on any `ValkeyEmbeddingStore` closes the underlying `GlideClient`. If you share a client across multiple stores, only close the last store — or manage the client lifecycle separately with a shutdown hook as shown above.

### Connection Configuration

```java
GlideClientConfiguration config = GlideClientConfiguration.builder()
        .address(NodeAddress.builder()
                .host("valkey.example.com")
                .port(6379)
                .build())
        .useTLS(true)                    // Enable for production
        .credentials(ServerCredentials.builder()
                .password("your-password")
                .build())
        .requestTimeout(5000)            // 5 second timeout
        .build();
```

### Cluster Mode

For Valkey Cluster deployments, use `GlideClusterClient`:

> **Note:** Cluster mode support in `ValkeyEmbeddingStore` depends on the store accepting `GlideClusterClient`. Verify compatibility with your version of `langchain4j-community-valkey` — this may require the store to accept a `BaseClient` interface.

```java
import glide.api.GlideClusterClient;
import glide.api.models.configuration.GlideClusterClientConfiguration;

GlideClusterClientConfiguration clusterConfig = GlideClusterClientConfiguration.builder()
        .address(NodeAddress.builder().host("node1.example.com").port(6379).build())
        .address(NodeAddress.builder().host("node2.example.com").port(6379).build())
        .address(NodeAddress.builder().host("node3.example.com").port(6379).build())
        .useTLS(true)
        .build();

GlideClusterClient clusterClient = GlideClusterClient.createClient(clusterConfig).get();
```

**Note:** When using cluster mode, all keys for a given index must route to the same shard. Use hash tags in your prefix (e.g., `{rag}:`) to guarantee co-location — Valkey Cluster hashes only the content inside `{}` (CRC16 mod 16384) to determine the slot.

## Error Handling

### Timeout Configuration

```java
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(1024)
        .operationTimeoutSeconds(30L)  // Default is 60s
        .build();
```

### Handling Failures

The store throws `ValkeyRequestFailedException` for all Valkey errors:

```java
try {
    store.addAll(embeddings, segments);
} catch (ValkeyRequestFailedException e) {
    if (e.getMessage().contains("timed out")) {
        // Retry with backoff
    } else if (e.getMessage().contains("CLUSTERDOWN")) {
        // Cluster is recovering — wait and retry
    } else {
        throw e;
    }
}
```

### Graceful Degradation

For search operations, consider falling back gracefully:

```java
EmbeddingSearchResult<TextSegment> results;
try {
    results = store.search(request);
} catch (ValkeyRequestFailedException e) {
    log.warn("Valkey search failed, returning empty results", e);
    results = new EmbeddingSearchResult<>(List.of());
}
```

## Index Management

### Checking Index State

```java
// Verify the index exists and is ready
// FT._LIST returns all indexes
Object[] indexes = client.customCommand(new String[]{"FT._LIST"}).get();
```

### Rebuilding an Index

If you need to change the schema (add metadata fields, change dimensions, switch metrics):

```java
// 1. Drop the old index (does NOT delete the data)
client.customCommand(new String[]{"FT.DROPINDEX", "my-index"}).get();

// 2. Recreate with new schema
ValkeyEmbeddingStore newStore = ValkeyEmbeddingStore.builder()
        .client(client)
        .dimension(1024)
        .indexName("my-index")
        .metadataConfig(newMetadataConfig)
        .build();

// The index will re-scan existing JSON documents matching the prefix
```

**Important:** `FT.DROPINDEX` only removes the index definition, not the underlying JSON documents. When you recreate the index with the same prefix, Valkey re-indexes existing documents automatically.

### Memory Estimation

Rough memory per document:
- Vector (1024 float32): ~4 KB
- HNSW graph overhead: ~1-2 KB per document (depends on M)
- JSON document (text + metadata): varies
- **Total estimate:** ~6-8 KB per document for 1024-dim embeddings

For 1M documents at 1024 dimensions: ~6-8 GB RAM.

## Scaling Considerations

| Scale | Recommendation |
|-------|---------------|
| < 100K docs | Single Valkey instance, HNSW, default params |
| 100K–1M docs | Single instance with tuned HNSW (M=32), adequate RAM |
| 1M–10M docs | Valkey Cluster, partition by use case (separate indexes) |
| > 10M docs | Multiple clusters, application-level sharding by tenant/domain |

### Key Practices

1. **Separate indexes by use case** — don't mix RAG documents with cache entries in the same index
2. **Use prefixes** — `rag:`, `cache:`, `user:` to isolate data and enable targeted cleanup
3. **Set `maxmemory`** — prevent OOM by configuring memory limits with `allkeys-lru` eviction
4. **Monitor with `FT.INFO`** — track index size, memory usage, and query latency

```java
// Check index stats
Object[] info = client.customCommand(new String[]{"FT.INFO", "my-index"}).get();
```

[← Previous: 03 RAG Pipeline](03-rag-pipeline.md)
