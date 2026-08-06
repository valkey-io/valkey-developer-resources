# Semantic Routing with Kong AI Proxy Advanced and Valkey

> Route incoming requests to the most appropriate LLM model based on semantic
> similarity — use Valkey to match request content against model descriptions
> and direct traffic to specialized models.

**Intermediate** · Docker · ~10 min

**Who is this for:** Teams running multiple LLM models (e.g., specialized for code,
support, general queries) who want Kong to automatically route requests to the best
model based on what the user is asking about.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Kong + Valkey running)
- Kong Gateway 3.14+ with AI Proxy Advanced plugin
- [Ollama](https://ollama.com/) running locally with `nomic-embed-text` and `llama3.2`

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## How Semantic Routing Works

Instead of routing by URL path or header, semantic routing embeds the incoming
request and compares it against model descriptions stored in Valkey. The request
goes to whichever model's description is most similar.

```text
┌────────────────┐        ┌──────────────────┐        ┌────────────────┐
│  "Fix my      │        │ Kong AI Proxy    │        │ llama3.2       │
│   Python code"│───────▶│ Advanced         │──┐     │ (Code Expert)  │
└────────────────┘        │                  │  │     └────────────────┘
                          │  1. Embed prompt │  │
                          │  2. FT.SEARCH    │  ├────▶┌────────────────┐
                          │     Valkey       │  │     │ llama3.2       │
                          │  3. Best match   │  │     │ (IT Support)   │
                          │     → route      │  │     └────────────────┘
                          └──────────────────┘  │
                                                └────▶┌────────────────┐
                                                      │ llama3.2       │
                                                      │ (Catch-all)    │
                                                      └────────────────┘
```

## Configuration

```yaml
plugins:
  - name: ai-proxy-advanced
    config:
      embeddings:
        model:
          name: nomic-embed-text
          provider: ollama
          options:
            upstream_url: http://host.docker.internal:11434/v1/embeddings
      vectordb:
        dimensions: 768
        distance_metric: cosine
        strategy: redis
        threshold: 0.7
        redis:
          host: valkey
          port: 6379
      balancer:
        algorithm: semantic
      targets:
        - model:
            name: llama3.2
            provider: ollama
            options:
              max_tokens: 826
              temperature: 0
              upstream_url: http://host.docker.internal:11434/v1/chat/completions
          route_type: llm/v1/chat
          description: "Specialist in code completions"
        - model:
            name: llama3.2
            provider: ollama
            options:
              max_tokens: 512
              temperature: 0.3
              upstream_url: http://host.docker.internal:11434/v1/chat/completions
          route_type: llm/v1/chat
          description: "Requests related to IT support"
        - model:
            name: llama3.2
            provider: ollama
            options:
              max_tokens: 256
              temperature: 1.0
              upstream_url: http://host.docker.internal:11434/v1/chat/completions
          route_type: llm/v1/chat
          description: "CATCHALL"
```

> **Note:** With a single local Ollama instance, all targets use the same model but with
> different parameters (temperature, max_tokens). In production with multiple models, you
> would use different `name` values pointing to specialized models.

<details>
<summary>Optional: Using OpenAI models for semantic routing</summary>

Replace the targets with OpenAI models for differentiated routing to specialized models:

```yaml
      targets:
        - model:
            name: gpt-3.5-turbo
            provider: openai
            options:
              max_tokens: 826
              temperature: 0
          route_type: llm/v1/chat
          auth:
            header_name: Authorization
            header_value: "Bearer ${OPENAI_API_KEY}"
          description: "Specialist in code completions"
        - model:
            name: gpt-4o
            provider: openai
          # ... (full config with auth for each target)
```

This requires `OPENAI_API_KEY` set as an environment variable.

</details>

## How Targets Are Matched

1. Kong embeds each target's `description` field and stores the embeddings in Valkey
2. When a request arrives, Kong embeds the prompt content
3. `FT.SEARCH` performs a KNN query against the stored description embeddings
4. The target with the highest similarity score (below `threshold`) gets the request
5. If no target exceeds the threshold, the `CATCHALL` target handles it

The `CATCHALL` description is a special marker — it receives requests that don't
match any other target well enough.

## Testing Semantic Routing

```bash
# Should route to code specialist target (llama3.2 with temp=0, max_tokens=826)
curl -s http://localhost:8000/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a Python function to sort a list"}]
  }' | jq .model
# Returns "llama3.2" — verify routing by checking response parameters

# Should route to IT support target (llama3.2 with temp=0.3, max_tokens=512)
curl -s http://localhost:8000/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "My VPN connection keeps dropping"}]
  }' | jq .model

# Should route to catch-all target (llama3.2 with temp=1.0, max_tokens=256)
curl -s http://localhost:8000/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the meaning of life?"}]
  }' | jq .model
```

> **Note:** With the default Ollama configuration, all targets use `llama3.2` so
> `.model` will always return `"llama3.2"`. Routing is differentiated by parameters
> (temperature, max_tokens). Use Kong debug logs or the OpenAI variant to observe
> which target was selected.

## Tuning Routing Accuracy

### Threshold

The `vectordb.threshold` controls how similar a prompt must be to a description
to be considered a match. For cosine distance:

- `0.5` — loose matching, more requests hit specialized models
- `0.7` — moderate, good starting point
- `0.9` — strict, only very similar prompts match (most go to catch-all)

### Descriptions

Write clear, distinct descriptions for each target:

- **Good:** "Specialist in Python, JavaScript, and SQL code generation and debugging"
- **Bad:** "General purpose AI model" (too vague, will match everything)

More specific descriptions produce better vector separations in Valkey.

### Embedding Model

The default configuration uses `nomic-embed-text` (768 dimensions) via Ollama —
it's free, fast, and runs locally. For production with OpenAI, use
`text-embedding-3-small` (1536 dimensions) for routing — it's fast and cheap since
every request needs an embedding. Reserve `text-embedding-3-large` (3072 dims) for
RAG and caching where accuracy matters more than latency.

## Combining with Other Plugins

Semantic routing works alongside the other AI plugins:

```yaml
plugins:
  - name: ai-semantic-cache         # Check cache first
  - name: ai-semantic-prompt-guard   # Block bad prompts
  - name: ai-proxy-advanced          # Semantic routing to best model
  - name: ai-semantic-response-guard # Filter responses
```

All share the same Valkey instance. Kong creates separate indices per plugin.

## Troubleshooting

### All requests go to the catch-all model

- Lower `vectordb.threshold` (e.g., 0.5)
- Make target descriptions more distinct and specific
- Check embeddings are working (look for embedding API errors in Kong logs)

### Wrong model selected

- Improve the target `description` to better characterize the model's specialty
- Avoid overlapping descriptions between targets
- Consider using a higher-quality embedding model

### Slow routing (high latency on first request)

On first request, Kong embeds all target descriptions and stores them in Valkey.
Subsequent requests only need to embed the incoming prompt (one embedding call)
and search Valkey (one `FT.SEARCH`). The first-request latency is a one-time cost.

---

[← Back to RAG and Guardrails](02-rag-and-guardrails.md) · [← Back to README](README.md)
