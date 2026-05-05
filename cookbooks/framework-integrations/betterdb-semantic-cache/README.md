# @betterdb/semantic-cache

> 3 cookbooks for the first Valkey-native semantic cache. Standalone, framework-agnostic, with built-in OpenTelemetry and Prometheus metrics at the cache-operation level.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install, connect to Valkey, write an embed function, and serve semantically similar prompts from cache - no LLM call needed. | Beginner, ~15 min, TypeScript |
| 02 | <nobr>[LangChain & Vercel AI Adapters](02-adapters.md)</nobr> | Drop-in caching for LangChain ChatModels via BetterDBSemanticCache, and for Vercel AI SDK models via createSemanticCacheMiddleware. | Intermediate, ~20 min, TypeScript |
| 03 | <nobr>[Production Patterns](03-production.md)</nobr> | Threshold tuning, uncertain hit strategies, per-category overrides, TTL management, invalidation, and Prometheus metrics dashboards. | Advanced, ~20 min, TypeScript |

