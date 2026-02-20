# Java GLIDE Demos

Working examples for developing the Java GLIDE skill.

## Setup

```bash
cd java/demos
mvn clean compile
```

## Test Connection

```bash
mvn exec:java -Dexec.mainClass="BasicOperations"
```

## Demos

- `BasicOperations.java` - Connect, set/get, error handling
- `BatchPipeline.java` - Atomic transactions vs non-atomic pipelines
- `VectorSearch.java` - FT.CREATE index, add documents, FT.SEARCH with KNN
- `ClusterOperations.java` - Multi-node routing, hash slot constraints

## Testing

All demos connect to Valkey host from `VALKEY_HOST` environment variable and port `6379` for local testing.
