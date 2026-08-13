# Getting Started with node-rate-limiter-flexible + Valkey

> Set up distributed rate limiting in under 10 minutes using rate-limiter-flexible with Valkey as the atomic backing store.

**Beginner** · TypeScript · ~10 min

## What is node-rate-limiter-flexible?

[rate-limiter-flexible](https://github.com/animir/node-rate-limiter-flexible) is the most popular Node.js rate-limiting library (3.5k+ stars). It provides atomic, race-condition-free rate limiting with multiple backend stores.
The `RateLimiterValkeyGlide` class uses Valkey server-side functions for atomic increment-and-check in a single round trip:

  * **Atomic operations** — Lua functions on the server prevent race conditions
  * **Sub-millisecond** — ~0.7ms average in cluster mode
  * **Flexible algorithms** — Fixed window, sliding window, token bucket
  * **Insurance strategy** — Automatic failover to in-memory if Valkey is down

## Step 1: Start Valkey

Docker and Node.js 20+ required.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Initialize the Project

```bash
mkdir rate-limiter-demo && cd rate-limiter-demo
npm init -y
npm install rate-limiter-flexible @valkey/valkey-glide express
npm install -D typescript @types/express @types/node tsx
```

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "outDir": "dist",
    "esModuleInterop": true
  }
}
```

## Step 3: Connect to Valkey and Create a Rate Limiter

Create `src/index.ts`:

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { RateLimiterValkeyGlide } from "rate-limiter-flexible";
import express from "express";

const app = express();

async function main() {
  // 1. Connect to Valkey via GLIDE
  const glideClient = await GlideClient.createClient({
    addresses: [{ host: "localhost", port: 6379 }],
  });

  // 2. Create a rate limiter: 10 requests per second per IP
  const rateLimiter = new RateLimiterValkeyGlide({
    storeClient: glideClient,
    points: 10,
    duration: 1,
    keyPrefix: "rl",
  });

  // 3. Apply to an endpoint
  app.get("/api/data", async (req, res) => {
    try {
      const rateLimiterRes = await rateLimiter.consume(req.ip ?? "unknown");
      res.json({
        message: "OK",
        remainingPoints: rateLimiterRes.remainingPoints,
      });
    } catch (rateLimiterRes: unknown) {
      if (rateLimiterRes instanceof Error) throw rateLimiterRes;
      // Rate limited — rateLimiterRes is a RateLimiterRes object
      if (typeof rateLimiterRes !== "object" || rateLimiterRes === null || !("msBeforeNext" in rateLimiterRes)) throw rateLimiterRes;
      res.status(429).json({
        error: "Too Many Requests",
        retryAfterMs: (rateLimiterRes as { msBeforeNext: number }).msBeforeNext,
      });
    }
  });

  app.listen(3000, () => console.log("Listening on :3000"));
}

main();
```

## Step 4: Run and Test

```bash
npx tsx src/index.ts
```

In another terminal, send 12 rapid requests:

```bash
for i in $(seq 1 12); do
  echo "Request $i: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/data)"
done
```

**Expected output:**

```
Request 1: 200
...
Request 10: 200
Request 11: 429
Request 12: 429
```

## How It Works Under the Hood

| Operation | What Happens | Latency |
|-----------|-------------|---------|
| `consume(key)` | Valkey server-side function: `INCRBY` + `PTTL` atomically | ~0.5ms |
| First request in window | `SET key 0 EX duration NX` then `INCRBY` | ~0.5ms |
| Rate limited | Returns `RateLimiterRes` with `msBeforeNext` | ~0.5ms |

The library registers a Lua function on the Valkey server (via `FUNCTION LOAD`) on first use. All subsequent calls invoke this function atomically — no multi-step pipelines, no race conditions.

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[Next: 02 Middleware Patterns →](02-middleware-patterns.md)
