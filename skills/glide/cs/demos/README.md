# C# GLIDE Demos

## Prerequisites
Leverage Docker containerization to satisfy these prerequisites

- .NET 8.0 SDK or higher
- Valkey server running (standalone or cluster)
- Set `VALKEY_HOST` environment variable (defaults to `localhost`)

## Running Demos

### Basic Operations
```bash
cd cs/demos
dotnet run --project BasicOperations.csproj
```

Demonstrates:
- Client creation and connection
- String, hash, list, set operations
- Error handling with specific exception types

### Batch/Pipeline Operations
```bash
dotnet run --project BatchPipeline.csproj
```

Demonstrates:
- Atomic batches (transactions)
- Non-atomic pipelines
- Batch execution patterns

### Cluster Operations
```bash
dotnet run --project ClusterOperations.csproj
```

Demonstrates:
- Cluster client creation
- Hash tags for slot control
- Cluster-aware batching

### Vector Search
```bash
dotnet run --project VectorSearch.csproj
```

Demonstrates:
- FT.CREATE index with vector field
- Storing binary vectors
- KNN vector search using CustomCommand
- Binary data handling

## Notes

- All demos use `await using` for automatic client disposal
- Error handling uses specific exception types (ConnectionException, TimeoutException, ValkeyException)
- Cluster demos require cluster mode (ports 7000-7002)
- Vector search requires Valkey with search module loaded
