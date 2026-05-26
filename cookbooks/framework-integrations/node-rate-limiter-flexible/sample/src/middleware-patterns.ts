/**
 * Middleware Patterns — node-rate-limiter-flexible + Valkey
 *
 * Demonstrates production middleware patterns:
 * - Reusable Express rate-limit middleware with standard headers
 * - Per-route limiters (general, auth, LLM)
 * - Per-user keying (user ID vs IP)
 * - Variable-cost batch endpoint
 *
 * Run: npm run middleware
 * Test:
 *   curl http://localhost:3001/api/data
 *   curl -X POST http://localhost:3001/auth/login
 *   curl -X POST http://localhost:3001/api/chat
 *   curl -X POST -H "Content-Type: application/json" \
 *     -d '{"items":["a","b","c"]}' http://localhost:3001/api/batch
 */

import { GlideClient } from "@valkey/valkey-glide";
import {
  RateLimiterValkeyGlide,
  RateLimiterRes,
} from "rate-limiter-flexible";
import express, { Request, Response, NextFunction } from "express";
import { isRateLimiterRes } from "./rate-limiter-guard.js";

const PORT = 3001;

/** Set standard rate-limit response headers. */
function setRateLimitHeaders(
  res: Response,
  rlRes: RateLimiterRes,
  limiter: RateLimiterValkeyGlide,
): void {
  res.set("X-RateLimit-Limit", String(limiter.points));
  res.set("X-RateLimit-Remaining", String(rlRes.remainingPoints));
  res.set(
    "X-RateLimit-Reset",
    String(Math.ceil((Date.now() + rlRes.msBeforeNext) / 1000)),
  );
}

/** Create reusable rate-limit middleware for a given limiter. */
function rateLimitMiddleware(
  limiter: RateLimiterValkeyGlide,
  // Behind a reverse proxy? Configure: app.set('trust proxy', 1)
  // so req.ip reflects the real client IP. See Express docs on trust proxy.
  keyFn: (req: Request) => string = (req) => req.ip ?? "unknown",
) {
  return async (req: Request, res: Response, next: NextFunction) => {
    const key = keyFn(req);
    try {
      const rlRes = await limiter.consume(key);
      setRateLimitHeaders(res, rlRes, limiter);
      next();
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) return next(rlRes);
      if (!isRateLimiterRes(rlRes)) return next(new Error(`Unexpected rate limiter rejection: ${String(rlRes)}`));
      setRateLimitHeaders(res, rlRes, limiter);
      res.set("Retry-After", String(Math.ceil(rlRes.msBeforeNext / 1000)));
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  };
}

async function main() {
  const glideClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });
  console.log("✅ Connected to Valkey");

  // Per-route limiters with different thresholds
  const generalLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 100,
    duration: 60,
    keyPrefix: "rl:general",
  });

  const authLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 5,
    duration: 900, // 15 minutes
    keyPrefix: "rl:auth",
    blockDuration: 900, // Block for 15 min after exceeding
  });

  const llmLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 20,
    duration: 60,
    keyPrefix: "rl:llm",
  });

  const batchLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 100,
    duration: 60,
    keyPrefix: "rl:batch",
  });

  const app = express();
  app.use(express.json());

  // General API rate limit (applies to all /api/* routes as a global safety net)
  app.use("/api", rateLimitMiddleware(generalLimiter));

  app.get("/api/data", (_req, res) => {
    res.json({ message: "General API response" });
  });

  // Auth endpoint — strict brute-force protection
  app.post("/auth/login", rateLimitMiddleware(authLimiter), (_req, res) => {
    res.json({ message: "Login attempt accepted (demo)" });
  });

  // LLM proxy — expensive calls, tighter limit
  // NOTE: /api/chat is intentionally double-limited — general (100/min) + LLM-specific (20/min).
  // The general limiter acts as a global safety net across all /api/* routes.
  app.post("/api/chat", rateLimitMiddleware(llmLimiter), (_req, res) => {
    res.json({ message: "Chat response (demo)", model: "gpt-4" });
  });

  // Batch endpoint — variable cost based on item count
  app.post("/api/batch", async (req, res, next) => {
    const items: unknown[] = req.body?.items ?? [];
    const pointsToConsume = Math.min(items.length || 1, 50);
    const key = req.ip ?? "unknown";

    try {
      const rlRes = await batchLimiter.consume(key, pointsToConsume);
      setRateLimitHeaders(res, rlRes, batchLimiter);
      res.json({
        message: `Processed ${items.length} items (cost: ${pointsToConsume} points)`,
        remainingPoints: rlRes.remainingPoints,
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) return next(rlRes);
      if (!isRateLimiterRes(rlRes)) return next(new Error(`Unexpected rate limiter rejection: ${String(rlRes)}`));
      setRateLimitHeaders(res, rlRes, batchLimiter);
      res.set("Retry-After", String(Math.ceil(rlRes.msBeforeNext / 1000)));
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  });

  app.listen(PORT, () => {
    console.log(`🚀 Server listening on http://localhost:${PORT}`);
    console.log(`   Routes:`);
    console.log(`     GET  /api/data    — 100 req/min`);
    console.log(`     POST /auth/login  — 5 attempts/15 min (blocks on exceed)`);
    console.log(`     POST /api/chat    — 20 req/min`);
    console.log(`     POST /api/batch   — 100 points/min (variable cost)`);
  });
}

main().catch(console.error);
