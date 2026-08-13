/**
 * Test script — exercises all rate-limiting patterns against a running Valkey instance.
 *
 * This script does NOT start a server. It directly tests the rate limiters
 * to verify they work correctly with Valkey.
 *
 * Run: npm test
 * Requires: Valkey running on localhost:6379
 */

import { GlideClient } from "@valkey/valkey-glide";
import {
  RateLimiterValkeyGlide,
  RateLimiterMemory,
} from "rate-limiter-flexible";
import { isRateLimiterRes } from "./rate-limiter-guard.js";

async function main() {
  const glideClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });
  console.log("✅ Connected to Valkey\n");

  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, name: string): void {
    if (condition) {
      console.log(`  ✅ ${name}`);
      passed++;
    } else {
      console.log(`  ❌ ${name}`);
      failed++;
    }
  }

  // --- Test 1: Basic rate limiting ---
  console.log("Test 1: Basic fixed-window rate limiting");
  {
    const limiter = new RateLimiterValkeyGlide({
      storeClient: glideClient,
      points: 3,
      duration: 10,
      keyPrefix: "test:basic",
    });

    // Clean up from previous runs
    await limiter.delete("test-key");

    const r1 = await limiter.consume("test-key");
    assert(r1.remainingPoints === 2, "First consume: 2 remaining");

    const r2 = await limiter.consume("test-key");
    assert(r2.remainingPoints === 1, "Second consume: 1 remaining");

    const r3 = await limiter.consume("test-key");
    assert(r3.remainingPoints === 0, "Third consume: 0 remaining");

    try {
      await limiter.consume("test-key");
      assert(false, "Fourth consume should throw");
    } catch (e: unknown) {
      if (e instanceof Error) throw e;
      assert(true, "Fourth consume rejected (rate limited)");
    }
  }

  // --- Test 2: Insurance strategy ---
  console.log("\nTest 2: Insurance strategy (in-memory fallback)");
  {
    const insurance = new RateLimiterMemory({ points: 5, duration: 10 });
    const limiter = new RateLimiterValkeyGlide({
      storeClient: glideClient,
      points: 5,
      duration: 10,
      keyPrefix: "test:insured",
      insuranceLimiter: insurance,
    });

    await limiter.delete("insured-key");
    const r = await limiter.consume("insured-key");
    assert(r.remainingPoints === 4, "Insured limiter works normally");
  }

  // --- Test 3: Block duration ---
  console.log("\nTest 3: Block duration");
  {
    const limiter = new RateLimiterValkeyGlide({
      storeClient: glideClient,
      points: 2,
      duration: 10,
      keyPrefix: "test:block",
      blockDuration: 5,
    });

    await limiter.delete("block-key");
    await limiter.consume("block-key");
    await limiter.consume("block-key");

    try {
      await limiter.consume("block-key");
      assert(false, "Should be blocked");
    } catch (e: unknown) {
      if (e instanceof Error) throw e;
      if (!isRateLimiterRes(e)) throw e;
      assert(e.msBeforeNext > 4000, "Blocked for ~5 seconds");
    }
  }

  // --- Test 4: Reward (token refund) ---
  console.log("\nTest 4: Reward (refund points)");
  {
    const limiter = new RateLimiterValkeyGlide({
      storeClient: glideClient,
      points: 100,
      duration: 60,
      keyPrefix: "test:reward",
    });

    await limiter.delete("reward-key");
    await limiter.consume("reward-key", 50);
    const before = await limiter.get("reward-key");
    assert(before?.consumedPoints === 50, "Consumed 50 points");

    await limiter.reward("reward-key", 20);
    const after = await limiter.get("reward-key");
    assert(after?.consumedPoints === 30, "After reward: 30 consumed (refunded 20)");
  }

  // --- Test 5: Penalty ---
  console.log("\nTest 5: Penalty (add points)");
  {
    const limiter = new RateLimiterValkeyGlide({
      storeClient: glideClient,
      points: 100,
      duration: 60,
      keyPrefix: "test:penalty",
    });

    await limiter.delete("penalty-key");
    await limiter.consume("penalty-key", 10);
    await limiter.penalty("penalty-key", 5);
    const result = await limiter.get("penalty-key");
    assert(result?.consumedPoints === 15, "After penalty: 15 consumed (10 + 5)");
  }

  // --- Summary ---
  console.log(`\n${"=".repeat(40)}`);
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log(`${"=".repeat(40)}`);

  await glideClient.close();
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
