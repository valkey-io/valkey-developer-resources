# RAG Injection and Semantic Guardrails with Valkey

> Configure Kong's AI RAG Injector and Semantic Prompt/Response Guard plugins
> with Valkey as the vector database — enrich LLM prompts with context and
> filter harmful content by semantic similarity.

**Intermediate** · Docker · ~15 min

**Who is this for:** API platform engineers who want to augment their AI endpoints
with RAG (retrieval-augmented generation) and enforce content policies using semantic
similarity matching, all backed by Valkey.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Kong + Valkey running)
- Kong Gateway 3.14+ with AI plugins enabled
- [Ollama](https://ollama.com/) running locally with `nomic-embed-text`

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## AI RAG Injector

The AI RAG Injector plugin retrieves relevant context from a vector store and injects
it into the LLM prompt before forwarding the request.

### Configuration

```yaml
plugins:
  - name: ai-rag-injector
    config:
      inject_template: |
        Only use the following information surrounded by <RAG></RAG>
        and your existing knowledge to provide the best possible answer.
        <RAG><CONTEXT></RAG>
        User's question: <PROMPT>
      embeddings:
        model:
          provider: ollama
          name: nomic-embed-text
          options:
            upstream_url: http://host.docker.internal:11434/v1/embeddings
      vectordb:
        strategy: redis
        redis:
          host: valkey
          port: 6379
        distance_metric: cosine
        dimensions: 768
```

### How It Works

1. User sends a question to the Kong-proxied AI endpoint
2. Kong embeds the question using the configured embedding model
3. Kong searches Valkey for the most similar stored vectors (via `FT.SEARCH`)
4. Retrieved context documents are injected into the prompt template
5. The augmented prompt is forwarded to the LLM
6. LLM response is returned with context-grounded answers

### Populating the Vector Store

The RAG Injector reads from Valkey but doesn't write to it. You need to populate
the vector store with your documents beforehand. See the [sample scripts](sample/)
for an example of how to embed and store documents in Valkey's vector index
using the same schema Kong expects.

## AI Semantic Prompt Guard

The Prompt Guard plugin blocks or allows incoming prompts based on semantic similarity
to configured rules. Deny rules take precedence over allow rules.

### Configuration

```yaml
plugins:
  - name: ai-semantic-prompt-guard
    config:
      embeddings:
        model:
          name: nomic-embed-text
          provider: ollama
          options:
            upstream_url: http://host.docker.internal:11434/v1/embeddings
      search:
        threshold: 0.7
      vectordb:
        strategy: redis
        distance_metric: cosine
        threshold: 0.5
        dimensions: 768
        redis:
          host: valkey
          port: 6379
      rules:
        match_all_conversation_history: true
        allow_prompts:
          - Network troubleshooting and diagnostics
          - Cloud infrastructure management (AWS, Azure, GCP)
          - DevOps workflows and automation
          - Programming concepts and language usage
          - System administration and configuration
        deny_prompts:
          - Hacking techniques or penetration testing without authorization
          - Instructions on exploiting vulnerabilities or writing malware
          - Circumventing security controls or access restrictions
          - Social engineering tactics or manipulation techniques
```

### How It Works

1. Kong embeds the incoming prompt
2. Searches Valkey for similarity against the configured allow/deny rules
3. If the prompt matches a deny rule above the threshold → request is blocked (403)
4. If allow rules are configured and the prompt doesn't match any → request is blocked
5. Otherwise → request passes through to the LLM

## AI Semantic Response Guard

The Response Guard works the same way but filters LLM responses instead of prompts.

### Configuration

```yaml
plugins:
  - name: ai-semantic-response-guard
    config:
      embeddings:
        model:
          name: nomic-embed-text
          provider: ollama
          options:
            upstream_url: http://host.docker.internal:11434/v1/embeddings
      search:
        threshold: 0.7
      vectordb:
        strategy: redis
        distance_metric: cosine
        threshold: 0.7
        dimensions: 768
        redis:
          host: valkey
          port: 6379
      rules:
        allow_responses:
          - Technical documentation and explanations
          - Code examples and programming guidance
          - Infrastructure and DevOps guidance
        deny_responses:
          - Instructions for exploiting vulnerabilities
          - Content unrelated to work
          - Political or religious discussions
```

### How It Works

1. LLM generates a response
2. Kong embeds the full response
3. Searches Valkey for similarity against allow/deny response rules
4. If the response matches a deny rule → response is blocked
5. If the response doesn't match any allow rule → response is blocked
6. Otherwise → response is returned to the client

## Combining Plugins

You can stack all three plugins on the same route:

```yaml
plugins:
  - name: ai-semantic-cache        # Cache first (fastest)
  - name: ai-semantic-prompt-guard  # Block bad prompts
  - name: ai-rag-injector           # Enrich allowed prompts
  - name: ai-semantic-response-guard # Filter responses
  - name: ai-proxy                  # Forward to LLM
```

All share the same `vectordb` configuration pointing at Valkey. Kong creates
separate indices per plugin automatically.

## Threshold Tuning

| Plugin | `vectordb.threshold` | Behavior |
| --- | --- | --- |
| Semantic Cache | `0.1` | Lower = only very similar prompts hit cache |
| Prompt Guard | `0.5` | Higher = more prompts match rules (broader filtering) |
| Response Guard | `0.7` | Higher = more responses match rules |
| RAG Injector | N/A | Uses `distance_metric` for ranking, returns top-K |

For cosine distance: 0.0 = identical, 2.0 = maximally dissimilar.

## Troubleshooting

### Prompt Guard blocks everything

- Lower the `threshold` value
- Check that your `allow_prompts` list covers the intended topics broadly enough
- Verify embeddings are working (check Kong error logs for embedding API failures)

### RAG Injector returns no context

- Ensure you've populated the vector store with documents
- Check the index exists: `docker exec kong-valkey valkey-cli FT._LIST`
- Verify dimensions match between the stored vectors and the embedding model

### Response Guard doesn't block harmful content

- Increase the `search.threshold` value
- Make deny rules more specific to the content you want to block
- Check that the embedding model produces vectors in the configured dimensions

---

[→ Next: Semantic Routing](03-semantic-routing.md) · [← Back to Getting Started](01-getting-started.md)
