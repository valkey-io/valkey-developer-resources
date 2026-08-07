/**
 * Integration tests for Cookbook 02 — Vector Search & Retrieval.
 *
 * Validates: multi-chunk ingest, KNN with threshold filtering,
 * pinned-source exclusion via filterIdentifiers.
 */

import { describe, it, expect, afterAll } from "vitest";
import {
  connect,
  embed,
  ensureIndex,
  upsertChunk,
  knnSearch,
  distanceToSimilarity,
  sourceIdentifier,
  waitForIndexCount,
  deleteNamespace,
  DIM,
} from "../valkey-lib.js";

const NS = "test_vector_search";

const documents = [
  {
    id: "d1",
    title: "Valkey",
    published: "2024-01-01",
    text: "Valkey is a high-performance open-source key-value datastore.",
  },
  {
    id: "d2",
    title: "Jazz",
    published: "2024-02-02",
    text: "Jazz is a music genre that originated in New Orleans.",
  },
  {
    id: "d3",
    title: "HNSW",
    published: "2024-03-03",
    text: "HNSW is a graph index for fast approximate nearest-neighbour search.",
  },
];

/**
 * Mirrors AnythingLLM's similarityResponse(): score, sort, threshold-filter,
 * and pinned-source exclusion.
 */
function similarityResponse(matches, { similarityThreshold = 0.25, filterIdentifiers = [] } = {}) {
  const result = { contextTexts: [], sources: [], scores: [] };
  const scored = matches
    .map((m) => ({ match: m, similarity: distanceToSimilarity(Number(m.score)) }))
    .sort((a, b) => b.similarity - a.similarity);

  for (const { match, similarity } of scored) {
    if (similarity < similarityThreshold) continue;
    let metadata = {};
    try {
      metadata = match.metadata ? JSON.parse(match.metadata) : {};
    } catch {
      metadata = {};
    }
    if (filterIdentifiers.includes(sourceIdentifier(metadata))) continue;
    result.contextTexts.push(metadata.text ?? match.text ?? "");
    result.sources.push({ ...metadata, score: similarity });
    result.scores.push(similarity);
  }
  return result;
}

describe("02 — Vector Search & Retrieval", () => {
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

  it("connects and ingests multiple chunks", async () => {
    client = await connect();
    await ensureIndex(client, NS, DIM, { forceFresh: true });

    for (const doc of documents) {
      await upsertChunk(client, NS, doc.id, embed(doc.text), doc);
    }

    const count = await waitForIndexCount(client, NS, documents.length);
    expect(count).toBe(documents.length);
  });

  it("returns ranked results above a similarity threshold", async () => {
    const matches = await knnSearch(client, NS, embed("in-memory key value database"), 4);
    // Use a very low threshold — the toy embedder produces coarse vectors.
    const response = similarityResponse(matches, { similarityThreshold: 0.01 });
    expect(response.contextTexts.length).toBeGreaterThanOrEqual(1);
    expect(response.scores[0]).toBeGreaterThanOrEqual(response.scores[response.scores.length - 1]);
  });

  it("excludes pinned sources via filterIdentifiers", async () => {
    const matches = await knnSearch(client, NS, embed("in-memory key value database"), 4);
    const baseline = similarityResponse(matches, { similarityThreshold: 0.01 });
    expect(baseline.contextTexts.length).toBeGreaterThanOrEqual(2);

    const top = baseline.sources[0];
    const pinnedId = sourceIdentifier({ title: top.title, published: top.published });
    const filtered = similarityResponse(matches, {
      similarityThreshold: 0.01,
      filterIdentifiers: [pinnedId],
    });

    expect(filtered.contextTexts).not.toContain(baseline.contextTexts[0]);
    expect(filtered.contextTexts.length).toBeGreaterThanOrEqual(1);
  });
});
