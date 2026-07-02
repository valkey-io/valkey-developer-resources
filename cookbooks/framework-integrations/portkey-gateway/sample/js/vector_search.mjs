/**
 * Portkey AI Gateway + Valkey vector search — full CRUD via the Portkey SDK.
 *
 * Corresponds to cookbook: 02-vector-search.md
 *
 * Uses the official `portkey-ai` SDK with the valkey-search provider. The custom
 * vector endpoints are reached through the SDK's generic post/get/delete methods.
 *
 * Tests:
 *   1. Create an HNSW vector index
 *   2. Upsert documents with embeddings
 *   3. KNN vector search
 *   4. Filtered search with TAG
 *   5. Drop index
 *
 * Requirements: Node.js 18+, portkey-ai (npm install)
 */

import "dotenv/config";
import { Portkey } from "portkey-ai";

const GATEWAY_URL = (process.env.GATEWAY_URL || "http://localhost:8787") + "/v1";
const VALKEY_HOST = process.env.VALKEY_CUSTOM_HOST || "valkey://localhost:6379";
const INDEX_NAME = "sample-docs-js";

const client = new Portkey({
  apiKey: "dummy",
  baseURL: GATEWAY_URL,
  provider: "valkey-search",
  customHost: VALKEY_HOST,
});

async function main() {
  console.log("=== Cookbook 02: Vector Search ===\n");

  // Idempotent cleanup so reruns don't fail on "index already exists"
  try {
    await client.delete(`/indexes/${INDEX_NAME}`);
  } catch {
    // index didn't exist — safe to ignore
  }

  // 1. Create index
  const created = await client.post("/indexes", {
    name: INDEX_NAME,
    schema: {
      vector: {
        type: "VECTOR",
        algorithm: "HNSW",
        dims: 3, // toy dimension — use 1536 for text-embedding-ada-002, 768 for MiniLM, etc.
        distance: "COSINE",
      },
      content: { type: "TEXT" },
      source: { type: "TAG" },
    },
    options: { prefix: `${INDEX_NAME}:` },
  });
  if (created.status !== "created") throw new Error(`Create failed: ${JSON.stringify(created)}`);
  console.log("OK: Create index");

  // 2. Upsert documents
  const upserted = await client.post(`/indexes/${INDEX_NAME}/upsert`, {
    documents: [
      { id: "doc1", vector: [0.1, 0.2, 0.3], fields: { content: "Valkey is a high-performance key-value store", source: "docs" } },
      { id: "doc2", vector: [0.4, 0.5, 0.6], fields: { content: "Vector search finds similar items by embedding distance", source: "tutorial" } },
      { id: "doc3", vector: [0.11, 0.21, 0.31], fields: { content: "Valkey supports HNSW and FLAT indexing algorithms", source: "docs" } },
    ],
  });
  const statuses = upserted.data.map((d) => d.status);
  if (!statuses.every((s) => s === "upserted")) throw new Error(`Upsert failed: ${statuses}`);
  console.log("OK: Upserted 3 documents");

  await new Promise((r) => setTimeout(r, 1000)); // allow Valkey Search to index — increase on slow machines

  // 3. KNN search
  const knn = await client.post(`/indexes/${INDEX_NAME}/search`, {
    vector: [0.12, 0.22, 0.32], // distinct from stored docs so ranking is non-trivial
    top_k: 2,
    return_fields: ["content", "source", "__score"],
  });
  if (knn.data[0] !== 2) throw new Error(`Expected 2 KNN results, got ${knn.data[0]}`);
  console.log(`OK: KNN search returned ${knn.data[0]} results`);

  // 4. Filtered search
  const filtered = await client.post(`/indexes/${INDEX_NAME}/search`, {
    vector: [0.12, 0.22, 0.32], // distinct from stored docs so ranking is non-trivial
    top_k: 5,
    filter: "@source:{docs}",
    return_fields: ["content", "__score"],
  });
  if (filtered.data[0] !== 2) throw new Error(`Expected 2 filtered results, got ${filtered.data[0]}`);
  console.log(`OK: Filtered search returned ${filtered.data[0]} results (source:docs only)`);

  // 5. Drop index
  const dropped = await client.delete(`/indexes/${INDEX_NAME}`);
  if (!dropped.deleted) throw new Error("Drop index failed");
  console.log("OK: Dropped index");

  console.log("\nAll tests passed!");
}

main().catch((err) => { console.error("Error:", err.message); process.exit(1); });
