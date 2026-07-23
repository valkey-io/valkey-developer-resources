/**
 * Simulates Recall's memory storage patterns in Valkey.
 * Demonstrates the key structure without requiring Recall or an Anthropic API key.
 */
import { GlideClient } from "@valkey/valkey-glide";
import { randomUUID, createHash } from "node:crypto";

const VALKEY_HOST = process.env.VALKEY_HOST || "localhost";
const VALKEY_PORT = Number(process.env.VALKEY_PORT) || 6379;

/**
 * Generate a workspace hash from a directory path (mimics Recall's behavior).
 */
function workspaceHash(directory) {
  return createHash("sha256").update(directory).digest("hex").slice(0, 12);
}

/**
 * Store a memory in the same format Recall uses.
 */
async function storeMemory(client, wsHash, content, options = {}) {
  const memoryId = randomUUID();
  const now = new Date().toISOString();
  const key = `recall:ws:${wsHash}:memory:${memoryId}`;

  const memory = {
    content,
    type: options.type || "knowledge",
    tags: JSON.stringify(options.tags || []),
    importance: String(options.importance || 5),
    created_at: now,
    updated_at: now,
  };

  // Store as hash (matching Recall's pattern)
  for (const [field, value] of Object.entries(memory)) {
    await client.hset(key, { [field]: value });
  }

  // Add to workspace index (sorted set, scored by timestamp)
  const indexKey = `recall:ws:${wsHash}:index`;
  await client.zadd(indexKey, { [memoryId]: Date.now() });

  return { memoryId, key };
}

async function main() {
  let client;
  try {
    client = await GlideClient.createClient({
      addresses: [{ host: VALKEY_HOST, port: VALKEY_PORT }],
    });

    console.log("Connected to Valkey\n");

    // Simulate two workspaces
    const wsA = workspaceHash("/Users/dev/project-alpha");
    const wsB = workspaceHash("/Users/dev/project-beta");

    console.log(`Workspace A hash: ${wsA}`);
    console.log(`Workspace B hash: ${wsB}\n`);

    // Store memories in workspace A
    const mem1 = await storeMemory(client, wsA, "Use Valkey for all caching layers", {
      type: "decision",
      tags: ["infrastructure", "valkey"],
      importance: 8,
    });
    console.log(`Stored in workspace A: ${mem1.key}`);

    const mem2 = await storeMemory(client, wsA, "API responses should be cached for 5 minutes", {
      type: "pattern",
      tags: ["api", "caching"],
      importance: 6,
    });
    console.log(`Stored in workspace A: ${mem2.key}`);

    // Store a memory in workspace B (isolated)
    const mem3 = await storeMemory(client, wsB, "This project uses PostgreSQL for persistence", {
      type: "knowledge",
      tags: ["database"],
      importance: 7,
    });
    console.log(`Stored in workspace B: ${mem3.key}\n`);

    // Demonstrate workspace isolation
    const indexA = await client.zcard(`recall:ws:${wsA}:index`);
    const indexB = await client.zcard(`recall:ws:${wsB}:index`);
    console.log(`Workspace A memories: ${indexA}`);
    console.log(`Workspace B memories: ${indexB}`);
    console.log("→ Workspaces are isolated!\n");

    // Read back a memory
    const fields = await client.hgetall(mem1.key);
    console.log("Retrieved memory:");
    console.log(JSON.stringify(fields, null, 2));

    // Clean up
    const pattern = "recall:*";
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, { match: pattern, count: 100 });
      cursor = nextCursor;
      for (const key of keys) {
        await client.del([key]);
      }
    } while (cursor !== "0");

    console.log("\n✓ Cleaned up all recall:* keys");
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  } finally {
    if (client) {
      client.close();
    }
  }
}

main();
