# vLLM Semantic Router + Valkey

> Configure the released vLLM Semantic Router service to use Valkey and call it from Go over its public HTTP API.

vLLM Semantic Router owns routing, embeddings, cache decisions, and storage operations. Valkey is its configured
semantic-cache backend. The Go sample is intentionally only an OpenAI-compatible client:

```text
Go client -> vLLM Semantic Router -> Valkey
```

This cookbook targets [vLLM Semantic Router v0.3.0](https://github.com/vllm-project/semantic-router/tree/v0.3.0),
the released version that contains Valkey semantic-cache, vector-store, and memory backends. It does not import
Semantic Router internals or recreate search indexes in application code. v0.3.0 does not publish a supported Go
SDK; its supported public interface is the `vllm-sr` service and OpenAI-compatible HTTP API used by this sample.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Semantic Cache](01-getting-started.md)</nobr> | Run the Router with its Valkey semantic cache and verify a routed cache hit. | Beginner, ~20 min, Go |
| 02 | <nobr>[Vector Store Configuration](02-vector-store.md)</nobr> | Configure the Router's Valkey vector-store backend. | Intermediate, ~10 min, Go |
| 03 | <nobr>[Agentic Memory Configuration](03-agentic-memory.md)</nobr> | Configure the Router's Valkey memory backend. | Advanced, ~10 min, Go |
