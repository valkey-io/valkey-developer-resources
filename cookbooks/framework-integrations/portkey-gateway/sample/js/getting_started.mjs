/**
 * Portkey AI Gateway + Valkey getting started — cache LLM responses with the SDK.
 *
 * Corresponds to cookbook: 01-getting-started.md
 *
 * Uses the official `portkey-ai` SDK pointed at a local gateway backed by Valkey.
 *
 * Tests:
 *   1. Build a Portkey client targeting the gateway
 *   2. Verify the gateway is reachable and Valkey is the active backend
 *   3. (Optional) Two identical cached chat completions showing MISS -> HIT.
 *      Runs only when OPENAI_API_KEY (or PROVIDER_API_KEY) is set.
 *
 * Requirements: Node.js 18+, portkey-ai (npm install)
 */

import "dotenv/config";
import { Portkey } from "portkey-ai";

const GATEWAY_URL = (process.env.GATEWAY_URL || "http://localhost:8787") + "/v1";
const VALKEY_HOST = process.env.VALKEY_CUSTOM_HOST || "valkey://localhost:6379";
// Cached-completion demo provider. Requires OPENAI_API_KEY by default.
// Set PROVIDER to use a different provider (e.g. anthropic, bedrock).
const PROVIDER = process.env.PROVIDER || "openai";
const PROVIDER_API_KEY = process.env.PROVIDER_API_KEY || process.env.OPENAI_API_KEY;
const MODEL = process.env.MODEL || "gpt-4o-mini";

async function verifyValkeyBackend() {
  // A successful index round-trip through the SDK proves the gateway is
  // connected to Valkey.
  const client = new Portkey({
    apiKey: "dummy",
    baseURL: GATEWAY_URL,
    provider: "valkey-search",
    customHost: VALKEY_HOST,
  });

  await client.post("/indexes", {
    name: "gs-probe-js",
    schema: { content: { type: "TEXT" } },
    options: { prefix: "gs-probe-js:" },
  });
  const info = await client.get("/indexes/gs-probe-js");
  if (info.object !== "index") throw new Error(`Unexpected index info: ${JSON.stringify(info)}`);
  await client.delete("/indexes/gs-probe-js");
  console.log("OK: SDK reached the gateway; Valkey is the active backend");
}

async function demoCachedCompletion() {
  // Requires the gateway built with `"cache": true` in conf.json.
  // Set OPENAI_API_KEY (or PROVIDER + PROVIDER_API_KEY for other providers).
  let client;
  if (PROVIDER_API_KEY) {
    client = new Portkey({
      apiKey: "dummy",
      baseURL: GATEWAY_URL,
      provider: PROVIDER,
      Authorization: `Bearer ${PROVIDER_API_KEY}`,
      config: { cache: { mode: "simple" } },
    });
  } else {
    console.log("SKIP: set OPENAI_API_KEY (or PROVIDER_API_KEY) to run the cached completion demo");
    return;
  }

  // A unique prompt per run so the first call is always a fresh MISS
  const messages = [{ role: "user", content: `Reply with one word. Token ${Date.now()}` }];

  // First call — cache MISS, hits the LLM and stores the response in Valkey
  let t0 = Date.now();
  const first = await client.chat.completions.create({ model: MODEL, messages });
  const missMs = Date.now() - t0;
  if (!first.choices[0].message.content) throw new Error("Empty completion on first call");
  console.log(`OK: first call (MISS) ${missMs}ms`);

  // Second identical call — cache HIT, served from Valkey
  t0 = Date.now();
  const second = await client.chat.completions.create({ model: MODEL, messages });
  const hitMs = Date.now() - t0;
  if (!second.choices[0].message.content) throw new Error("Empty completion on second call");
  if (hitMs >= missMs) throw new Error(`Cache HIT (${hitMs}ms) not faster than MISS (${missMs}ms)`);
  console.log(`OK: second call (HIT) ${hitMs}ms — served from Valkey`);
}

async function main() {
  console.log("=== Cookbook 01: Getting Started ===\n");
  await verifyValkeyBackend();
  await demoCachedCompletion();
  console.log("\nAll tests passed!");
}

main().catch((err) => { console.error("Error:", err.message); process.exit(1); });
