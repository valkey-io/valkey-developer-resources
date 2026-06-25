/**
 * 03 - Production Operations — AnythingLLM + Valkey
 *
 * Demonstrates the provider's operational machinery: the connection probe,
 * the embedding-dimension guard, namespace counting/deletion, bounded SCAN
 * cleanup, and a full reset.
 *
 * Run: npm run production
 */

import { GlideClient, GlideFt, RequestError } from "@valkey/valkey-glide";
import {
  buildConfig,
  connect,
  embed,
  DIM,
  indexName,
  keyPrefix,
  ensureIndex,
  upsertChunk,
  namespaceCount,
  waitForIndexCount,
  scanKeys,
  deleteNamespace,
  reset,
} from "./valkey-lib.js";

const NS = "prod_demo";

// Validate a connection, always closing the probe client even on failure.
async function validateConnection(config) {
  let probe = null;
  try {
    probe = await GlideClient.createClient(config);
    await probe.ping();
    await probe.close();
    return { success: true, error: null };
  } catch (e) {
    if (probe) {
      try {
        await probe.close();
      } catch {
        /* ignore close failures during cleanup */
      }
    }
    return { success: false, error: e.message };
  }
}

// Read an index's configured vector dimension from a parsed FT.INFO reply.
// valkey-search nests `dimensions` inside the per-field attribute list and the
// exact shape varies by version, so flatten the whole reply into a token
// stream and take the value following a `dimensions`/`dim` key.
function indexDimension(info) {
  const tokens = [];
  const flatten = (node) => {
    if (Array.isArray(node)) {
      for (const item of node) flatten(item);
    } else if (node && typeof node === "object" && !Buffer.isBuffer(node)) {
      for (const [k, v] of Object.entries(node)) {
        tokens.push(k);
        flatten(v);
      }
    } else {
      tokens.push(Buffer.isBuffer(node) ? node.toString("utf-8") : `${node}`);
    }
  };
  flatten(info);
  for (let i = 0; i < tokens.length - 1; i++) {
    const key = tokens[i].toLowerCase();
    if (key === "dimensions" || key === "dim") {
      const dim = Number(tokens[i + 1]);
      if (Number.isFinite(dim) && dim > 0) return dim;
    }
  }
  return null;
}

// Reject a write whose dimension would not match an existing index.
async function assertDimensionCompatible(client, ns, dims) {
  let info = null;
  try {
    info = await GlideFt.info(client, indexName(ns));
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
    return; // index absent — nothing to check
  }
  const existing = indexDimension(info);
  if (dims && existing && existing !== dims) {
    throw new Error(
      `Dimension mismatch for ${indexName(ns)}: index is ${existing}-dim but ` +
        `incoming vectors are ${dims}-dim. Reset the vector store after ` +
        `changing the embedding model.`
    );
  }
}

async function main() {
  // 1. Connection probe (the admin "save settings" path).
  const probe = await validateConnection(buildConfig());
  if (!probe.success) throw new Error(`Connection probe failed: ${probe.error}`);
  console.log("Connection probe OK");

  const client = await connect();
  try {
    // 2. Ingest a couple of chunks into a namespace.
    await ensureIndex(client, NS, DIM, { forceFresh: true });
    await upsertChunk(client, NS, "c1", embed("alpha document about databases"), {
      title: "Alpha",
      published: "2024-01-01",
      text: "alpha document about databases",
    });
    await upsertChunk(client, NS, "c2", embed("beta document about music"), {
      title: "Beta",
      published: "2024-02-02",
      text: "beta document about music",
    });
    const count = await waitForIndexCount(client, NS, 2);
    if (count !== 2) throw new Error(`Expected 2 vectors, got ${count}`);
    console.log(`namespaceCount(${NS}) = ${await namespaceCount(client, NS)}`);

    // 3. Dimension guard: a wrong-dimension write must be rejected.
    let rejected = false;
    try {
      await assertDimensionCompatible(client, NS, DIM + 8); // pretend new model
    } catch {
      rejected = true;
    }
    if (!rejected) throw new Error("Dimension guard should have rejected a mismatch");
    console.log("Dimension guard rejected a mismatched-dimension write");

    // 4. Delete the namespace and confirm no orphan keys remain.
    await deleteNamespace(client, NS);
    const orphans = await scanKeys(client, `${keyPrefix(NS)}*`);
    if (orphans.length !== 0) throw new Error(`Expected 0 orphan keys, got ${orphans.length}`);
    if ((await namespaceCount(client, NS)) !== 0) {
      throw new Error("Namespace should report 0 after deletion");
    }
    console.log("Namespace deleted — index dropped and chunk keys swept");

    // 5. Full reset clears every managed index and key.
    await ensureIndex(client, "reset_check", DIM, { forceFresh: true });
    await reset(client);
    const remaining = await scanKeys(client, "allm:*");
    if (remaining.length !== 0) throw new Error(`reset left ${remaining.length} keys`);
    console.log("Reset cleared all managed indexes and keys");

    console.log("\nProduction-operations flow complete.");
  } finally {
    await client.close();
  }
}

main().catch((e) => {
  console.error("Failed:", e.message);
  console.error("Is Valkey running with the search module? Try: docker compose up -d");
  process.exit(1);
});
