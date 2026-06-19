# Getting Started with Stagehand + Valkey

> Connect Stagehand to a local Valkey instance so that act() and agent() actions are cached and replayed without LLM inference on subsequent runs.

**Beginner** · TypeScript · ~15 min

Stagehand's `act()` and `agent()` methods can cache their resolved actions so that identical instructions replay instantly on subsequent runs. By default this uses the local filesystem, but configuring `valkeyHost` switches the backend to Valkey - enabling shared caching across machines, TTL-based expiry, and zero local disk usage.

## Prerequisites

- Docker installed
- Node.js 18+
- An OpenAI API key (or any Stagehand-supported LLM provider)

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments (see [03 - Production Configuration](03-production-configuration.md)).

## Step 1: Start Valkey

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
docker exec valkey valkey-cli PING
# PONG
```

If you cloned the sample directory, you can use `docker compose up -d` instead.

## Step 2: Set Up the Project

```bash
mkdir stagehand-valkey-demo && cd stagehand-valkey-demo
npm init -y
npm install @browserbasehq/stagehand
npm install -D typescript tsx
```

## Step 3: Create a Cached Browser Action

Create `demo.ts`:

```typescript
import { Stagehand } from "@browserbasehq/stagehand";

async function main() {
  const stagehand = new Stagehand({
    env: "LOCAL",
    model: {
      modelName: "gpt-4o-mini",
      apiKey: process.env.OPENAI_API_KEY,
    },
    valkeyHost: "localhost",
    valkeyPort: 6379,
  });

  await stagehand.init();
  const page = stagehand.context.pages()[0];
  await page.goto("https://docs.stagehand.dev");

  // First run: resolves via LLM. Second run: replays from Valkey cache.
  await stagehand.act("click on the Quickstart link");

  console.log("Action completed. Page title:", await page.title());
  await stagehand.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

Run it:

```bash
OPENAI_API_KEY=your-key npx tsx demo.ts
```

On the first run Stagehand calls the LLM to resolve the action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed without any LLM call.

## What Happens Under the Hood

When `valkeyHost` is set, Stagehand:

1. Connects to Valkey via `iovalkey`
2. On `act()` or `agent()`, hashes the instruction + page context into a cache key
3. Stores the resolved action sequence as JSON under `stagehand:act:<hash>` or `stagehand:agent:<hash>`
4. On repeat calls, reads the cached entry with `GET` and replays the actions directly

If the Valkey connection fails at startup, Stagehand logs a warning and falls back to disabled caching - the automation still runs, just without cache benefits.

---

[02 - Cache Categories and TTL →](02-cache-categories-and-ttl.md)
