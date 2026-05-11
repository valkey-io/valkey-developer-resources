# Agent SessionState

> Persist tool calls, reasoning chains, and intermediate results for multi-step AI agents with atomic operations. Low-latency state management that scales.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 03 | <nobr>[Agent Session Store](../../framework-integrations/betterdb-agent-cache/03-session-store.md)</nobr> | Per-field TTL, sliding-window refresh, and atomic state updates. Store intent, reasoning chains, and extracted entities across invocations. | Intermediate, TypeScript, @betterdb/agent-cache |
| 04 | <nobr>[LangGraph Checkpointing](../../framework-integrations/betterdb-agent-cache/04-langgraph.md)</nobr> | BetterDBSaver persists LangGraph graph state on vanilla Valkey 7+ - no Redis 8, no RedisJSON, no modules required. | Advanced, TypeScript, @betterdb/agent-cache |

