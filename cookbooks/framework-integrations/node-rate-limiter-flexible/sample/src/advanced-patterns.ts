/**
 * Advanced Patterns — node-rate-limiter-flexible + Valkey
 *
 * Demonstrates production-grade patterns:
 * - Insurance strategy (automatic failover to in-memory)
 * - In-memory block strategy (zero-network rejection for abusers)
 * - Token-aware rate limiting for AI/LLM workloads
 * - Dynamic block escalation for repeat offenders
 *
 * Run: npm run advanced
 * Test:
 *   curl http://localhost:3002/api/insured
 *   curl -X POST -H "Content-Type: application/json" \
 *     -d '{"prompt":"Hello world","userId":"user-1"}' \
 *     http://localhost:3002/api/token-limit
 *   curl http://localhost:3002/api/escalating
 */

import { GlideClient } from "@valkey/valkey-glide";
import {
  RateLimiterValkeyGlide,
  RateLimiterMemory,
  RateLimiterRes,
} from "rate-limiter-flexible";
import express from "express";
import { isRateLimiterRes } from "./rate-limiter-guard.js";

const PORT = 3002;

async function main() {
  const glideClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });
  console.log("✅ Connected to Valkey");

  // --- Pattern 1: Insurance Strategy ---
  // Falls back to in-memory if Valkey is unreachable
  const insuranceLimiter = new RateLimiterMemory({
    points: 150, // Slightly more permissive (can't share state across instances)
    duration: 60,
  });

  const insuredLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 100,
    duration: 60,
    keyPrefix: "rl:insured",
    insuranceLimiter,
  });

  // --- Pattern 2: In-Memory Block Strategy ---
  // After exceeding limit, block in-memory for 30s (zero network calls)
  const blockLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 5,
    duration: 10,
    keyPrefix: "rl:block",
    inMemoryBlockOnConsumed: 5,
    inMemoryBlockDuration: 30,
  });

  // --- Pattern 3: Token-Aware Limiting ---
  // Budget: 10,000 tokens per minute per user
  const tokenLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 10_000,
    duration: 60,
    keyPrefix: "rl:tokens",
  });

  // --- Pattern 4: Escalating Block ---
  const escalatingLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 5,
    duration: 60,
    keyPrefix: "rl:escalate",
  });

  const app = express();
  app.use(express.json());

  // Pattern 1: Insured endpoint — works even if Valkey goes down
  app.get("/api/insured", async (req, res) => {
    const key = req.ip ?? "unknown";
    try {
      const rlRes = await insuredLimiter.consume(key);
      res.json({
        message: "OK (insured endpoint)",
        remainingPoints: rlRes.remainingPoints,
        note: "This endpoint falls back to in-memory limiting if Valkey is down",
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) {
        res.status(500).json({ error: rlRes.message });
        return;
      }
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: rlRes.msBeforeNext,
      });
    }
  });

  // Pattern 2: Block strategy endpoint
  app.get("/api/blocked", async (req, res) => {
    const key = req.ip ?? "unknown";
    try {
      const rlRes = await blockLimiter.consume(key);
      res.json({
        message: "OK",
        remainingPoints: rlRes.remainingPoints,
        note: "After exceeding 5 req/10s, blocked in-memory for 30s (no Valkey calls)",
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) {
        res.status(500).json({ error: rlRes.message });
        return;
      }
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      res.status(429).json({
        error: "Blocked",
        retryAfterMs: rlRes.msBeforeNext,
        note: "Blocked in-memory — no network round-trip to Valkey",
      });
    }
  });

  // Pattern 3: Token-aware limiting
  app.post("/api/token-limit", async (req, res) => {
    // NOTE: Production code should use Zod or similar for runtime schema validation.
    const body: unknown = req.body;
    const prompt =
      body && typeof body === "object" && "prompt" in body && typeof (body as Record<string, unknown>).prompt === "string"
        ? (body as Record<string, unknown>).prompt as string
        : undefined;
    const userId =
      body && typeof body === "object" && "userId" in body && typeof (body as Record<string, unknown>).userId === "string"
        ? (body as Record<string, unknown>).userId as string
        : undefined;

    if (!prompt || !userId) {
      res.status(400).json({ error: "prompt (string) and userId (string) required" });
      return;
    }

    // Simple token estimation: ~4 chars per token, estimate 3x for output
    const estimatedInputTokens = Math.ceil(prompt.length / 4);
    const estimatedTotal = estimatedInputTokens * 3;

    try {
      const rlRes = await tokenLimiter.consume(userId, estimatedTotal);
      // Simulate LLM response
      const actualTokens = Math.floor(estimatedTotal * 0.7); // Actual was less

      // Give back over-estimated tokens
      const diff = estimatedTotal - actualTokens;
      if (diff > 0) {
        await tokenLimiter.reward(userId, diff);
      }

      res.json({
        message: "LLM response (simulated)",
        tokensEstimated: estimatedTotal,
        tokensActual: actualTokens,
        tokensRefunded: diff,
        remainingTokenBudget: rlRes.remainingPoints + diff,
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) {
        res.status(500).json({ error: rlRes.message });
        return;
      }
      if (!isRateLimiterRes(rlRes)) throw rlRes;
      res.status(429).json({
        error: "Token budget exceeded",
        retryAfterMs: rlRes.msBeforeNext,
        tokensRequested: estimatedTotal,
        budgetPerMinute: 10_000,
      });
    }
  });

  // Pattern 4: Escalating block duration
  app.get("/api/escalating", async (req, res) => {
    const key = req.ip ?? "unknown";
    try {
      const rlRes = await escalatingLimiter.consume(key);
      res.json({
        message: "OK",
        remainingPoints: rlRes.remainingPoints,
        note: "Exceeding limit triggers escalating block durations",
      });
    } catch (rlRes: unknown) {
      if (rlRes instanceof Error) {
        res.status(500).json({ error: rlRes.message });
        return;
      }
      if (!isRateLimiterRes(rlRes)) throw rlRes;

      // Escalate: more overage = longer block
      const overageMultiplier = Math.floor(rlRes.consumedPoints / 5);
      const blockDuration = Math.min(overageMultiplier * 60, 3600);

      if (blockDuration > 0) {
        await escalatingLimiter.block(key, blockDuration);
      }

      res.status(429).json({
        error: "Rate limit exceeded",
        retryAfterMs: rlRes.msBeforeNext,
        blockDurationSec: blockDuration,
        consumedPoints: rlRes.consumedPoints,
        note: `Blocked for ${blockDuration}s (escalates with repeated violations)`,
      });
    }
  });

  app.listen(PORT, () => {
    console.log(`🚀 Server listening on http://localhost:${PORT}`);
    console.log(`   Routes:`);
    console.log(`     GET  /api/insured    — 100 req/min (falls back to in-memory)`);
    console.log(`     GET  /api/blocked    — 5 req/10s (in-memory block for 30s)`);
    console.log(`     POST /api/token-limit — 10k tokens/min per user`);
    console.log(`     GET  /api/escalating  — 5 req/min (escalating block)`);
  });
}

main().catch(console.error);
