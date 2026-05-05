# @betterdb/agent-cache

> 4 cookbooks for multi-tier AI agent caching. LLM responses, tool results, and session state behind one connection - on vanilla Valkey 7+, no modules required.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install on vanilla Valkey 7+, create an AgentCache, and use all three tiers: LLM cache, tool cache, and session store. | Beginner, ~15 min, TypeScript |
| 02 | <nobr>[LLM & Tool Cache](02-llm-and-tool-cache.md)</nobr> | Exact-match LLM response caching with cost tracking. Per-tool TTL policies. toolEffectiveness() recommendations for self-tuning caches. | Intermediate, ~20 min, TypeScript |
| 03 | <nobr>[Agent Session Store](03-session-store.md)</nobr> | Per-field TTL, sliding-window refresh, and atomic state updates for multi-step agents. Store intent, reasoning chains, and extracted entities. | Intermediate, ~20 min, TypeScript |
| 04 | <nobr>[LangGraph Checkpointing](04-langgraph.md)</nobr> | BetterDBSaver persists LangGraph graph state on vanilla Valkey 7+ - no Redis 8, no RedisJSON, no RediSearch. Combine with LLM and tool caching for full-stack agent optimization. | Advanced, ~25 min, TypeScript |

