import Redis from "ioredis";

const redis = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
const PREFIX = "firecrawl:sim:";

try {
  console.log("=== Firecrawl Pattern Simulation ===\n");

  // --- Rate Limiting: INCR + EXPIRE ---
  console.log("1. Rate Limiting (INCR + EXPIRE)");
  const rlKey = `${PREFIX}ratelimit:crawl:user123`;
  const count1 = await redis.incr(rlKey);
  const count2 = await redis.incr(rlKey);
  const count3 = await redis.incr(rlKey);
  await redis.expire(rlKey, 60);
  console.log(`   Requests in window: ${count3} (limit would be e.g. 100/min)`);
  console.log(`   TTL: ${await redis.ttl(rlKey)}s\n`);

  // --- Crawl State: Sorted Set with timestamp scores ---
  console.log("2. Crawl State (ZADD / ZRANGE)");
  const crawlKey = `${PREFIX}crawl:pending`;
  const now = Date.now();
  await redis.zadd(crawlKey, now, "https://example.com/page1");
  await redis.zadd(crawlKey, now + 1000, "https://example.com/page2");
  await redis.zadd(crawlKey, now + 2000, "https://example.com/page3");
  const pending = await redis.zrange(crawlKey, 0, -1, "WITHSCORES");
  console.log(`   Pending URLs: ${pending.filter((_, i) => i % 2 === 0).length}`);
  for (let i = 0; i < pending.length; i += 2) {
    console.log(`     ${pending[i]} (score: ${pending[i + 1]})`);
  }
  console.log();

  // --- URL Deduplication: SADD ---
  console.log("3. URL Deduplication (SADD)");
  const dedupKey = `${PREFIX}crawl:visited`;
  const added1 = await redis.sadd(dedupKey, "https://example.com/page1");
  const added2 = await redis.sadd(dedupKey, "https://example.com/page1"); // duplicate
  const added3 = await redis.sadd(dedupKey, "https://example.com/page4");
  console.log(`   First add: ${added1} (1=new)`);
  console.log(`   Duplicate add: ${added2} (0=already seen)`);
  console.log(`   Another new: ${added3} (1=new)`);
  const members = await redis.smembers(dedupKey);
  console.log(`   Visited set size: ${members.length}\n`);

  // --- Caching: SET with EX, GET ---
  console.log("4. Caching (SET with EX / GET)");
  const cacheKey = `${PREFIX}cache:page:example.com/page1`;
  const pageData = JSON.stringify({ html: "<h1>Hello</h1>", crawledAt: new Date().toISOString() });
  await redis.set(cacheKey, pageData, "EX", 2); // 2 second TTL for demo
  const cached = await redis.get(cacheKey);
  console.log(`   Cached: ${cached ? "yes" : "no"} (TTL: ${await redis.ttl(cacheKey)}s)`);
  console.log(`   Waiting 2.5s for expiration...`);
  await new Promise((r) => setTimeout(r, 2500));
  const expired = await redis.get(cacheKey);
  console.log(`   After TTL: ${expired === null ? "expired (null)" : "still cached"}\n`);

  // --- Pipeline: Multi-command batch ---
  console.log("5. Pipeline (multi-command batch)");
  const pipeline = redis.pipeline();
  pipeline.set(`${PREFIX}pipe:a`, "1");
  pipeline.set(`${PREFIX}pipe:b`, "2");
  pipeline.set(`${PREFIX}pipe:c`, "3");
  pipeline.get(`${PREFIX}pipe:a`);
  pipeline.get(`${PREFIX}pipe:b`);
  pipeline.get(`${PREFIX}pipe:c`);
  const results = await pipeline.exec();
  console.log(`   Commands executed: ${results.length}`);
  console.log(`   Results: a=${results[3][1]}, b=${results[4][1]}, c=${results[5][1]}\n`);

  // --- Cleanup ---
  console.log("6. Cleanup");
  const keys = await redis.keys(`${PREFIX}*`);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
  console.log(`   Deleted ${keys.length} keys`);
  console.log("\n=== Simulation Complete ===");
} catch (err) {
  console.error("Simulation failed:", err.message);
  process.exitCode = 1;
} finally {
  redis.disconnect();
}
