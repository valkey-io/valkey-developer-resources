/**
 * Integration tests for Cookbook 01 — Getting Started.
 *
 * Validates: connect, create index, store chunk, KNN search, similarity score.
 */

import { describe, it, expect, afterAll } from "vitest";
import {
  connect,
  embed,
  ensureIndex,
  upsertChunk,
  knnSearch,
  distanceToSimilarity,
  waitForIndexCount,
  deleteNamespace,
  DIM,
} from "../valkey-lib.js";

const NS = "test_getting_started";

describe("01 — Getting Started", () => {
  let client;

  afterAll(async () => {
    if (client) {
      try {
        await deleteNamespace(client, NS);
      } finally {
        client.close();
      }
    }
  });

  it("connects to Valkey", async () => {
    client = await connect();
    expect(client).toBeDefined();
  });

  it("creates a per-namespace HNSW index", async () => {
    await ensureIndex(client, NS, DIM, { forceFresh: true });
    // If it didn't throw, the index was created successfully.
  });

  it("stores a chunk and indexes it", async () => {
    const text = "Valkey is a high-performance open-source key-value datastore.";
    await upsertChunk(client, NS, "chunk-1", embed(text), { title: "Valkey", text });

    const count = await waitForIndexCount(client, NS, 1);
    expect(count).toBe(1);
  });

  it("retrieves the chunk via KNN search with similarity score", async () => {
    const matches = await knnSearch(client, NS, embed("key value store"), 3);
    expect(matches.length).toBeGreaterThanOrEqual(1);

    const top = matches[0];
    expect(top.text).toContain("Valkey");

    const similarity = distanceToSimilarity(Number(top.score));
    expect(similarity).toBeGreaterThan(0);
    expect(similarity).toBeLessThanOrEqual(1);
  });
});
