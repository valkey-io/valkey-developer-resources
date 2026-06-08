# Advanced Patterns

**Advanced** · TypeScript · ~20 min

## Insurance Strategy (Failover to In-Memory)

If Valkey goes down, you don't want to either block all traffic or allow unlimited requests. The insurance strategy uses an in-memory limiter as a fallback:

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import {
  RateLimiterValkeyGlide,
  RateLimiterMemory,
} from "rate-limiter-flexible";

const glideClient = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

// Backup limiter — slightly more permissive to avoid false positives
// across multiple app instances that can't share state
const insuranceLimiter = new RateLimiterMemory({
  points: 150,
  duration: 60,
});

const rateLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 100,
  duration: 60,
  keyPrefix: "rl:insured",
  insuranceLimiter,
});
```

When Valkey is unreachable, `rate-limiter-flexible` automatically falls back to the in-memory limiter. When Valkey recovers, it switches back — no manual intervention needed.

## In-Memory Block Strategy

For high-volume attacks (100k+ req/sec), even the Valkey round trip adds up. Block abusive keys in-memory to avoid hitting the network at all:

```typescript
const rateLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 10,
  duration: 1,
  keyPrefix: "rl:block",
  // After consuming 10 points, block in-memory for 30 seconds
  inMemoryBlockOnConsumed: 10,
  inMemoryBlockDuration: 30,
});
```

**How it works:** Once a key exceeds `inMemoryBlockOnConsumed`, all subsequent requests for that key are rejected instantly from process memory — zero network calls to Valkey. After `inMemoryBlockDuration` seconds, the block expires and the key is checked against Valkey again.

## Token-Aware Rate Limiting for AI Workloads

LLM API calls vary wildly in cost. A 4-token request and a 4000-token request shouldn't count the same. Use points proportional to token consumption:

```typescript
import { encoding_for_model } from "tiktoken";

const glideClient = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

// Budget: 10,000 tokens per minute per user
const tokenLimiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 10_000,
  duration: 60,
  keyPrefix: "rl:tokens",
});

async function checkTokenBudget(
  userId: string,
  prompt: string,
): Promise<{ allowed: boolean; tokensUsed?: number; retryAfterMs?: number }> {
  const enc = encoding_for_model("gpt-4");
  const inputTokens = enc.encode(prompt).length;
  enc.free();

  // Estimate output tokens (conservative: 2x input)
  const estimatedTotal = inputTokens * 3;

  try {
    await tokenLimiter.consume(userId, estimatedTotal);
    return { allowed: true, tokensUsed: estimatedTotal };
  } catch (rlRes: unknown) {
    if (rlRes instanceof Error) throw rlRes;
    if (typeof rlRes === "object" && rlRes !== null && "msBeforeNext" in rlRes) {
      return { allowed: false, retryAfterMs: (rlRes as { msBeforeNext: number }).msBeforeNext };
    }
    throw rlRes;
  }
}

// After the LLM responds, adjust for actual usage
async function adjustTokenUsage(
  userId: string,
  estimated: number,
  actual: number,
): Promise<void> {
  const diff = estimated - actual;
  if (diff > 0) {
    // Give back over-estimated tokens
    await tokenLimiter.reward(userId, diff);
  } else if (diff < 0) {
    // Charge under-estimated tokens
    await tokenLimiter.penalty(userId, Math.abs(diff));
  }
}
```

Usage in an endpoint:

```typescript
app.post("/api/chat", async (req, res) => {
  const { prompt } = req.body;
  const userId = req.user.id;

  const budget = await checkTokenBudget(userId, prompt);
  if (!budget.allowed) {
    res.status(429).json({
      error: "Token budget exceeded",
      retryAfterMs: budget.retryAfterMs,
    });
    return;
  }

  const llmResponse = await callLLM(prompt);

  // Adjust for actual token usage (tokensUsed is always set when allowed === true)
  await adjustTokenUsage(userId, budget.tokensUsed ?? 0, llmResponse.totalTokens);

  res.json({ response: llmResponse.text });
});
```

## Valkey Cluster Mode

For high-availability production deployments, use `GlideClusterClient`:

```typescript
import { GlideClusterClient } from "@valkey/valkey-glide";
import { RateLimiterValkeyGlide } from "rate-limiter-flexible";

const clusterClient = await GlideClusterClient.createClient({
  addresses: [
    { host: "valkey-node-1", port: 6379 },
    { host: "valkey-node-2", port: 6379 },
    { host: "valkey-node-3", port: 6379 },
  ],
});

const rateLimiter = new RateLimiterValkeyGlide({
  storeClient: clusterClient,
  points: 100,
  duration: 60,
  keyPrefix: "rl:cluster",
});
```

`RateLimiterValkeyGlide` works identically with both `GlideClient` and `GlideClusterClient` — no code changes needed beyond the client initialization.

## Dynamic Block Duration

Escalate block duration for repeat offenders:

```typescript
const limiter = new RateLimiterValkeyGlide({
  storeClient: glideClient,
  points: 10,
  duration: 60,
  keyPrefix: "rl:dynamic",
});

async function consumeWithEscalation(key: string): Promise<void> {
  try {
    await limiter.consume(key);
  } catch (rlRes: unknown) {
    if (rlRes instanceof Error) throw rlRes;
    if (typeof rlRes !== "object" || rlRes === null || !("consumedPoints" in rlRes)) throw rlRes;
    const { consumedPoints, msBeforeNext } = rlRes as { consumedPoints: number; msBeforeNext: number };

    // Escalate: the more they exceed, the longer the block
    const overageMultiplier = Math.floor(consumedPoints / 10);
    const blockDuration = Math.min(overageMultiplier * 60, 3600); // Max 1 hour

    await limiter.block(key, blockDuration);
    throw new RateLimitError(msBeforeNext, blockDuration);
  }
}

class RateLimitError extends Error {
  constructor(
    public readonly retryAfterMs: number,
    public readonly blockDurationSec: number,
  ) {
    super("Rate limit exceeded");
    this.name = "RateLimitError";
  }
}
```

## Production Checklist

| Concern | Solution |
|---------|----------|
| Valkey downtime | `insuranceLimiter` — automatic in-memory fallback |
| DDoS / high-volume abuse | `inMemoryBlockOnConsumed` — zero-network rejection |
| Connection pooling | `GlideClient` handles pooling internally |
| Multiple app instances | Valkey is the shared state — all instances see the same counters |
| Key expiry / memory | Built-in TTL via `duration` — keys auto-expire |
| Cluster failover | `GlideClusterClient` handles topology changes automatically |

---

[← 02 Middleware Patterns](02-middleware-patterns.md)
