# Go GLIDE Demos

Working examples for developing the Go GLIDE skill.

## Setup

```bash
cd go/demos
go mod tidy
```

## Run Demos

```bash
go run basic_operations.go
go run batch_pipeline.go
go run vector_search.go
go run cluster_operations.go
go run batch_retry_strategies.go
```

## Testing

All demos connect to Valkey at host identified in `VALKEY_HOST` environment variable at port `6379` (standalone) or `:7000` (cluster) for local testing.
