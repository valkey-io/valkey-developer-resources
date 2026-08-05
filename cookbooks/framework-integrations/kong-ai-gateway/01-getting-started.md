# Getting Started with Kong AI Gateway and Valkey

> Set up Kong AI Gateway with Valkey as the vector database for semantic caching —
> cache LLM responses by meaning so similar questions get instant answers.

**Beginner** · Docker · ~15 min

**Who is this for:** API platform engineers using Kong Gateway who want to add
semantic caching to their AI endpoints, reducing LLM costs and latency by serving
cached responses for semantically similar requests.

## Prerequisites

- Docker and Docker Compose
- Kong Gateway 3.14+ license or Free tier
- [Ollama](https://ollama.com/) running locally with `nomic-embed-text` and a chat model (e.g., `llama3.2`)
- Valkey 8.x+ with search module (`valkey/valkey-bundle`)

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Step 1: Create the Docker Compose File

```yaml
# docker-compose.yml
services:
  valkey:
    image: valkey/valkey-bundle:9.1.0
    container_name: kong-valkey
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  kong:
    image: kong/kong-gateway:3.14
    container_name: kong-gateway
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
    ports:
      - "127.0.0.1:8000:8000"
      - "127.0.0.1:8001:8001"
    volumes:
      - ./kong.yml:/kong/kong.yml:ro
    depends_on:
      valkey:
        condition: service_healthy
```

## Step 2: Create the Kong Declarative Configuration

```yaml
# kong.yml
_format_version: "3.0"

services:
  - name: ollama
    url: http://host.docker.internal:11434
    routes:
      - name: ollama-chat
        paths:
          - /ai
        strip_path: true

plugins:
  - name: ai-proxy
    config:
      route_type: llm/v1/chat
      model:
        provider: ollama
        name: llama3.2
        options:
          upstream_url: http://host.docker.internal:11434/v1/chat/completions

  - name: ai-semantic-cache
    config:
      embeddings:
        model:
          provider: ollama
          name: nomic-embed-text
          options:
            upstream_url: http://host.docker.internal:11434/v1/embeddings
      vectordb:
        dimensions: 768
        distance_metric: cosine
        strategy: redis
        threshold: 0.1
        redis:
          host: valkey
          port: 6379
```

<details>
<summary>Optional: Using OpenAI instead of Ollama</summary>

Replace the `kong.yml` above with this configuration if you prefer to use OpenAI
(requires a paid API key set as `OPENAI_API_KEY`):

```yaml
# kong.yml (OpenAI variant)
_format_version: "3.0"

services:
  - name: openai
    url: https://api.openai.com
    routes:
      - name: openai-chat
        paths:
          - /ai
        strip_path: true

plugins:
  - name: ai-proxy
    config:
      route_type: llm/v1/chat
      auth:
        header_name: Authorization
        header_value: "Bearer ${OPENAI_API_KEY}"
      model:
        provider: openai
        name: gpt-4o-mini

  - name: ai-semantic-cache
    config:
      embeddings:
        auth:
          header_name: Authorization
          header_value: "Bearer ${OPENAI_API_KEY}"
        model:
          provider: openai
          name: text-embedding-3-large
          options:
            upstream_url: https://api.openai.com/v1/embeddings
      vectordb:
        dimensions: 3072
        distance_metric: cosine
        strategy: redis
        threshold: 0.1
        redis:
          host: valkey
          port: 6379
```

</details>

## Step 3: Start the Services

```bash
docker compose up -d
```

Verify:

```bash
docker compose ps
# Both kong-valkey (healthy) and kong-gateway (running) should appear
```

## Step 4: Verify Valkey Search Module

```bash
docker exec kong-valkey valkey-cli MODULE LIST
```

Confirm `search` appears in the output.

## Step 5: Test Semantic Caching

Send a request to the AI proxy:

```bash
curl -s http://localhost:8000/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is Valkey?"}]
  }' | jq .choices[0].message.content
```

Send a semantically similar request:

```bash
curl -s http://localhost:8000/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Can you explain what Valkey is?"}]
  }' | jq .choices[0].message.content
```

The second request should return faster (cached) if it's semantically similar enough
(within the `threshold: 0.1` cosine distance).

## Step 6: Verify Vectors in Valkey

```bash
# Check that Kong created a vector index
docker exec kong-valkey valkey-cli FT._LIST

# See how many cached entries exist
docker exec kong-valkey valkey-cli FT.SEARCH <index-name> "*" LIMIT 0 0
```

## How Auto-Detection Works

Kong's AI plugins use the `redis` vectordb strategy for both Redis and Valkey.
At startup, Kong:

1. Connects to the configured `redis.host:port`
2. Runs `INFO server` and checks the `server_name` field
3. If `server_name` is `valkey`, it uses the Valkey-specific vector search driver
4. If `server_name` is `redis`, it uses the Redis Stack VSS driver

This means you can switch from Redis to Valkey by just changing the hostname — no
strategy or plugin configuration changes needed.

## Configuration Reference

| Parameter | Description |
| --- | --- |
| `vectordb.strategy` | Always `redis` (Valkey is auto-detected) |
| `vectordb.dimensions` | Must match embedding model output (3072 for `text-embedding-3-large`) |
| `vectordb.distance_metric` | `cosine` (recommended), `l2`, or `ip` |
| `vectordb.threshold` | Similarity threshold; lower = stricter match for cosine |
| `vectordb.redis.host` | Valkey hostname |
| `vectordb.redis.port` | Valkey port (default 6379) |
| `embeddings.model.provider` | `ollama`, `openai`, `azure`, etc. |
| `embeddings.model.name` | Model name (e.g., `text-embedding-3-large`, `text-embedding-3-small`) |

## Embedding Model Dimensions

| Model | Dimensions | Notes |
| --- | --- | --- |
| `text-embedding-3-large` | 3072 | Recommended, highest quality |
| `text-embedding-3-small` | 1536 | Good balance of quality/cost, supports dynamic dims |
| `text-embedding-ada-002` | 1536 | Legacy, must set dimensions to exactly 1536 |

## Troubleshooting

### Kong logs: "Failed to connect to vector database"

- Verify Valkey is running: `docker exec kong-valkey valkey-cli ping`
- Check `redis.host` matches the Docker service name (`valkey` inside the network)
- Ensure port 6379 is not blocked

### Cache never hits (always calls LLM)

- Lower the `threshold` value (e.g., 0.05 for stricter matching)
- Verify embeddings are being generated (check Kong logs for embedding API calls)
- Confirm the search module is loaded: `docker exec kong-valkey valkey-cli MODULE LIST`

### "Dimensions mismatch" error

- The `vectordb.dimensions` must exactly match what the embedding model produces
- `text-embedding-3-large` = 3072, `text-embedding-ada-002` = 1536

---

[→ Next: RAG and Guardrails](02-rag-and-guardrails.md) · [← Back to README](README.md)
