/**
 * 02 - Vector Search & Retrieval — AnythingLLM + Valkey
 *
 * Reproduces the provider's retrieval path: KNN search with a bound query
 * vector, COSINE distance -> similarity, threshold + topN filtering, and
 * pinned-source exclusion via filterIdentifiers.
 *
 * Run: npm run vector-search
 */

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
} from "./valkey-lib.js";

const NS = "search_demo";

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

// Score, sort highest-first, threshold, and drop pinned sources — the body of
// the provider's similarityResponse().
function similarityResponse(matches, { similarityThreshold = 0.25, filterIdentifiers = [] } = {}) {
  const result = { contextTexts: [], sources: [], scores: [] };
  const scored = matches
    .map((m) => ({ match: m, similarity: distanceToSimilarity(Number(m.score)) }))
    .sort((a, b) => b.similarity - a.similarity); // KNN order isn't guaranteed

  for (const { match, similarity } of scored) {
    if (similarity < similarityThreshold) continue; // 0.25 = provider default
    let metadata = {};
    try {
      metadata = match.metadata ? JSON.parse(match.metadata) : {};
    } catch {
      metadata = {}; // tolerate a malformed metadata field
    }
    if (filterIdentifiers.includes(sourceIdentifier(metadata))) continue; // pinned
    result.contextTexts.push(metadata.text ?? match.text ?? "");
    result.sources.push({ ...metadata, score: similarity });
    result.scores.push(similarity);
  }
  return result;
}

async function main() {
  const client = await connect();
  console.log("Connected to Valkey");

  try {
    await ensureIndex(client, NS, undefined, { forceFresh: true });
    // Demo loop of single-key HSETs; batch with the GLIDE pipeline API at scale.
    for (const doc of documents) {
      await upsertChunk(client, NS, doc.id, embed(doc.text), doc);
    }
    const indexed = await waitForIndexCount(client, NS, documents.length);
    if (indexed !== documents.length) {
      throw new Error(`Expected ${documents.length} indexed vectors, got ${indexed}`);
    }
    console.log(`Ingested ${documents.length} chunks`);

    // Use a low threshold here: the toy embedder produces coarse vectors, so
    // real similarity scores are modest. Tune for your real embedding model.
    const threshold = 0.1;
    const matches = await knnSearch(client, NS, embed("in-memory key value database"), 4);

    const baseline = similarityResponse(matches, { similarityThreshold: threshold });
    if (baseline.contextTexts.length < 2) {
      throw new Error("Expected at least two matches above the threshold for the pinning demo");
    }
    const top = baseline.sources[0];
    console.log(
      `Top context: "${baseline.contextTexts[0]}" (similarity ${baseline.scores[0].toFixed(3)})`
    );

    // Pin the top-ranked document and confirm its chunk drops out of the
    // results. (The toy embedder isn't semantic, so we pin whatever ranks
    // first rather than asserting a specific document does.)
    const pinnedId = sourceIdentifier({ title: top.title, published: top.published });
    const filtered = similarityResponse(matches, {
      similarityThreshold: threshold,
      filterIdentifiers: [pinnedId],
    });
    if (filtered.contextTexts.includes(baseline.contextTexts[0])) {
      throw new Error("Pinned top chunk should have been excluded");
    }
    if (filtered.contextTexts.length === 0) {
      throw new Error("Expected a next-best match after pinning the top result");
    }
    console.log(`After pinning "${top.title}", top context: "${filtered.contextTexts[0]}"`);

    console.log("\nVector-search flow complete.");
  } finally {
    try {
      await deleteNamespace(client, NS);
    } finally {
      await client.close();
    }
  }
}

main().catch((e) => {
  console.error("Failed:", e.message);
  console.error("Is Valkey running with the search module? Try: docker compose up -d");
  process.exit(1);
});
