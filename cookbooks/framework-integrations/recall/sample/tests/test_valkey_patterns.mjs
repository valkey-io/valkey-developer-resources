/**
 * Integration tests validating Recall's Valkey data patterns.
 * Uses Node.js built-in test runner (node --test).
 * Requires Valkey running on localhost:6379.
 */
import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { GlideClient } from "@valkey/valkey-glide";
import { randomUUID, createHash } from "node:crypto";

const VALKEY_HOST = process.env.VALKEY_HOST || "localhost";
const VALKEY_PORT = Number(process.env.VALKEY_PORT) || 6379;
const TEST_PREFIX = "test:recall:";

let client;

/**
 * Convert valkey-glide hgetall result (array of {field, value}) to plain object.
 */
function toObject(hgetallResult) {
  if (!hgetallResult || !Array.isArray(hgetallResult)) return {};
  const obj = {};
  for (const { field, value } of hgetallResult) {
    obj[field] = value;
  }
  return obj;
}

before(async () => {
  client = await GlideClient.createClient({
    addresses: [{ host: VALKEY_HOST, port: VALKEY_PORT }],
  });
});

after(async () => {
  // Clean up all test keys
  if (client) {
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${TEST_PREFIX}*`,
        count: 100,
      });
      cursor = nextCursor;
      for (const key of keys) {
        await client.del([key]);
      }
    } while (cursor !== "0");
    client.close();
  }
});

// Pre-clean before each test to handle leftover state
beforeEach(async () => {
  let cursor = "0";
  do {
    const [nextCursor, keys] = await client.scan(cursor, {
      match: `${TEST_PREFIX}*`,
      count: 100,
    });
    cursor = nextCursor;
    for (const key of keys) {
      await client.del([key]);
    }
  } while (cursor !== "0");
});

function workspaceHash(directory) {
  return createHash("sha256").update(directory).digest("hex").slice(0, 12);
}

describe("Valkey Connectivity", () => {
  it("should respond to PING", async () => {
    const result = await client.ping();
    assert.equal(result, "PONG");
  });

  it("should support basic SET/GET", async () => {
    const key = `${TEST_PREFIX}basic`;
    await client.set(key, "hello");
    const value = await client.get(key);
    assert.equal(value, "hello");
  });
});

describe("Recall Memory Storage Pattern", () => {
  it("should store a memory as a hash", async () => {
    const wsHash = workspaceHash("/test/project");
    const memoryId = randomUUID();
    const key = `${TEST_PREFIX}ws:${wsHash}:memory:${memoryId}`;

    const memory = {
      content: "Always use parameterized queries",
      type: "pattern",
      tags: JSON.stringify(["security", "sql"]),
      importance: "9",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    await client.hset(key, memory);
    const retrieved = toObject(await client.hgetall(key));

    assert.equal(retrieved.content, "Always use parameterized queries");
    assert.equal(retrieved.type, "pattern");
    assert.equal(retrieved.importance, "9");
    assert.deepEqual(JSON.parse(retrieved.tags), ["security", "sql"]);
  });

  it("should store multiple memories with unique IDs", async () => {
    const wsHash = workspaceHash("/test/project");
    const memories = [
      "Prefer composition over inheritance",
      "Use Valkey for session storage",
      "All APIs must be versioned",
    ];

    for (const content of memories) {
      const key = `${TEST_PREFIX}ws:${wsHash}:memory:${randomUUID()}`;
      await client.hset(key, { content, type: "decision", importance: "7" });
    }

    // Scan for all memories in this workspace
    const found = [];
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${TEST_PREFIX}ws:${wsHash}:memory:*`,
        count: 100,
      });
      cursor = nextCursor;
      found.push(...keys);
    } while (cursor !== "0");

    assert.equal(found.length, 3);
  });
});

describe("Recall Workspace Index Pattern", () => {
  it("should maintain a sorted set index by timestamp", async () => {
    const wsHash = workspaceHash("/test/indexed-project");
    const indexKey = `${TEST_PREFIX}ws:${wsHash}:index`;

    const ids = [];
    for (let i = 0; i < 5; i++) {
      const id = randomUUID();
      ids.push(id);
      // Score is timestamp (ascending = chronological order)
      await client.zadd(indexKey, { [id]: Date.now() + i });
    }

    // Get count
    const count = await client.zcard(indexKey);
    assert.equal(count, 5);

    // Get recent (last 3)
    const recent = await client.zrange(indexKey, { start: -3, end: -1 });
    assert.equal(recent.length, 3);
    // Most recent should be the last one added
    assert.equal(recent[2], ids[4]);
  });

  it("should support removing memories from the index", async () => {
    const wsHash = workspaceHash("/test/removal-project");
    const indexKey = `${TEST_PREFIX}ws:${wsHash}:index`;
    const memoryId = randomUUID();

    await client.zadd(indexKey, { [memoryId]: Date.now() });
    assert.equal(await client.zcard(indexKey), 1);

    await client.zrem(indexKey, [memoryId]);
    assert.equal(await client.zcard(indexKey), 0);
  });
});

