# node-rate-limiter-flexible + Valkey

> 3 cookbooks for production-grade distributed rate limiting in Node.js using `rate-limiter-flexible` with Valkey as the backing store via `@valkey/valkey-glide`.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install deps, start Valkey, configure `RateLimiterValkeyGlide`, and rate-limit your first Express endpoint in under 10 minutes. | Beginner, ~10 min, TypeScript |
| 02 | <nobr>[Middleware Patterns](02-middleware-patterns.md)</nobr> | Express and Fastify middleware, `Retry-After` headers, per-route limits, per-user limits, and proper 429 responses. | Intermediate, ~15 min, TypeScript |
| 03 | <nobr>[Advanced Patterns](03-advanced-patterns.md)</nobr> | Insurance strategy (failover to in-memory), in-memory block strategy, token-aware AI workload limiting, and Valkey cluster mode. | Advanced, ~20 min, TypeScript |
