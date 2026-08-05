# Kong AI Gateway + Valkey Cookbook

> Use Valkey as the vector database backend for Kong AI Gateway's semantic plugins —
> caching, RAG injection, prompt/response guardrails, and semantic load balancing —
> with zero configuration changes beyond pointing `vectordb.redis.host` at Valkey.

## Cookbooks

| # | Title | Description | Level |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Set up Kong AI Gateway with Valkey for semantic caching. | Beginner, ~15 min, Docker |
| 02 | <nobr>[RAG and Guardrails](02-rag-and-guardrails.md)</nobr> | Configure RAG injection and semantic prompt/response guards with Valkey. | Intermediate, ~15 min, Docker |
| 03 | <nobr>[Semantic Routing](03-semantic-routing.md)</nobr> | Route requests to models by semantic similarity using Valkey. | Intermediate, ~10 min, Docker |

## Prerequisites

- Docker and Docker Compose
- Kong Gateway 3.14+ (Enterprise or Free tier with AI Gateway plugins)
- Valkey 8.x+ with valkey-search module (`valkey/valkey-bundle`)
- [Ollama](https://ollama.com/) running locally with an embedding model (or OpenAI API key)

## How Kong AI Gateway Uses Valkey

Kong's AI Gateway plugins use Valkey as a vector database through the `redis` strategy.
When you configure `vectordb.strategy: redis`, Kong queries the backend server's `INFO`
response. If it detects a Valkey server name, it automatically uses the Valkey-specific
driver — no extra configuration needed.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Kong AI Gateway (3.14+)                          │
├──────────────────┬─────────────────┬───────────────────┬────────────────┤
│  AI Semantic     │  AI RAG         │  AI Semantic      │  AI Proxy      │
│  Cache           │  Injector       │  Prompt/Response  │  Advanced      │
│  ──────────────  │  ─────────────  │  Guard            │  (Semantic LB) │
│  cache LLM       │  inject context │  ───────────────  │  ────────────  │
│  responses by    │  from vector    │  allow/deny by    │  route to      │
│  semantic sim.   │  store          │  semantic match   │  best model    │
└────────┬─────────┴────────┬────────┴─────────┬─────────┴────────┬───────┘
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                     │
                          vectordb.strategy: redis
                          (auto-detects Valkey)
                                     │
                                     ▼
                             ┌──────────────┐
                             │    Valkey     │
                             │  (FT.CREATE   │
                             │   FT.SEARCH)  │
                             └──────────────┘
```

All five AI plugins share the same vectordb configuration block:

```yaml
vectordb:
  strategy: redis       # Kong auto-detects Valkey via server INFO
  dimensions: 3072      # Must match your embedding model
  distance_metric: cosine
  threshold: 0.1        # Similarity threshold (lower = more similar for cosine)
  redis:
    host: valkey-server
    port: 6379
```

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

  kong:
    image: kong/kong-gateway:3.14
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      valkey:
        condition: service_healthy
```

## Upstream Status

> **Note:** [Kong/developer.konghq.com#4710](https://github.com/Kong/developer.konghq.com/pull/4710)
> has been **merged**. Valkey vector DB support is available in Kong Gateway 3.14+.
> Kong auto-detects Valkey when using `vectordb.strategy: redis` — no separate strategy needed.

## References

- [Kong AI Gateway - Semantic Similarity](https://developer.konghq.com/ai-gateway/semantic-similarity/)
- [AI Semantic Cache Plugin](https://developer.konghq.com/plugins/ai-semantic-cache/)
- [AI RAG Injector Plugin](https://developer.konghq.com/plugins/ai-rag-injector/)
- [AI Semantic Prompt Guard Plugin](https://developer.konghq.com/plugins/ai-semantic-prompt-guard/)
- [AI Semantic Response Guard Plugin](https://developer.konghq.com/plugins/ai-semantic-response-guard/)
- [AI Proxy Advanced Plugin](https://developer.konghq.com/plugins/ai-proxy-advanced/)
- [Valkey Search Documentation](https://valkey.io/topics/search/)

---

[← Back to Valkey Samples](../../../README.md)
