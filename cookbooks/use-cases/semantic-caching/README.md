# Semantic Caching

> Cache LLM responses by meaning, not exact match. Cut API costs by 60%+ and slash latency from seconds to milliseconds using vector similarity with the valkey-search module.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Build a semantic cache with FT.CREATE, HSET, and FT.SEARCH KNN. Embed prompts, cache responses, and return hits for similar queries. | Beginner, ~15 min, Python |
| 02 | <nobr>[Multi-Turn Conversation Caching](02-multiturn-caching.md)</nobr> | Cache full conversation contexts, not just single prompts. Per-user isolation with TAG filters and hybrid search. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Patterns](03-production.md)</nobr> | Threshold tuning, hit rate monitoring, TTL strategies, memory management, cache invalidation, and cost tracking. | Advanced, ~25 min, Python |

