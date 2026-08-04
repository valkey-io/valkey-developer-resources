/**
 * Validates the raw Valkey protocol contract documented in 02-cache-categories-and-ttl.md:
 * keys follow `{prefix}:{category}:{hash}`, writes use SET (with EX for TTL), reads use GET.
 * Uses the `iovalkey` client directly against a real Valkey instance — the same client
 * Stagehand's CacheStorage.createValkey() uses internally, but this file does NOT import
 * or call any code from the fork. It proves the key scheme and commands are valid Valkey
 * usage, not that the fork's actual caching code path is bug-free.
 *
 * This does not exercise Stagehand's CacheStorage class, or act()/agent() — those require
 * the real library, a real browser, and a paid LLM call, demonstrated manually in demo.ts.
 */
import { beforeAll, afterAll, describe, expect, it } from "vitest";
import Valkey from "iovalkey";

const prefix = `stagehand-test-${Date.now()}`;
let client: Valkey;

beforeAll(() => {
  client = new Valkey({
    host: process.env.VALKEY_HOST ?? "localhost",
    port: Number(process.env.VALKEY_PORT ?? 6379),
  });
});

afterAll(async () => {
  const keys = await client.keys(`${prefix}:*`);
  if (keys.length > 0) {
    await client.del(...keys);
  }
  client.disconnect();
});

describe("Stagehand Valkey cache contract", () => {
  it("writes and reads an act() entry under {prefix}:act:{hash}", async () => {
    const key = `${prefix}:act:a1b2c3d4`;
    const value = JSON.stringify({ action: "click", selector: "#quickstart" });

    await client.set(key, value);
    const result = await client.get(key);

    expect(result).toBe(value);
  });

  it("namespaces agent() entries separately under {prefix}:agent:{hash}", async () => {
    const agentKey = `${prefix}:agent:e5f6g7h8`;
    const actKey = `${prefix}:act:e5f6g7h8`;

    await client.set(agentKey, JSON.stringify({ steps: ["navigate", "click"] }));

    expect(await client.get(agentKey)).not.toBeNull();
    expect(await client.get(actKey)).toBeNull();
  });

  it("expires entries written with a TTL via SET ... EX", async () => {
    const key = `${prefix}:act:ttl-check`;

    await client.set(key, "cached-value", "EX", 1);
    expect(await client.get(key)).toBe("cached-value");

    const ttl = await client.ttl(key);
    expect(ttl).toBeGreaterThan(0);
    expect(ttl).toBeLessThanOrEqual(1);
  });

  it("returns null on a cache miss without throwing", async () => {
    const result = await client.get(`${prefix}:act:never-written`);
    expect(result).toBeNull();
  });
});
