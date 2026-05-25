/**
 * Getting Started — node-rate-limiter-flexible + Valkey
 *
 * Demonstrates basic rate limiting with RateLimiterValkeyGlide:
 * - Connect to Valkey via GLIDE
 * - Create a fixed-window rate limiter (10 req/sec)
 * - Serve a rate-limited Express endpoint
 * - Return proper rate-limit headers
 *
 * Run: npm run getting-started
 * Test: curl http://localhost:3000/api/data (repeat rapidly)
 */

import { GlideClient } from "@valkey/valkey-glide";
import { RateLimiterValkeyGlide } from "rate-limiter-flexible";
import express from "express";
import { isRateLimiterRes } from "./rate-limiter-guard.js";

const PORT = 3000;

async function main() {
  // 1. Connect to Valkey
  const glideClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });
  console.log("✅ Connected to Valkey");

  // 2. Create rate limiter: 10 requests per second per IP
  const rateLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 10,
    duration: 1,
    keyPrefix: "rl:getting-started",
  });

  // 3. Express app with rate-limited endpoint
  const app = express();

  app.get("/api/data", async (req, res) => {
    const key = req.ip ?? "unknown";
    try {
      const rlRes = await rateLimiter.consume(key);
      res.set("X-RateLimit-Limit", "10");
      res.set("X-RateLimit-Remaining", String(rlRes.remainingPoints));
      res.json({
        message: "OK",
        remainingPoints: rlRes.remainingPoints,
        consumedPoints: rlRes.consumedPoints,
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) {
        res.status(500).json({ error: rlRes.message });
        return;
      }
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      res.set("Retry-After", String(Math.ceil(rlRes.msBeforeNext / 1000)));
      res.set("X-RateLimit-Limit", "10");
      res.set("X-RateLimit-Remaining", "0");
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  });

  app.listen(PORT, () => {
    console.log(`🚀 Server listening on http://localhost:${PORT}`);
    console.log(`   Try: curl http://localhost:${PORT}/api/data`);
    console.log(`   Send 12 rapid requests to see rate limiting in action`);
  });
}

main().catch(console.error);
