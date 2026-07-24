import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import Redis from "ioredis";

const TEST_PREFIX = "test:firecrawl:";

describe("Firecrawl Valkey Patterns", () => {
  let redis;

  before(() => {
    redis = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
  });

  after(async () => {
    try {
      const keys = await redis.keys(`${TEST_PREFIX}*`);
      if (keys.length > 0) {
        await redis.del(...keys);
      }
    } finally {
      redis.disconnect();
    }
  });

  beforeEach(async () => {
    const keys = await redis.keys(`${TEST_PREFIX}*`);
    if (keys.length > 0) {
      await redis.del(...keys);
    }
  });

  describe("Connectivity", () => {
    it("responds to PING", async () => {
      const result = await redis.ping();
      assert.equal(result, "PONG");
    });

    it("detects Valkey via INFO SERVER", async () => {
      const info = await redis.call("INFO", "SERVER");
      const serverName = info.match(/^server_name:(.+)$/m)?.[1]?.trim();
      assert.equal(serverName, "valkey", "Expected server_name to be 'valkey'");
    });
  });

  describe("Basic Operations", () => {
    it("SET and GET a string value", async () => {
      const key = `${TEST_PREFIX}basic:str`;
      await redis.set(key, "hello");
      const val = await redis.get(key);
      assert.equal(val, "hello");
      await redis.del(key);
    });

    it("SET and GET a JSON value", async () => {
      const key = `${TEST_PREFIX}basic:json`;
      const data = { url: "https://example.com", depth: 2, ts: Date.now() };
      await redis.set(key, JSON.stringify(data));
      const raw = await redis.get(key);
      const parsed = JSON.parse(raw);
      assert.deepEqual(parsed, data);
      await redis.del(key);
    });

    it("DEL removes a key", async () => {
      const key = `${TEST_PREFIX}basic:del`;
      await redis.set(key, "temp");
      const deleted = await redis.del(key);
      assert.equal(deleted, 1);
      const val = await redis.get(key);
      assert.equal(val, null);
    });

    it("SET with EX expires after TTL", async () => {
      const key = `${TEST_PREFIX}basic:ex`;
      await redis.set(key, "cached", "EX", 1);
      const before = await redis.get(key);
      assert.equal(before, "cached");
      await new Promise((r) => setTimeout(r, 1100));
      const afterExpiry = await redis.get(key);
      assert.equal(afterExpiry, null);
    });
  });

  describe("Rate Limiting Pattern", () => {
    it("INCR increments a counter", async () => {
      const key = `${TEST_PREFIX}ratelimit:counter`;
      const r1 = await redis.incr(key);
      const r2 = await redis.incr(key);
      const r3 = await redis.incr(key);
      assert.equal(r1, 1);
      assert.equal(r2, 2);
      assert.equal(r3, 3);
    });

    it("EXPIRE sets TTL on rate limit key", async () => {
      const key = `${TEST_PREFIX}ratelimit:ttl`;
      await redis.incr(key);
      await redis.expire(key, 60);
      const ttl = await redis.ttl(key);
      assert.ok(ttl > 0 && ttl <= 60, `TTL should be between 1 and 60, got ${ttl}`);
    });

    it("counter resets after expiration", async () => {
      const key = `${TEST_PREFIX}ratelimit:reset`;
      await redis.incr(key);
      await redis.incr(key);
      await redis.expire(key, 1);
      await new Promise((r) => setTimeout(r, 1100));
      const val = await redis.get(key);
      assert.equal(val, null);
    });
  });

  describe("Sorted Set Operations (Crawl State)", () => {
    it("ZADD adds members with scores", async () => {
      const key = `${TEST_PREFIX}crawl:pending`;
      const now = Date.now();
      const added = await redis.zadd(key, now, "url1", now + 1000, "url2");
      assert.equal(added, 2);
    });

    it("ZRANGE returns members in score order", async () => {
      const key = `${TEST_PREFIX}crawl:ordered`;
      await redis.zadd(key, 300, "third", 100, "first", 200, "second");
      const members = await redis.zrange(key, 0, -1);
      assert.deepEqual(members, ["first", "second", "third"]);
    });

    it("ZRANGE WITHSCORES includes scores", async () => {
      const key = `${TEST_PREFIX}crawl:scores`;
      await redis.zadd(key, 10, "a", 20, "b");
      const result = await redis.zrange(key, 0, -1, "WITHSCORES");
      assert.deepEqual(result, ["a", "10", "b", "20"]);
    });

    it("ZREM removes a member", async () => {
      const key = `${TEST_PREFIX}crawl:rem`;
      await redis.zadd(key, 1, "x", 2, "y", 3, "z");
      const removed = await redis.zrem(key, "y");
      assert.equal(removed, 1);
      const members = await redis.zrange(key, 0, -1);
      assert.deepEqual(members, ["x", "z"]);
    });

    it("ZCARD returns cardinality", async () => {
      const key = `${TEST_PREFIX}crawl:card`;
      await redis.zadd(key, 1, "a", 2, "b", 3, "c");
      const card = await redis.zcard(key);
      assert.equal(card, 3);
    });
  });

  describe("Set Operations (URL Dedup)", () => {
    it("SADD returns 1 for new members", async () => {
      const key = `${TEST_PREFIX}dedup:urls`;
      const result = await redis.sadd(key, "https://example.com/page1");
      assert.equal(result, 1);
    });

    it("SADD returns 0 for duplicate members", async () => {
      const key = `${TEST_PREFIX}dedup:dup`;
      await redis.sadd(key, "https://example.com/page1");
      const result = await redis.sadd(key, "https://example.com/page1");
      assert.equal(result, 0);
    });

    it("SMEMBERS returns all set members", async () => {
      const key = `${TEST_PREFIX}dedup:members`;
      await redis.sadd(key, "url1", "url2", "url3");
      const members = await redis.smembers(key);
      assert.equal(members.length, 3);
      assert.ok(members.includes("url1"));
      assert.ok(members.includes("url2"));
      assert.ok(members.includes("url3"));
    });
  });

  describe("Lua Script Execution", () => {
    it("SCRIPT LOAD and EVALSHA execute a Lua script", async () => {
      // Simple script: returns the sum of two arguments
      const script = "return tonumber(ARGV[1]) + tonumber(ARGV[2])";
      const sha = await redis.script("LOAD", script);
      assert.ok(sha && sha.length === 40, "SHA should be a 40-char hex string");
      const result = await redis.evalsha(sha, 0, 5, 3);
      assert.equal(result, 8);
    });

    it("Lua script can read and write keys", async () => {
      const key = `${TEST_PREFIX}lua:key`;
      const script = `
        redis.call('SET', KEYS[1], ARGV[1])
        return redis.call('GET', KEYS[1])
      `;
      const sha = await redis.script("LOAD", script);
      const result = await redis.evalsha(sha, 1, key, "lua-value");
      assert.equal(result, "lua-value");
    });
  });

  describe("Pipeline Operations", () => {
    it("executes multiple commands in a batch", async () => {
      const pipeline = redis.pipeline();
      pipeline.set(`${TEST_PREFIX}pipe:a`, "1");
      pipeline.set(`${TEST_PREFIX}pipe:b`, "2");
      pipeline.set(`${TEST_PREFIX}pipe:c`, "3");
      pipeline.get(`${TEST_PREFIX}pipe:a`);
      pipeline.get(`${TEST_PREFIX}pipe:b`);
      pipeline.get(`${TEST_PREFIX}pipe:c`);
      const results = await pipeline.exec();

      assert.equal(results.length, 6);
      // SET results
      assert.equal(results[0][1], "OK");
      assert.equal(results[1][1], "OK");
      assert.equal(results[2][1], "OK");
      // GET results
      assert.equal(results[3][1], "1");
      assert.equal(results[4][1], "2");
      assert.equal(results[5][1], "3");
    });

    it("pipeline reports no errors on success", async () => {
      const pipeline = redis.pipeline();
      pipeline.set(`${TEST_PREFIX}pipe:ok`, "value");
      pipeline.get(`${TEST_PREFIX}pipe:ok`);
      const results = await pipeline.exec();

      for (const [err] of results) {
        assert.equal(err, null);
      }
    });
  });
});
