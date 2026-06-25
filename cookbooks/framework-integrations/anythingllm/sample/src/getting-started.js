/**
 * 01 - Getting Started — AnythingLLM + Valkey
 *
 * Mirrors the provider's first operations: connect, create a per-namespace
 * HNSW index, store one chunk as a HASH, and retrieve it with a KNN search.
 *
 * Run: npm run getting-started
 */

import {
  connect,
  embed,
  ensureIndex,
  upsertChunk,
  knnSearch,
  distanceToSimilarity,
  waitForIndexCount,
  deleteNamespace,
} from "./valkey-lib.js";

const NS = "getting_started";

async function main() {
  const client = await connect();
  console.log("Connected to Valkey");

  try {
    // Idempotent: start from a clean index so re-runs are deterministic.
    await ensureIndex(client, NS, undefined, { forceFresh: true });
    console.log(`Created index allm_idx_${NS}`);

    const text =
      "Valkey is a high-performance open-source key-value datastore.";
    await upsertChunk(client, NS, "chunk-1", embed(text), { title: "Valkey", text });
    console.log("Stored 1 chunk");

    // Indexing is asynchronous — poll until the chunk is searchable.
    const indexed = await waitForIndexCount(client, NS, 1);
    if (indexed !== 1) throw new Error(`Expected 1 indexed vector, got ${indexed}`);

    const matches = await knnSearch(client, NS, embed("key value store"), 3);
    if (matches.length < 1) throw new Error("Expected at least one KNN match");

    console.log(`Search returned ${matches.length} match(es):`);
    for (const m of matches) {
      const similarity = distanceToSimilarity(Number(m.score));
      console.log(`  (similarity ${similarity.toFixed(3)}): ${m.text}`);
    }

    const top = matches[0];
    if (!top.text.includes("Valkey")) {
      throw new Error("Top match did not contain the stored chunk text");
    }

    console.log("\nGetting-started flow complete.");
  } finally {
    // Clean up demo data, then always close the client.
    try {
      await deleteNamespace(client, NS);
    } finally {
      await client.close();
    }
  }
}

main().catch((e) => {
  console.error("Failed:", e.message);
  console.error(
    "Is Valkey running with the search module? Try: docker compose up -d"
  );
  process.exit(1);
});
