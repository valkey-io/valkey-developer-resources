# Open WebUI + Valkey Cookbook

> Use Valkey as the vector database backend for Open WebUI's RAG pipeline — store
> document embeddings, perform KNN similarity search, and filter by metadata with
> zero external vector DB dependencies.

## Cookbooks

| # | Title | Description | Level |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Configure Open WebUI with `VECTOR_DB=valkey` and ingest your first documents. | Beginner, ~10 min, Docker |
| 02 | <nobr>[RAG Configuration](02-rag-configuration.md)</nobr> | Tune HNSW parameters, distance metrics, and collection management for RAG. | Intermediate, ~15 min, Docker |
| 03 | <nobr>[Production Deployment](03-production-deployment.md)</nobr> | Deploy Open WebUI + Valkey with TLS, persistence, monitoring, and scaling. | Intermediate, ~20 min, Docker |

## Prerequisites

- Docker and Docker Compose
- Valkey 9.0.1+ with valkey-search module 1.2.0+ (`valkey/valkey-bundle:9.1.0`)
- Open WebUI (latest from `main` branch, post-merge of PR #24769)
- An LLM backend (Ollama, OpenAI, or other OpenAI-compatible API)

## How Open WebUI Uses Valkey

Open WebUI's RAG pipeline uses Valkey as a vector store via `valkey-glide-sync`:

- **HASH document storage** — Each document chunk is stored as a Valkey HASH with
  `vector` (FLOAT32 bytes), `text`, `metadata_json`, and TAG fields (`id`, `hash`,
  `file_id`, `source`, `knowledge_base_id`)
- **HNSW/FLAT indexing** — `FT.CREATE` with configurable algorithm and distance metric
- **KNN search** — `FT.SEARCH` with `*=>[KNN k @vector $query_vec]` syntax
- **Metadata filtering** — TAG field filters for scoped retrieval (`@file_id:{...}`)
- **Collection isolation** — Prefix-based key namespacing (`{prefix}:{collection}:{id}`)
- **Startup validation** — Checks Valkey core version and search module version at boot

## Quick Start

```yaml
# docker-compose.yml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "127.0.0.1:3000:8080"
    environment:
      - VECTOR_DB=valkey
      - VALKEY_URL=valkey://valkey:6379
    depends_on:
      valkey:
        condition: service_healthy
```

```bash
docker compose up -d
# Open http://localhost:3000 and upload a document — it's automatically embedded and stored in Valkey
```

## Upstream Status

> **Note:** [open-webui/open-webui#24769](https://github.com/open-webui/open-webui/pull/24769)
> has been **merged**. Valkey vector DB support is available in Open WebUI builds from the
> `main` branch. Uses `valkey-glide-sync==2.3.1` and requires `valkey-search` 1.2.0+.

## References

- [Open WebUI Documentation](https://docs.openwebui.com/)
- [Valkey Search Commands](https://github.com/valkey-io/valkey-search/blob/main/COMMANDS.md)
- [Valkey GLIDE Python Client](https://github.com/valkey-io/valkey-glide)
- [PR #24769 — Add Valkey vector database support](https://github.com/open-webui/open-webui/pull/24769)

---

[← Back to Valkey Samples](../../../README.md)
