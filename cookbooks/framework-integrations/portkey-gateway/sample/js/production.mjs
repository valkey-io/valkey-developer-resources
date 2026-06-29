/**
 * Portkey AI Gateway + Valkey production patterns — SDK error handling + monitoring.
 *
 * Corresponds to cookbook: 03-production.md
 *
 * Uses the official `portkey-ai` SDK. Demonstrates production concerns that can be
 * exercised locally: connection-string formats, the SDK's error responses, and
 * monitoring via the index-info endpoint. ElastiCache/TLS deployment is
 * config-only and requires a live AWS cluster, so it is not exercised here.
 *
 * Tests:
 *   1. Connection string formats accepted by the gateway
 *   2. Error handling (404 on missing index, 409 on duplicate) via SDK exceptions
 *   3. Monitoring — index stats via FT.INFO
 *
 * Requirements: Node.js 18+, portkey-ai (npm install)
 */

import { Portkey } from "portkey-ai";

const GATEWAY_URL = (process.env.GATEWAY_URL || "http://localhost:8787") + "/v1";
const VALKEY_HOST = process.env.VALKEY_CUSTOM_HOST || "valkey://localhost:6379";
const INDEX_NAME = "prod-docs-js";

function makeClient(customHost = VALKEY_HOST) {
  return new Portkey({
    apiKey: "dummy",
    baseURL: GATEWAY_URL,
    provider: "valkey-search",
    customHost,
  });
}

async function testConnectionFormats() {
  // The custom-host validator accepts the format; a real connection only succeeds
  // for reachable endpoints. A 503 still proves the format was ACCEPTED — only a
  // 400 means rejection. Multi-seed cluster strings are valid only for the
  // VALKEY_CONNECTION_STRING env var, not this header, so not tested here.
  const formats = [
    "valkey://localhost:6379",             // plaintext, connects
    "valkeys://localhost:6379",            // TLS scheme, accepted (503 locally)
    "redis://localhost:6379",              // redis scheme, connects
    "rediss://localhost:6379",             // redis TLS scheme, accepted (503 locally)
    "valkey://localhost:6379?cluster=true",// cluster flag, accepted (503 locally)
    "valkey://:pass@localhost:6379",       // password auth, accepted
  ];
  for (const fmt of formats) {
    const client = makeClient(fmt);
    try {
      await client.post("/indexes", { name: "fmt-prod-js", schema: { x: { type: "TEXT" } } });
      await client.delete("/indexes/fmt-prod-js");
      console.log(`OK: format accepted (connected) -> ${fmt}`);
    } catch (e) {
      if (e.status === 400) throw new Error(`Format rejected by validator: ${fmt}`);
      console.log(`OK: format accepted (${e.status}) -> ${fmt}`);
    }
  }
}

async function testErrorHandling() {
  const client = makeClient();

  // 404 — search a non-existent index
  try {
    await client.post("/indexes/does-not-exist/search", { vector: [0.1, 0.2, 0.3], top_k: 1 });
    throw new Error("Expected 404 for missing index");
  } catch (e) {
    if (e.status !== 404) throw e;
    console.log("OK: missing index returns 404 (handled gracefully)");
  }

  // 409 — create the same index twice
  const body = {
    name: INDEX_NAME,
    schema: { vector: { type: "VECTOR", algorithm: "HNSW", dims: 3, distance: "COSINE" } },
    options: { prefix: `${INDEX_NAME}:` },
  };
  await client.post("/indexes", body);
  try {
    await client.post("/indexes", body);
    throw new Error("Expected 409 for duplicate index");
  } catch (e) {
    if (e.status !== 409) throw e;
    console.log("OK: duplicate index returns 409 (handled gracefully)");
  }
}

async function testMonitoring() {
  const client = makeClient();
  const info = await client.get(`/indexes/${INDEX_NAME}`);
  if (!("info" in info)) throw new Error("Expected index info in response");
  console.log("OK: retrieved index stats via FT.INFO (monitoring)");
  await client.delete(`/indexes/${INDEX_NAME}`);
}

async function main() {
  console.log("=== Cookbook 03: Production Patterns ===\n");
  await testConnectionFormats();
  await testErrorHandling();
  await testMonitoring();
  console.log("\nAll tests passed!");
}

main().catch((err) => { console.error("Error:", err.message); process.exit(1); });
