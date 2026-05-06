# Token-Aware Rate Limiting

> Token-aware, cost-based, and hierarchical rate limiting for production AI workloads. Protect your APIs, control spend, and keep your LLM integrations reliable.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey, install deps, and build your first token-aware rate limiter in under 5 minutes. | Beginner, ~5 min, Python |
| 02 | <nobr>[Token-Aware Limiting](02-token-aware.md)</nobr> | Count LLM tokens, not just requests. Dual limiting, output estimation, and post-call adjustment. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Agent Rate Limiting](03-agent-limiting.md)</nobr> | Per-agent limits with token bucket, tool-weighted costs, concurrent agent slots, and budget tracking. | Intermediate, ~20 min, Python |
| 04 | <nobr>[Hierarchical Limits](04-hierarchical.md)</nobr> | Cascading Org → Team → User → Agent → Model limits. All tiers checked in a single Valkey pipeline. | Advanced, ~25 min, Python |
| 05 | <nobr>[Cost-Based Limiting](05-cost-based.md)</nobr> | Dollar-amount budgets per window. Model-aware pricing, automatic downgrades, and spend tracking. | Advanced, ~20 min, Python |
| 06 | <nobr>[Production Patterns](06-production.md)</nobr> | Retry-After headers, circuit breakers, graceful degradation, request queuing, and observability. | Advanced, ~30 min, Python |

