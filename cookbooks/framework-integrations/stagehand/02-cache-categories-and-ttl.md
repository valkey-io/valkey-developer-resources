# Cache Categories and TTL

> Understand how Stagehand namespaces cached actions into act and agent categories, configure key prefixes for multi-tenant setups, and set TTL to expire stale entries automatically.

**Intermediate** · TypeScript · ~15 min

**Who is this for:** Developers who've completed the getting-started cookbook and need to namespace or expire cached actions across environments, tenants, or deployments.

Stagehand stores two categories of cached actions in Valkey: `act` (single-step browser actions) and `agent` (multi-step task sequences).
Understanding this structure lets you inspect, tune, and isolate cache data across environments or tenants.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running on localhost:6379

## Step 1: Understand Key Structure

Stagehand keys follow the pattern:

```text
{prefix}:{category}:{hash}
```

- **prefix** - configurable via `valkeyKeyPrefix` (default: `"stagehand"`)
- **category** - either `act` or `agent`
- **hash** - deterministic hash of the instruction and page state

## Step 2: Configure a Custom Key Prefix

Use `valkeyKeyPrefix` to namespace cache keys per environment or tenant:

```typescript
import { Stagehand } from "@browserbasehq/stagehand";

const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: "localhost",
  valkeyKeyPrefix: "myapp-staging",
});

await stagehand.init();
try {
  const page = stagehand.context.pages()[0];
  await page.goto("https://docs.stagehand.dev");
  await stagehand.act("click on the Quickstart link");
} finally {
  await stagehand.close();
}
```

This stores keys like `myapp-staging:act:<hash>` instead of the default `stagehand:act:<hash>`.

## Step 3: Set TTL for Automatic Expiry

Set `cacheTtl` (in seconds) to automatically expire stale cache entries. This is useful when pages change frequently and cached actions may become invalid:

```typescript
const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: "localhost",
  cacheTtl: 3600, // Cache entries expire after 1 hour
});

await stagehand.init();
try {
  const page = stagehand.context.pages()[0];
  await page.goto("https://docs.stagehand.dev");
  await stagehand.act("click on the Quickstart link");
} finally {
  await stagehand.close();
}
```

Omitting `cacheTtl` (or setting it to `0`) means entries persist indefinitely until manually deleted.

## Step 4: Use the Agent Cache

The `agent()` method caches multi-step task sequences under the `agent` category:

```typescript
const stagehand = new Stagehand({
  env: "LOCAL",
  model: {
    modelName: "gpt-4o-mini",
    apiKey: process.env.OPENAI_API_KEY,
  },
  valkeyHost: "localhost",
  valkeyKeyPrefix: "myapp",
  cacheTtl: 7200,
});

await stagehand.init();
try {
  const page = stagehand.context.pages()[0];
  await page.goto("https://github.com/browserbase/stagehand");

  const agent = stagehand.agent();
  await agent.execute("Navigate to the Issues tab and find the newest open issue");
} finally {
  await stagehand.close();
}
```

The resolved step sequence is stored at `myapp:agent:<hash>` and replays on subsequent calls with the same instruction.

## What Happens Under the Hood

| Action | Valkey Command | Key Example |
| --- | --- | --- |
| Cache write (no TTL) | `SET key value` | `myapp:act:a1b2c3d4` |
| Cache write (with TTL) | `SET key value EX 3600` | `myapp:agent:e5f6g7h8` |
| Cache read | `GET key` | `myapp:act:a1b2c3d4` |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Configuration →](03-production-configuration.md)
