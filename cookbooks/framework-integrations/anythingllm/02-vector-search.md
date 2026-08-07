# Vector Search & Retrieval

> Perform KNN similarity search with bound parameters, convert COSINE distance to similarity scores, apply threshold filtering, and exclude pinned sources from results.

**Intermediate** · Node.js · ~15 min

**Who is this for:** Developers who have completed Getting Started and want to understand how AnythingLLM's retrieval pipeline uses Valkey — scoring, filtering, and source exclusion.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running with the search module (`docker compose up -d`)
- Familiarity with KNN (K-Nearest Neighbours) search concepts

## KNN with Bound Parameters

AnythingLLM's provider never interpolates vectors into the query string. The query vector is always bound via `PARAMS`, which prevents injection and handles binary data correctly:

```javascript
const queryVector = Buffer.from(
  Float32Array.from(embeddingOfQuestion).buffer,
);

const [count, docs] = await GlideFt.search(
  client,
  `allm_idx_${ns}`,
  "*=>[KNN 4 @vector $BLOB AS score]",
  {
    params: [{ key: "BLOB", value: queryVector }],
    returnFields: [
      { fieldIdentifier: "text" },
      { fieldIdentifier: "metadata" },
      { fieldIdentifier: "score" },
    ],
    limit: { offset: 0, count: 4 },
    dialect: 2,
  },
);
```

Key points:

- `$BLOB` is a named parameter bound via `params` — never concatenated
- `AS score` aliases the distance field for easy access in results
- `DIALECT 2` is required for vector queries
- `limit.count` controls the K in KNN (how many neighbours to return)

## COSINE Distance to Similarity

Valkey's COSINE distance metric returns values where:

- **0** = identical vectors (maximum similarity)
- **1** = orthogonal vectors (no similarity)
- **2** = opposite vectors (theoretical maximum distance)

AnythingLLM converts this to a [0, 1] similarity score:

```javascript
function distanceToSimilarity(distance) {
  return Math.max(0, Math.min(1, 1 - distance));
}
```

| Distance | Similarity | Interpretation |
| --- | --- | --- |
| 0.0 | 1.0 | Identical |
| 0.1 | 0.9 | Very similar |
| 0.3 | 0.7 | Related |
| 0.5 | 0.5 | Weakly related |
| 1.0 | 0.0 | Unrelated |

## Threshold Filtering

Not all KNN results are useful. The provider applies a `similarityThreshold` (default `0.25`) to discard low-quality matches:

```javascript
function similarityResponse(matches, { similarityThreshold = 0.25 } = {}) {
  const result = { contextTexts: [], sources: [], scores: [] };

  const scored = matches
    .map((m) => ({
      match: m,
      similarity: distanceToSimilarity(Number(m.score)),
    }))
    .sort((a, b) => b.similarity - a.similarity);

  for (const { match, similarity } of scored) {
    if (similarity < similarityThreshold) continue;

    const metadata = JSON.parse(match.metadata || "{}");
    result.contextTexts.push(metadata.text ?? match.text ?? "");
    result.sources.push({ ...metadata, score: similarity });
    result.scores.push(similarity);
  }
  return result;
}
```

The sort ensures results are returned highest-similarity-first regardless of the order returned by Valkey (KNN ordering is not guaranteed to be stable).

## Pinned-Source Exclusion (filterIdentifiers)

AnythingLLM lets users "pin" documents into a workspace's context window. Pinned documents are always included in the LLM prompt, so they must be excluded from similarity search results to avoid duplication.

Each document gets a stable identifier:

```javascript
function sourceIdentifier(metadata) {
  if (!metadata.title || !metadata.published) {
    return `random-${Math.random()}`; // never matches a filter
  }
  return `title:${metadata.title}-timestamp:${metadata.published}`;
}
```

The provider passes pinned source identifiers as `filterIdentifiers` and skips any chunk whose source matches:

```javascript
function similarityResponse(matches, { filterIdentifiers = [], ...opts } = {}) {
  // ... scoring and sorting ...

  for (const { match, similarity } of scored) {
    const metadata = JSON.parse(match.metadata || "{}");
    const srcId = sourceIdentifier(metadata);

    if (filterIdentifiers.includes(srcId)) continue; // pinned — skip

    result.contextTexts.push(metadata.text);
    // ...
  }
  return result;
}
```

This is application-level filtering, not a Valkey query filter. The KNN search returns K results,
and pinned sources are removed from the response afterward. This means the effective result count
may be less than K when sources are pinned.

## Why Not Use a Valkey Pre-Filter?

Valkey's FT.SEARCH supports hybrid queries with TAG or NUMERIC pre-filters. AnythingLLM chose application-level filtering because:

1. **The filter set changes per-query** — pinned documents vary by conversation
2. **The identifier is a composite string** — not a stored field that can be indexed
3. **The number of pinned sources is small** — typically 1–5, so post-filter cost is negligible
4. **Simplicity** — no extra index fields to maintain

For workloads with hundreds of filter values, consider storing a `source_id` TAG field and using a hybrid query instead.

## Run the Integration Test

```bash
npm test -- --grep "Vector Search"
```

## Configuration Reference

| Parameter | Default | Description |
| --- | --- | --- |
| `topN` (KNN count) | `4` | Number of nearest neighbours to retrieve |
| `similarityThreshold` | `0.25` | Minimum similarity score to include in results |
| `filterIdentifiers` | `[]` | Source identifiers to exclude (pinned documents) |

---

[← Getting Started](./01-getting-started.md) · [Next: Production Operations →](./03-production.md) · [← Back to README](./README.md)
