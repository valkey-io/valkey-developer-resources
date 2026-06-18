/**
 * Stagehand + Valkey Cache Demo
 *
 * Demonstrates all three cookbook topics in a single runnable script:
 *   1. Basic cached browser action (01-getting-started)
 *   2. Cache categories, key prefix, and TTL (02-cache-categories-and-ttl)
 *   3. Production configuration with TLS and auth (03-production-configuration)
 *
 * Usage:
 *   OPENAI_API_KEY=your-key npx tsx demo.ts
 *
 * Requires:
 *   - Valkey running on localhost:6379 (see docker-compose.yml)
 *   - An OpenAI API key (or any Stagehand-supported LLM provider)
 */

import { Stagehand } from "@browserbasehq/stagehand";

async function main() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY environment variable is required");
  }

  // --- Section 1: Basic cached action (01-getting-started) ---
  // Connect to a local Valkey instance. On the first run, act() resolves via
  // the LLM. On subsequent runs with the same instruction and page state, the
  // cached result is read from Valkey and replayed without any LLM call.

  const stagehand = new Stagehand({
    env: "LOCAL",
    model: {
      modelName: "gpt-4o-mini",
      apiKey,
    },
    // --- Section 2: Key prefix and TTL (02-cache-categories-and-ttl) ---
    // Keys follow the pattern: {prefix}:{category}:{hash}
    // Categories are "act" (single-step) or "agent" (multi-step).
    valkeyHost: process.env.VALKEY_HOST ?? "localhost",
    valkeyPort: Number(process.env.VALKEY_PORT ?? 6379),
    valkeyKeyPrefix: "stagehand-demo",
    cacheTtl: 3600, // entries expire after 1 hour

    // --- Section 3: Production TLS/auth (03-production-configuration) ---
    // Uncomment the following for TLS-enabled or ACL-protected instances:
    // valkeyTls: true,
    // valkeyUsername: process.env.VALKEY_USERNAME,
    // valkeyPassword: process.env.VALKEY_PASSWORD,
  });

  await stagehand.init();
  try {
    const page = stagehand.context.pages()[0];

    // Navigate and perform a cached action
    await page.goto("https://docs.stagehand.dev");
    console.log("Running act() - first call resolves via LLM, second replays from Valkey cache");
    await stagehand.act("click on the Quickstart link");
    console.log("Action completed. Page title:", await page.title());
  } finally {
    await stagehand.close();
  }
  console.log("\nDone! Run again to see the cache hit (no LLM call).");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
