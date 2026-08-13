# LangChain4j + Valkey Cookbook Sample

Runnable code for the [LangChain4j + Valkey cookbook series](../README.md).

## Prerequisites

1. **Docker** (for Valkey)
2. **Java 17+**
3. **Maven 3.8+**

## Setup

```bash
# Start Valkey
docker compose up -d

# Compile
mvn compile
```

## Running

```bash
# 01 - Getting Started (store embeddings, similarity search)
mvn exec:java -Dexec.mainClass="com.valkey.samples.langchain4j.ValkeyQuickStart"

# 02 - Metadata Filtering (TAG, NUMERIC filters)
mvn exec:java -Dexec.mainClass="com.valkey.samples.langchain4j.MetadataFilteringExample"

# 03 - RAG Pipeline (retrieval with local model)
mvn exec:java -Dexec.mainClass="com.valkey.samples.langchain4j.RagPipelineExample"

# 04 - Production Patterns (batch ingestion, concurrent writes)
mvn exec:java -Dexec.mainClass="com.valkey.samples.langchain4j.ProductionPatternsExample"
```

## Testing

Run integration tests against a live Valkey instance:

```bash
mvn verify
```

Tests exercise embedding store operations and metadata filtering using a local embedding model (no API keys required).

## Platform Notes

The `valkey-glide` native library requires a platform-specific classifier. The pom.xml uses Maven profiles to auto-detect your OS:

| Platform | Profile (auto-activated) | Classifier |
|----------|-------------------------|------------|
| Linux x86_64 | `linux-x86_64` | `linux-x86_64` |
| Linux ARM64 | `linux-aarch64` | `linux-aarch_64` |
| macOS ARM (Apple Silicon) | `osx-aarch64` | `osx-aarch_64` |
| macOS Intel | `osx-x86_64` | `osx-x86_64` |

## Teardown

```bash
docker compose down
```

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `ValkeyQuickStart.java` | [01 - Getting Started](../01-getting-started.md) | Connect, store embeddings, similarity search |
| `MetadataFilteringExample.java` | [02 - Metadata Filtering](../02-metadata-filtering.md) | TAG/NUMERIC filters, combined AND/OR, remove by filter |
| `RagPipelineExample.java` | [03 - RAG Pipeline](../03-rag-pipeline.md) | Chunk, embed, store, retrieve context for RAG |
| `ProductionPatternsExample.java` | [04 - Production](../04-production.md) | Batch ingestion, concurrent writes, shared client, error handling |
