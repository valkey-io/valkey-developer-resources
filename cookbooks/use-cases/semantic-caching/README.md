# Semantic Caching with Valkey

> Use Valkey's vector search to cache LLM responses by meaning — return cached answers for semantically similar prompts instead of calling the LLM again.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Build a semantic cache with FT.CREATE, HSET, and FT.SEARCH KNN. Embed prompts, cache responses, and return hits for similar queries. | Beginner, ~15 min, Python |
| 02 | <nobr>[Multi-Turn Conversation Caching](02-multiturn-caching.md)</nobr> | Cache full conversation contexts, not just single prompts. Per-user isolation with TAG filters and hybrid search. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Patterns](03-production.md)</nobr> | Threshold tuning, hit rate monitoring, TTL strategies, memory management, and cache invalidation. | Advanced, ~25 min, Python |