describe("Recall Workspace Isolation", () => {
  it("should isolate memories between workspaces", async () => {
    const hashA = workspaceHash("/project-alpha");
    const hashB = workspaceHash("/project-beta");

    // Store in workspace A
    const keyA = `${TEST_PREFIX}ws:${hashA}:memory:${randomUUID()}`;
    await client.hset(keyA, { content: "Alpha secret", type: "knowledge" });

    // Store in workspace B
    const keyB = `${TEST_PREFIX}ws:${hashB}:memory:${randomUUID()}`;
    await client.hset(keyB, { content: "Beta secret", type: "knowledge" });

    // Scan workspace A — should only find A's memory
    const foundA = [];
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${TEST_PREFIX}ws:${hashA}:memory:*`,
        count: 100,
      });
      cursor = nextCursor;
      foundA.push(...keys);
    } while (cursor !== "0");

    assert.equal(foundA.length, 1);
    const contentA = await client.hget(foundA[0], "content");
    assert.equal(contentA, "Alpha secret");
  });

  it("should generate different hashes for different paths", () => {
    const hash1 = workspaceHash("/Users/dev/project-one");
    const hash2 = workspaceHash("/Users/dev/project-two");
    assert.notEqual(hash1, hash2);
  });
});

describe("Recall Global Memory Pattern", () => {
  it("should store global memories under recall:global: prefix", async () => {
    const memoryId = randomUUID();
    const key = `${TEST_PREFIX}global:memory:${memoryId}`;
    const indexKey = `${TEST_PREFIX}global:index`;

    await client.hset(key, {
      content: "Company uses trunk-based development",
      type: "convention",
      importance: "8",
    });
    await client.zadd(indexKey, { [memoryId]: Date.now() });

    const content = await client.hget(key, "content");
    assert.equal(content, "Company uses trunk-based development");

    const count = await client.zcard(indexKey);
    assert.equal(count, 1);
  });

  it("should keep global memories separate from workspace memories", async () => {
    const wsHash = workspaceHash("/some/workspace");
    const globalId = randomUUID();
    const wsId = randomUUID();

    await client.hset(`${TEST_PREFIX}global:memory:${globalId}`, {
      content: "global",
    });
    await client.hset(`${TEST_PREFIX}ws:${wsHash}:memory:${wsId}`, {
      content: "workspace",
    });

    // Scan global — should only find global
    const globalKeys = [];
    let cursor = "0";
    do {
      const [nextCursor, keys] = await client.scan(cursor, {
        match: `${TEST_PREFIX}global:memory:*`,
        count: 100,
      });
      cursor = nextCursor;
      globalKeys.push(...keys);
    } while (cursor !== "0");

    assert.equal(globalKeys.length, 1);
    const content = await client.hget(globalKeys[0], "content");
    assert.equal(content, "global");
  });
});

describe("Recall Memory Update Pattern", () => {
  it("should update individual hash fields without overwriting others", async () => {
    const wsHash = workspaceHash("/test/update-project");
    const memoryId = randomUUID();
    const key = `${TEST_PREFIX}ws:${wsHash}:memory:${memoryId}`;

    // Initial store
    await client.hset(key, {
      content: "Original content",
      type: "knowledge",
      importance: "5",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    });

    // Update (mimics Recall's update_memory tool)
    await client.hset(key, {
      content: "Updated content",
      importance: "8",
      updated_at: "2024-06-15T00:00:00Z",
    });

    const result = toObject(await client.hgetall(key));
    assert.equal(result.content, "Updated content");
    assert.equal(result.importance, "8");
    assert.equal(result.type, "knowledge"); // unchanged
    assert.equal(result.created_at, "2024-01-01T00:00:00Z"); // unchanged
    assert.equal(result.updated_at, "2024-06-15T00:00:00Z"); // updated
  });
});
