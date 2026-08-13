import Redis from "ioredis";
import { createHash } from "node:crypto";

const client = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
const PREFIX = "helicone:sim:";

try {
  console.log("=== Helicone Pattern Simulation ===\n");

  // --- 1. KV Cache: SET PX / GET ---
  console.log("1. KV Cache (SET PX / GET)");
  const kvKey = `${PREFIX}kv:response`;
  const kvValue = JSON.stringify({ model: "gpt-4o", tokens: 512, cached: true });
  await client.set(kvKey, kvValue, "PX", 5000);
  const kvResult = await client.get(kvKey);
  console.log(`   Stored:    ${kvValue}`);
  console.log(`   Retrieved: ${kvResult}`);
  console.log(`   TTL: ~${await client.pttl(kvKey)}ms remaining\n`);

  // --- 2. Proxy Rate Limiter: GET / SET EX (sliding window JSON array) ---
  console.log("2. Proxy Rate Limiter (GET / SET EX — sliding window)");
  const rlKey = `${PREFIX}rl:proxy:user123_3`;
  const now = Date.now();
  const windowMs = 60_000;
  const raw = await client.get(rlKey);
  let entries = raw ? JSON.parse(raw) : [];
  entries = entries.filter((e) => e.timestamp >= now - windowMs);
  entries.push({ timestamp: now, unit: 1 });
  await client.set(rlKey, JSON.stringify(entries), "EX", 60);
  console.log(`   Window entries: ${entries.length} (limit e.g. 10/min)`);
  console.log(`   TTL: ${await client.ttl(rlKey)}s\n`);

  // --- 3. Lua Rate Limiter: SCRIPT LOAD / EVALSHA ---
  console.log("3. Lua Rate Limiter (SCRIPT LOAD / EVALSHA)");
  const luaScript = `
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
`.trim();
  const sha = await client.call("SCRIPT", "LOAD", luaScript);
  const luaKey = `${PREFIX}rl:lua:org1`;
  const [count, ttlMs] = await client.evalsha(sha, 1, luaKey, "60000");
  console.log(`   Script SHA: ${sha}`);
  console.log(`   Request count: ${count}, window TTL: ~${ttlMs}ms\n`);

  // --- 4. Usage Cache: GET / SET EX (cache-aside) ---
  console.log("4. Usage Cache (GET / SET EX — cache-aside)");
  const usageKey = `${PREFIX}usage:org1hash`;
  const miss = await client.get(usageKey);
  console.log(`   Cache miss: ${miss}`);
  // On miss, compute from DB then cache for 1 hour
  await client.set(usageKey, "true", "EX", 3600);
  const hit = await client.get(usageKey);
  console.log(`   Cache hit:  ${hit} (TTL: ${await client.ttl(usageKey)}s)\n`);

  // --- 5. Encrypted Key Cache: GET / SET EX (SHA-256 hashed key) ---
  console.log("5. Encrypted Key Cache (GET / SET EX — hashed key)");
  const plainKey = "api-key:openai-provider";
  // Key is hashed with SHA-256 before storage; app handles AES-GCM encryption of the value
  const hashedKey = `${PREFIX}enc:${createHash("sha256").update(plainKey).digest("hex")}`;
  const encryptedValue = '{"iv":"<12-byte-iv>","content":"<AES-GCM ciphertext>"}';
  await client.set(hashedKey, encryptedValue, "EX", 600);
  const stored = await client.get(hashedKey);
  console.log(`   Plain key:    ${plainKey}`);
  console.log(`   Hashed key:   ${hashedKey.replace(PREFIX + "enc:", "").slice(0, 16)}...`);
  console.log(`   Retrieved:    ${stored !== null ? "yes" : "no"} (TTL: ${await client.ttl(hashedKey)}s)\n`);

  // --- Cleanup ---
  const keys = await client.keys(`${PREFIX}*`);
  if (keys.length > 0) await client.del(...keys);
  console.log(`Cleanup: deleted ${keys.length} keys`);
  console.log("\n=== Simulation Complete ===");
} catch (err) {
  console.error("Simulation failed:", err.message);
  process.exitCode = 1;
} finally {
  client.disconnect();
}
