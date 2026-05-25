# Middleware Patterns

**Intermediate** · TypeScript · ~15 min

## Express Middleware

Wrap the rate limiter in reusable middleware that sets standard rate-limit headers on every response:

```typescript
import { RateLimiterValkeyGlide, RateLimiterRes } from "rate-limiter-flexible";
import type { Request, Response, NextFunction } from "express";

/** Type guard for RateLimiterRes thrown on limit exceeded. */
function isRateLimiterRes(val: unknown): val is RateLimiterRes {
  return val !== null && typeof val === "object" && "msBeforeNext" in val;
}

function rateLimitMiddleware(limiter: RateLimiterValkeyGlide) {
  return async (req: Request, res: Response, next: NextFunction) => {
    const key = req.ip ?? "unknown";
    try {
      const rlRes = await limiter.consume(key);
      setRateLimitHeaders(res, rlRes, limiter);
      next();
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) return next(rlRes);
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      setRateLimitHeaders(res, rlRes, limiter);
      res.set("Retry-After", String(Math.ceil(rlRes.msBeforeNext / 1000)));
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  };
}

function setRateLimitHeaders(
  res: Response,
  rlRes: RateLimiterRes,
  limiter: RateLimiterValkeyGlide,
) {
  res.set("X-RateLimit-Limit", String(limiter.points));
  res.set("X-RateLimit-Remaining", String(rlRes.remainingPoints));
  res.set(
    "X-RateLimit-Reset",
    String(Math.ceil((Date.now() + rlRes.msBeforeNext) / 1000)),
  );
}
```

Usage:

```typescript
import express from "express";

const app = express();

// Apply globally
app.use(rateLimitMiddleware(globalLimiter));

// Or per-route
app.get("/api/expensive", rateLimitMiddleware(strictLimiter), handler);
```

## Per-Route Limits

Different endpoints have different cost profiles. Create separate limiters:

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { RateLimiterValkeyGlide } from "rate-limiter-flexible";

const glideClient = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

// General API: 100 req/min
const generalLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 100,
  duration: 60,
  keyPrefix: "rl:general",
});

// Auth endpoints: 5 attempts/15 min (brute-force protection)
const authLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 5,
  duration: 900,
  keyPrefix: "rl:auth",
  blockDuration: 900, // Block for 15 min after exceeding
});

// LLM proxy: 20 req/min (expensive calls)
const llmLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 20,
  duration: 60,
  keyPrefix: "rl:llm",
});

app.use("/api", rateLimitMiddleware(generalLimiter));
app.post("/auth/login", rateLimitMiddleware(authLimiter), loginHandler);
app.post("/api/chat", rateLimitMiddleware(llmLimiter), chatHandler);
```

## Per-User Limits

Use authenticated user IDs instead of IP addresses for fairer limiting:

```typescript
function userRateLimitMiddleware(limiter: RateLimiterValkeyGlide) {
  return async (req: Request, res: Response, next: NextFunction) => {
    // Prefer user ID, fall back to IP
    const key = req.user?.id ?? req.ip ?? "unknown";
    try {
      const rlRes = await limiter.consume(key);
      setRateLimitHeaders(res, rlRes, limiter);
      next();
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) return next(rlRes);
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      setRateLimitHeaders(res, rlRes, limiter);
      res.set("Retry-After", String(Math.ceil(rlRes.msBeforeNext / 1000)));
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  };
}
```

## Fastify Integration

The same pattern works with Fastify using a `preHandler` hook:

```typescript
import Fastify from "fastify";
import { GlideClient } from "@valkey/valkey-glide";
import { RateLimiterValkeyGlide, RateLimiterRes } from "rate-limiter-flexible";

const fastify = Fastify();

const glideClient = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const limiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 50,
  duration: 60,
  keyPrefix: "rl:fastify",
});

fastify.addHook("preHandler", async (request, reply) => {
  try {
    const rlRes = await limiter.consume(request.ip);
    reply.header("X-RateLimit-Remaining", rlRes.remainingPoints);
  } catch (rlRes: unknown) {
    if (rlRes instanceof Error) throw rlRes;
    if (!isRateLimiterRes(rlRes)) throw rlRes;
    reply.header("Retry-After", Math.ceil(rlRes.msBeforeNext / 1000));
    reply.status(429).send({ error: "Too Many Requests" });
  }
});

fastify.get("/api/data", async () => ({ message: "OK" }));
await fastify.listen({ port: 3000 });
```

## Consuming Multiple Points

For endpoints with variable cost (e.g., batch operations), consume proportional points:

```typescript
app.post("/api/batch", async (req, res, next) => {
  const itemCount = req.body.items?.length ?? 1;
  const pointsToConsume = Math.min(itemCount, 50); // Cap at 50

  try {
    const rlRes = await generalLimiter.consume(req.ip ?? "unknown", pointsToConsume);
    setRateLimitHeaders(res, rlRes, generalLimiter);
    // Process batch...
    res.json({ processed: itemCount });
  } catch (rlRes: unknown) {
    if (rlRes instanceof Error) return next(rlRes);
    if (!isRateLimiterRes(rlRes)) throw rlRes;
    res.status(429).json({
      error: "Too Many Requests",
      retryAfterMs: rlRes.msBeforeNext,
    });
  }
});
```

---

[← 01 Getting Started](01-getting-started.md) · [Next: 03 Advanced Patterns →](03-advanced-patterns.md)
