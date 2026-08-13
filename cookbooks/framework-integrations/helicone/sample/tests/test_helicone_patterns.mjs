import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import Redis from "ioredis";
import { createHash } from "node:crypto";

const TEST_PREFIX = "test:helicone:";

describe("Helicone Valkey Patterns", () => {
  let client;

  before(() => {
    client = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
  });

  after(async () => {
    try {
      const keys = await client.keys(`${TEST_PREFIX}*`);
      if (keys.length > 0) await client.del(...keys);
    } finally {
      client.disconnect();
    }
  });

  beforeEach(async () => {
    const keys = await client.keys(`${TEST_PREFIX}*`);
    if (keys.length > 0) await client.del(...keys);
  });

  describe("Connectivity", () => {
    it("responds to PING", async () => {
      const result = await client.ping();
      assert.equal(result, "PONG");
    });

    it("detects Valkey via INFO SERVER", async () => {
      const info = await client.call("INFO", "SERVER");
      const serverName = info.match(/^server_name:(.+)$/m)?.[1]?.trim();
      assert.equal(serverName, "valkey", `Expected server_name to be 'valkey', got '${serverName}'`);
    });
  });

  describe("KV Cache — SET PX / GET", () => {
    it("stores a JSON value with SET PX and retrieves it with GET", async () => {
      const key = `${TEST_PREFIX}kv:item`;
      const value = JSON.stringify({ model: "gpt-4o", tokens: 512 });
      await client.set(key, value, "PX", 5000);
      const result = await client.get(key);
      assert.equal(result, value);
      assert.deepEqual(JSON.parse(result), { model: "gpt-4o", tokens: 512 });
    });

    it("returns null for a missing key", async () => {
      assert.equal(await client.get(`${TEST_PREFIX}kv:missing`), null);
    });

    it("expires after the millisecond TTL", async () => {
      const key = `${TEST_PREFIX}kv:expiring`;
      await client.set(key, "temp", "PX", 100);
      assert.notEqual(await client.get(key), null);
      await new Promise((r) => setTimeout(r, 150));
      assert.equal(await client.get(key), null);
    });
  });

  describe("Proxy Rate Limiter — GET / SET EX (sliding window)", () => {
    it("stores a JSON entry array with SET EX and retrieves it", async () => {
      const key = `${TEST_PREFIX}rl:window`;
      const entries = [{ timestamp: Date.now(), unit: 1 }];
      await client.set(key, JSON.stringify(entries), "EX", 60);
      assert.deepEqual(JSON.parse(await client.get(key)), entries);
    });

    it("expires the window after the TTL", async () => {
      const key = `${TEST_PREFIX}rl:expiring`;
      await client.set(key, JSON.stringify([{ timestamp: Date.now(), unit: 1 }]), "EX", 1);
      assert.notEqual(await client.get(key), null);
      await new Promise((r) => setTimeout(r, 1100));
      assert.equal(await client.get(key), null);
    });

    it("sliding window prunes entries outside the window on read", async () => {
      const key = `${TEST_PREFIX}rl:sliding`;
      const now = Date.now();
      const windowMs = 60_000;
      const entries = [
        { timestamp: now - 90_000, unit: 1 }, // outside window
        { timestamp: now - 30_000, unit: 1 }, // inside window
        { timestamp: now, unit: 1 },           // inside window
      ];
      await client.set(key, JSON.stringify(entries), "EX", 60);
      const active = JSON.parse(await client.get(key)).filter((e) => e.timestamp >= now - windowMs);
      assert.equal(active.length, 2);
    });
  });

  describe("Lua Rate Limiter — SCRIPT LOAD / EVALSHA", () => {
    const luaScript = `
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
`.trim();

    it("SCRIPT LOAD returns a 40-character SHA", async () => {
      const sha = await client.call("SCRIPT", "LOAD", luaScript);
      assert.equal(typeof sha, "string");
      assert.equal(sha.length, 40);
    });

    it("EVALSHA increments the counter and sets a window TTL", async () => {
      const key = `${TEST_PREFIX}lua:counter`;
      const sha = await client.call("SCRIPT", "LOAD", luaScript);
      const result = await client.evalsha(sha, 1, key, "60000");
      assert.equal(result[0], 1);
      assert.ok(result[1] > 0, "TTL should be positive");
    });

    it("increments the counter on each EVALSHA call", async () => {
      const key = `${TEST_PREFIX}lua:multi`;
      const sha = await client.call("SCRIPT", "LOAD", luaScript);
      assert.equal((await client.evalsha(sha, 1, key, "60000"))[0], 1);
      assert.equal((await client.evalsha(sha, 1, key, "60000"))[0], 2);
      assert.equal((await client.evalsha(sha, 1, key, "60000"))[0], 3);
    });

    it("returns NOSCRIPT error for an unknown SHA", async () => {
      const key = `${TEST_PREFIX}lua:noscript`;
      await assert.rejects(
        () => client.evalsha("0".repeat(40), 1, key, "60000"),
        /NOSCRIPT/
      );
    });
  });

  describe("Usage Cache — GET / SET EX (cache-aside)", () => {
    it("returns null on cache miss", async () => {
      assert.equal(await client.get(`${TEST_PREFIX}usage:miss`), null);
    });

    it("stores and retrieves a boolean result string", async () => {
      const key = `${TEST_PREFIX}usage:org1`;
      await client.set(key, "true", "EX", 3600);
      assert.equal(await client.get(key), "true");
    });

    it("expires after the TTL", async () => {
      const key = `${TEST_PREFIX}usage:expiring`;
      await client.set(key, "true", "EX", 1);
      assert.equal(await client.get(key), "true");
      await new Promise((r) => setTimeout(r, 1100));
      assert.equal(await client.get(key), null);
    });
  });

  describe("Encrypted Key Cache — GET / SET EX (SHA-256 hashed key)", () => {
    it("stores an opaque value under a hashed key", async () => {
      const plainKey = "api-key:provider-x";
      // Helicone hashes the key with SHA-256; the app handles encryption of the value
      const hashedKey = `${TEST_PREFIX}enc:${createHash("sha256").update(plainKey).digest("hex")}`;
      const encryptedValue = '{"iv":"abc123","content":"ciphertext"}';
      await client.set(hashedKey, encryptedValue, "EX", 600);
      assert.equal(await client.get(hashedKey), encryptedValue);
    });

    it("same plain key always produces the same hashed key", async () => {
      const plainKey = "api-key:deterministic";
      const h1 = createHash("sha256").update(plainKey).digest("hex");
      const h2 = createHash("sha256").update(plainKey).digest("hex");
      assert.equal(h1, h2);
    });

    it("different plain keys produce different hashed keys", async () => {
      const h1 = createHash("sha256").update("key:a").digest("hex");
      const h2 = createHash("sha256").update("key:b").digest("hex");
      assert.notEqual(h1, h2);
    });

    it("expires after the TTL", async () => {
      const hashedKey = `${TEST_PREFIX}enc:expiring`;
      await client.set(hashedKey, '{"iv":"x","content":"y"}', "EX", 1);
      assert.notEqual(await client.get(hashedKey), null);
      await new Promise((r) => setTimeout(r, 1100));
      assert.equal(await client.get(hashedKey), null);
    });
  });
});
