# Production Patterns for LangChain4j + Valkey

> Configure HNSW vs FLAT indexing, choose distance metrics, tune batch ingestion, and manage connections and errors at scale.

**Advanced** · Java · ~20 min

**Who is this for:** Java developers moving a LangChain4j + Valkey integration from prototype to production who need to understand index tuning, connection lifecycle, and operational best practices.

## Prerequisites

- Valkey running locally — start it with `docker compose -f sample/docker-compose.yml up -d --wait` (see [01 Getting Started](01-getting-started.md) for what the bundle image provides)
- Java 17+, Maven 3.8+
- Familiarity with cookbooks 01–03

## Step 1: Choose an Index Algorithm (HNSW vs FLAT)

The `ValkeyEmbeddingStore` uses HNSW by default. Choose based on your dataset size:

| | HNSW (default) | FLAT |
|---|---|---|
| **Search type** | Approximate nearest neighbor | Exact nearest neighbor |
| **Complexity** | O(log n) | O(n) — linear scan |
| **Recall** | ~95–99% (tunable) | 100% |
| **Memory** | Higher (graph structure overhead) | Lower (vectors only) |
| **Best for** | > 10K documents, latency-sensitive | < 10K documents, recall-critical |

### Configuring HNSW Parameters

The builder uses defaults suitable for most workloads. For custom tuning, pre-create the index:

```java
// Pre-create the index with custom HNSW parameters
valkeyClient.customCommand(new String[]{"FT.CREATE", "my-index", "ON", "JSON",
        "PREFIX", "1", "embedding:",
        "SCHEMA",
        "$.vector", "AS", "vector", "VECTOR", "HNSW", "10",
        "TYPE", "FLOAT32", "DIM", "1024", "DISTANCE_METRIC", "COSINE",
        "M", "32", "EF_CONSTRUCTION", "400",
        "$.text", "AS", "text", "TEXT"}).get();

// Build the store — it detects the existing index
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
        .indexName("my-index")
        .prefix("embedding:")
        .build();
```

**HNSW parameter guide:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| M | 16 | Connections per node. Higher = better recall, more memory |
| EF_CONSTRUCTION | 200 | Build-time search width. Higher = better graph quality, slower indexing |

**Rules of thumb:**

- For 100K–1M documents: M=16, EF_CONSTRUCTION=200
- For 1M–10M documents: M=32, EF_CONSTRUCTION=400
- For maximum recall: M=64, EF_CONSTRUCTION=500

> **Note:** `EF_RUNTIME` is a query-time parameter set per-query, not at index creation.

## Step 2: Choose a Distance Metric

Choose based on your embedding model's training objective:

| Metric | When to Use | Score Range |
|--------|-------------|-------------|
| **COSINE** (default) | Most text embedding models (Titan, OpenAI, MiniLM) | [0, 1] |
| **IP** (Inner Product) | Models trained with dot-product similarity | (-∞, 1] |
| **L2** (Euclidean) | Image embeddings, spatial data | (0, 1] |

The metric is set at index creation time and cannot be changed without recreating the index.

## Step 3: Batch Ingestion

### Sequential Batches

`addAll()` uses `CompletableFuture` internally for concurrent writes. For large jobs, batch your calls to keep inflight requests manageable:

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

### Concurrent Ingestion

For maximum throughput, parallelize both embedding and storage:

```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.CompletableFuture;

ExecutorService executor = Executors.newFixedThreadPool(4);

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

## Step 4: Connection Management

### Client Lifecycle

The `GlideClient` is thread-safe and should be shared across your application:

```java
// Create once at application startup
GlideClient valkeyClient = GlideClient.createClient(config).get();

// Share across multiple stores
ValkeyEmbeddingStore ragStore = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
        .indexName("rag-index")
        .dimension(384)
        .build();

ValkeyEmbeddingStore cacheStore = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
        .indexName("cache-index")
        .dimension(384)
        .build();

// Close at application shutdown
Runtime.getRuntime().addShutdownHook(new Thread(valkeyClient::close));
```

> **Warning:** Calling `close()` on any `ValkeyEmbeddingStore` closes the underlying `GlideClient`.
> If you share a client across multiple stores, manage the client lifecycle separately with a shutdown hook.

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

> **Note:** When using cluster mode, all keys for a given index must route to the same shard. Use hash tags in your prefix (e.g., `{rag}:`) to guarantee co-location.

## Step 5: Error Handling

### Timeout Configuration

```java
ValkeyEmbeddingStore store = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
        .dimension(384)
        .operationTimeoutSeconds(30L)  // Default is 60s
        .build();
```

### Handling Failures

```java
try {
    store.addAll(embeddings, segments);
} catch (Exception e) {
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
} catch (Exception e) {
    log.warn("Valkey search failed, returning empty results", e);
    results = new EmbeddingSearchResult<>(List.of());
}
```

## Step 6: Index Management

### Checking Index State

```java
// List all indexes
Object indexes = valkeyClient.customCommand(new String[]{"FT._LIST"}).get();

// Get detailed info about an index
Object info = valkeyClient.customCommand(new String[]{"FT.INFO", "my-index"}).get();
```

### Rebuilding an Index

If you need to change the schema (add metadata fields, change dimensions, switch metrics):

```java
// 1. Drop the old index (does NOT delete the data)
valkeyClient.customCommand(new String[]{"FT.DROPINDEX", "my-index"}).get();

// 2. Recreate with new schema
ValkeyEmbeddingStore newStore = ValkeyEmbeddingStore.builder()
        .client(valkeyClient)
        .dimension(1024)
        .indexName("my-index")
        .metadataConfig(newMetadataConfig)
        .build();
// Valkey re-indexes existing JSON documents matching the prefix automatically
```

> **Important:** `FT.DROPINDEX` only removes the index definition, not the underlying JSON documents. Re-creating the index with the same prefix triggers automatic re-indexing.

### Memory Estimation

Rough memory per document (1024-dimension float32 vectors):

- Vector storage: ~4 KB
- HNSW graph overhead: ~1–2 KB (depends on M)
- JSON document (text + metadata): varies

For 1M documents at 1024 dimensions: estimate ~6–8 GB RAM.

## Step 7: Scaling Considerations

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

## Complete Example

See [`sample/src/main/java/.../ProductionPatternsExample.java`](sample/src/main/java/com/valkey/samples/langchain4j/ProductionPatternsExample.java)
for the full runnable version demonstrating batch ingestion, concurrent writes, shared clients, and error handling.

---

[← 03 RAG Pipeline](03-rag-pipeline.md)
