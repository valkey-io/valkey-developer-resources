/**
 * Integration tests for Cookbook 03 — Production Operations.
 *
 * Validates: connection probe, dimension-mismatch guard, namespace deletion
 * (no orphan keys), and full reset.
 */

import { describe, it, expect, afterAll } from "vitest";
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
  deleteKeys,
  deleteNamespace,
  reset,
  toStr,
} from "../valkey-lib.js";

const NS = "test_production";

/**
 * Read an index's configured vector dimension from a parsed FT.INFO reply.
 * Flatten the whole reply into a token stream and find the value after a
 * "dimensions" or "dim" key.
 */
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

/**
 * Reject a write whose dimension would not match an existing index.
 */
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
        `incoming vectors are ${dims}-dim.`,
    );
  }
}

describe("03 — Production Operations", () => {
  let client;

  afterAll(async () => {
    if (client) {
      try {
        await reset(client);
      } finally {
        client.close();
      }
    }
  });

  it("validates connection with a PING probe", async () => {
    let probe = null;
    try {
      probe = await GlideClient.createClient(buildConfig());
      const pong = await probe.ping();
      expect(toStr(pong)).toBe("PONG");
    } finally {
      if (probe) probe.close();
    }
  });

  it("connects and ingests test data", async () => {
    client = await connect();
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
    expect(count).toBe(2);
  });

  it("rejects a dimension-mismatched write", async () => {
    await expect(
      assertDimensionCompatible(client, NS, DIM + 8),
    ).rejects.toThrow("Dimension mismatch");
  });

  it("deletes a namespace leaving no orphan keys", async () => {
    await deleteNamespace(client, NS);
    const orphans = await scanKeys(client, `${keyPrefix(NS)}*`);
    expect(orphans.length).toBe(0);
    expect(await namespaceCount(client, NS)).toBe(0);
  });

  it("full reset clears all managed indexes and keys", async () => {
    // Re-create a namespace to verify reset clears it.
    await ensureIndex(client, "reset_check", DIM, { forceFresh: true });
    await upsertChunk(client, "reset_check", "r1", embed("reset test"), {
      text: "reset test",
    });
    await waitForIndexCount(client, "reset_check", 1);

    await reset(client);

    const remaining = await scanKeys(client, "allm:*");
    expect(remaining.length).toBe(0);
  });
});
