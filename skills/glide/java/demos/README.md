# Java GLIDE Demos

Working examples for developing the Java GLIDE skill.

## Setup

```bash
cd java/demos
./gradlew build
```

## Core Demos

- `BasicOperations.java` - Connect, set/get, error handling
- `BatchPipeline.java` - Atomic transactions vs non-atomic pipelines
- `VectorSearch.java` - FT.CREATE index, add documents, FT.SEARCH with KNN
- `ClusterOperations.java` - Multi-node routing, hash slot constraints
- `AntiPatternDemo.java` - 4 anti-patterns with demonstrations
- `AsyncExceptionHandling.java` - Async vs blocking exception patterns

## Project Integration Demos

### SpringBootDemo.java
Validates REST API patterns with CompletableFuture (simulates Spring Boot controller).

```bash
./gradlew run -PmainClass=main.java.SpringBootDemo
```

### BatchImporter.java
Validates CLI batch processing patterns (try-with-resources, pipelines).

```bash
./gradlew run -PmainClass=main.java.BatchImporter
```

## Running Demos

```bash
# Set Valkey host (optional)
export VALKEY_HOST=localhost

# Run any demo
./gradlew run -PmainClass=main.java.BasicOperations
./gradlew run -PmainClass=main.java.SpringBootDemo
```

## Testing

All demos connect to Valkey host from `VALKEY_HOST` environment variable and port `6379` for local testing.
