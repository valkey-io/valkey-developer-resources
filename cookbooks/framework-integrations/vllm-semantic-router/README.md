# vLLM Semantic Router + Valkey

> Three cookbooks for running the vLLM Semantic Router on Valkey. Use Valkey (with the Search module) as the semantic cache, the RAG vector store, and the agentic memory backend — all through the `valkey-glide` Go client with HNSW vector indexing.

> **⚠️ Note:** These cookbooks and [sample code](sample/) demonstrate the Valkey integration patterns added to the [vLLM Semantic Router](https://github.com/vllm-project/semantic-router). The router itself is a Go service that builds Rust embedding bindings (candle) and runs alongside one or more vLLM endpoints, so the full pipeline is not validated here. The runnable Go sample exercises the same Valkey commands (`FT.CREATE`, `FT.SEARCH`, `HSET`) the router issues, against a local `valkey/valkey-bundle` instance. Content is based on the integration source in PRs [#1540](https://github.com/vllm-project/semantic-router/pull/1540), [#1671](https://github.com/vllm-project/semantic-router/pull/1671), and [#1739](https://github.com/vllm-project/semantic-router/pull/1739).

## What is vLLM Semantic Router?

The [vLLM Semantic Router](https://github.com/vllm-project/semantic-router) is a system-level intelligent router for mixture-of-models serving. It classifies incoming requests, routes them to the right model, caches semantically similar responses, retrieves documents for RAG, and remembers facts across conversations. Each of those data-plane concerns is backed by a pluggable store — and Valkey is now a first-class option for all three.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Semantic Cache Backend](01-getting-started.md)</nobr> | Configure Valkey as the semantic cache so repeated or paraphrased prompts skip the LLM. HNSW vector index, KNN lookup, TTL eviction via `valkey-glide`. | Beginner, ~15 min, Go/YAML |
| 02 | <nobr>[Vector Store Backend](02-vector-store.md)</nobr> | Use Valkey as the RAG vector store — per-collection FT indexes, KNN search with `file_id` TAG filtering, and batch chunk ingestion. | Intermediate, ~20 min, Go/YAML |
| 03 | <nobr>[Agentic Memory Backend](03-agentic-memory.md)</nobr> | Back the router's agentic memory with Valkey — per-user vector recall, hybrid reranking, access tracking, and TLS for production. | Advanced, ~20 min, Go/YAML |
