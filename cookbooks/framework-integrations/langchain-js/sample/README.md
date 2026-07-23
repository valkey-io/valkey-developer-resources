# LangChain.js + Valkey Cookbook Sample

Sample project demonstrating ValkeyVectorStore patterns using `@valkey/valkey-glide`.
This project accompanies the LangChain.js + Valkey cookbook and exercises the core
vector search operations: index creation, document storage with embeddings, KNN search,
and metadata filtering.

## Prerequisites

- Node.js >= 20
- Docker & Docker Compose

## Quick Start

```bash
# Start Valkey with search module
docker compose up -d

# Install dependencies
npm install

# Run the integration tests
npm test
```

## Scripts

- `scripts/health_check.mjs` — Verify Valkey connectivity and search module availability
- `scripts/simulate_vectorstore.mjs` — End-to-end simulation of ValkeyVectorStore patterns

## Tests

Integration tests use the Node.js built-in test runner (`node:test`). They require a running Valkey instance on `localhost:6379` with the search module loaded.
