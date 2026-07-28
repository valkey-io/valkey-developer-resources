# Spring AI + Valkey Sample

Validates the ValkeyVectorStore patterns from Spring AI against Valkey using the
`valkey-glide` Java client directly. Tests exercise the same commands that
`ValkeyVectorStore` uses: `FT.CREATE`, `FT.SEARCH` (KNN), `JSON.SET`, `JSON.GET`,
and `FT.INFO`.

## Quick Start

```bash
# Start Valkey with search module
docker compose up -d

# Run integration tests
mvn test

# Tear down
docker compose down -v
```

## What the Tests Validate

- Connectivity and search module availability
- JSON document storage and retrieval
- FT index creation (HNSW + FLAT, COSINE/L2/IP)
- KNN vector search with distance scoring
- TAG and NUMERIC metadata filtering
- Namespace isolation via key prefix
- Document deletion by key

## Requirements

- Java 17+
- Maven 3.9+
- Docker (for Valkey)
