# Rate Limiting with Valkey

> Production-ready rate limiting patterns for AI workloads — from basic fixed windows to enterprise hierarchical limits and cost-based budgets.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey, build a fixed-window limiter, then add token-aware and dual limiting for AI workloads. | Beginner, ~15 min, Python |
| 02 | <nobr>[Agent and Hierarchical Limiting](02-agent-hierarchical.md)</nobr> | Per-agent token buckets with Lua scripts, tool-weighted costs, concurrent slots, and cascading Org→Team→User→Agent checks. | Intermediate, ~25 min, Python |
| 03 | <nobr>[Production Patterns](03-production.md)</nobr> | Dollar-budget limits, model downgrades, Retry-After headers, circuit breakers, graceful degradation, and request queuing. | Advanced, ~30 min, Python |
