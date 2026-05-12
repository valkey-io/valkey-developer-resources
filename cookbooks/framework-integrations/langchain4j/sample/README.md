# LangChain4j + Valkey Cookbook Sample

Runnable code for the [LangChain4j + Valkey cookbook series](../README.md).

## Prerequisites

1. **Java 17+**
2. **Docker** (for Valkey)
3. **AWS credentials** (for the RAG pipeline example only — Bedrock Titan + Claude)

## Platform Note

The `valkey-glide` native library requires a platform-specific classifier. The `pom.xml` is configured for **macOS ARM** (`osx-aarch_64`). If you're on a different platform, update the classifier in the `valkey-glide` dependency:

| Platform | Classifier |
|----------|-----------|
| macOS ARM (M1/M2/M3) | `osx-aarch_64` |
| Linux x86_64 | `linux-x86_64` |
| Linux ARM | `linux-aarch_64` |

## Running

```bash
# Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9

# Run the quick start example
mvn compile exec:java -Dexec.mainClass="com.valkey.samples.langchain4j.ValkeyQuickStart"
```

## Sample Classes

| Class | Cookbook | Description |
|-------|---------|-------------|
| `ValkeyQuickStart` | [01 - Getting Started](../01-getting-started.md) | Connect, store embeddings, similarity search |
| `MetadataFilteringExample` | [02 - Metadata Filtering](../02-metadata-filtering.md) | Typed metadata + filtered search |
| `RagPipelineExample` | [03 - RAG Pipeline](../03-rag-pipeline.md) | Bedrock RAG pipeline with Claude |
| `ProductionPatternsExample` | [04 - Production Patterns](../04-production.md) | HNSW tuning, batch ingestion, benchmarks |

## Troubleshooting

- **Native library not found**: Check the `valkey-glide` classifier in `pom.xml` matches your platform (see table above).
- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes JSON and Search modules.
- **Bedrock errors**: Ensure AWS credentials are configured and you have access to Titan Embeddings + Claude in us-west-2.
