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

### Batch/Pipeline Operations
```bash
dotnet run --project BatchPipeline.csproj
```

Demonstrates:
- Atomic batches (transactions)
- Non-atomic pipelines
- Batch execution patterns

### Batch Retry Strategies
```bash
dotnet run --project BatchRetryStrategies.csproj
```

Demonstrates:
- Retry strategy limitation in v0.9.0
- Application-level retry workaround
- Expected API for future versions

### Cluster Operations
```bash
dotnet run --project ClusterOperations.csproj
```

Demonstrates:
- Cluster client creation
- Hash tags for slot control
- Cluster-aware batching

## Docker Validation

Run all demos in Docker:
```bash
./validate.sh
```

## Notes

- All demos use `await using` for automatic client disposal
- Cluster demos require cluster mode (ports 7000-7002)
- Vector search not yet supported in C# GLIDE (use CustomCommand when available)
