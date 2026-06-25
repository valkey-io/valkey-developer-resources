# Vector Search & Retrieval with AnythingLLM + Valkey

**Intermediate** · JavaScript · ~20 min

## What You'll Build

[Getting Started](01-getting-started.md) created an index and ran one KNN search. This cookbook reproduces the full retrieval path AnythingLLM uses to answer a chat question — `performSimilaritySearch` → `similarityResponse`:

* **Bound KNN queries** — the query vector travels as a `PARAMS` binding, never string-interpolated
* **COSINE distance → similarity** — convert and clamp the raw distance into a `[0, 1]` score
* **Threshold + topN filtering** — drop weak matches below `similarityThreshold`
* **Pinned-source exclusion** — skip chunks whose parent document the user pinned (`filterIdentifiers`)

It assumes Valkey is running with the search module and you have `@valkey/valkey-glide@2.4.1` installed (see [01 - Getting Started](01-getting-started.md)).

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments — see [03 - Production Operations](03-production.md).

## Step 1: Ingest a few chunks

We reuse the toy embedder and the FLOAT32 encoder from cookbook 01. Storing several distinct chunks gives the KNN query something to rank.

```javascript
import { GlideClient, GlideFt, RequestError } from "@valkey/valkey-glide";

const DIM = 8; // dimension of the toy embedder (real models output e.g. 1536)
function embed(text = "") {
  const v = new Array(DIM).fill(0);
  for (let i = 0; i < text.length; i++) v[i % DIM] += text.charCodeAt(i);
  const mag = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
  return v.map((x) => x / mag);
}
const floatToBuffer = (values) => Buffer.from(Float32Array.from(values).buffer);
const toStr = (v) => (Buffer.isBuffer(v) ? v.toString("utf-8") : `${v}`);

const namespace = "search_demo";
const indexName = `allm_idx_${namespace}`;
const keyPrefix = `allm:${namespace}:`;

// `client` is a connected GlideClient (see cookbook 01 for createClient).
async function ingest(client, docs) {
  try {
    await GlideFt.dropindex(client, indexName); // idempotent: clean re-runs
  } catch (e) {
    if (!(e instanceof RequestError)) throw e; // RequestError == index absent
  }
  await GlideFt.create(
    client,
    indexName,
    [{
      type: "VECTOR",
      name: "vector",
      attributes: { algorithm: "HNSW", type: "FLOAT32", dimensions: DIM, distanceMetric: "COSINE" },
    }],
    { dataType: "HASH", prefixes: [keyPrefix] }
  );

  // Demo loop of single-key HSETs. For bulk ingestion at scale, batch writes
  // with the GLIDE Batch/pipeline API to avoid one round trip per chunk.
  for (const doc of docs) {
    await client.hset(`${keyPrefix}${doc.id}`, {
      vector: floatToBuffer(embed(doc.text)),
      text: doc.text,
      metadata: JSON.stringify(doc),
    });
  }
}
```

## Step 2: Search with a bound query vector

The query string uses `valkey-search` KNN syntax. The vector is passed as the `$BLOB` parameter, so it is never concatenated into the query text.

```javascript
// `client`, `indexName`, embed/floatToBuffer/toStr come from Step 1.
async function rawSearch(client, queryText, topN = 4) {
  const [count, docs] = await GlideFt.search(
    client,
    indexName,
    // `=>` separates the (here hardcoded) pre-filter from the KNN clause.
    `*=>[KNN ${topN} @vector $BLOB AS score]`,
    {
      params: [{ key: "BLOB", value: floatToBuffer(embed(queryText)) }],
      returnFields: [
        { fieldIdentifier: "text" },
        { fieldIdentifier: "metadata" },
        { fieldIdentifier: "score" },
      ],
      limit: { offset: 0, count: topN },
      dialect: 2, // valkey-search requires DIALECT 2 for vector queries
    }
  );
  // Flatten each doc's [{key,value}, ...] field list into a plain object.
  return docs.map((doc) =>
    Object.fromEntries(doc.value.map((f) => [toStr(f.key), toStr(f.value)]))
  );
}
```

> **Query-injection note:** the KNN query above is safe because the filter is hardcoded (`*`) and the vector is a bound parameter (`$BLOB`). Never interpolate raw user input into the query string — the `=>` token separates the pre-filter from the KNN clause, so an attacker who controls that text could alter the search semantics. Cookbook 03 and the [OpenAI cookbook](../openai/02-vector-search.md) cover guarded TAG pre-filters.

## Step 3: Score, sort, and threshold

`valkey-search` returns the COSINE **distance** in `score`. AnythingLLM converts it to a similarity, sorts highest-first (KNN results are not guaranteed sorted, and `SORTBY` is rejected on a KNN query), then drops anything below `similarityThreshold`.

```javascript
// Convert a COSINE distance into a clamped [0, 1] similarity. distance 0 -> 1.0
// (identical direction); distance 1 -> 0.0 (orthogonal). Returns 0 for junk.
function distanceToSimilarity(distance) {
  if (distance === null || Number.isNaN(distance)) return 0;
  return Math.max(0, Math.min(1, 1 - distance));
}

function rankAndFilter(matches, { similarityThreshold = 0.25 } = {}) {
  return matches
    .map((m) => ({ match: m, similarity: distanceToSimilarity(Number(m.score)) }))
    .sort((a, b) => b.similarity - a.similarity) // highest similarity first
    .filter((s) => s.similarity >= similarityThreshold); // 0.25 = provider default
}
```

`similarityThreshold` defaults to `0.25` in AnythingLLM (a chunk must be at least 25% similar to be handed to the LLM). Raise it for stricter retrieval, lower it to recall more context.

## Step 4: Exclude pinned sources

When a user "pins" a document in a workspace, AnythingLLM injects it into context directly and asks the vector store to **exclude** its chunks from KNN results (otherwise they would appear twice). It identifies a parent document by a `sourceIdentifier` built from the chunk's metadata, and skips any match whose identifier is in `filterIdentifiers`.

```javascript
// Mirror of AnythingLLM's sourceIdentifier: derives a stable id for a chunk's
// PARENT document from its metadata. Chunks without title+published get a
// random id (so they are never accidentally filtered).
function sourceIdentifier(meta = {}) {
  if (!meta.title || !meta.published) return `random-${Math.random()}`;
  return `title:${meta.title}-timestamp:${meta.published}`;
}

function similarityResponse(matches, { similarityThreshold = 0.25, filterIdentifiers = [] } = {}) {
  const result = { contextTexts: [], sources: [], scores: [] };
  for (const { match, similarity } of rankAndFilter(matches, { similarityThreshold })) {
    let metadata = {};
    try {
      metadata = match.metadata ? JSON.parse(match.metadata) : {};
    } catch {
      metadata = {}; // tolerate a malformed metadata field rather than crash
    }
    if (filterIdentifiers.includes(sourceIdentifier(metadata))) continue; // pinned -> skip
    result.contextTexts.push(metadata.text ?? match.text ?? "");
    result.sources.push({ ...metadata, score: similarity });
    result.scores.push(similarity);
  }
  return result;
}
```

## Step 5: Put it together

```javascript
// `client` is a connected GlideClient (cookbook 01). All helpers from Steps 1-4.
const documents = [
  { id: "d1", title: "Valkey", published: "2024-01-01",
    text: "Valkey is a high-performance open-source key-value datastore." },
  { id: "d2", title: "Jazz", published: "2024-02-02",
    text: "Jazz is a music genre that originated in New Orleans." },
  { id: "d3", title: "HNSW", published: "2024-03-03",
    text: "HNSW is a graph index for fast approximate nearest-neighbour search." },
];

await ingest(client, documents);

// valkey-search indexing is asynchronous; in a real app poll FT.INFO num_docs
// (see cookbook 03) instead of assuming the chunk is immediately searchable.
const matches = await rawSearch(client, "in-memory key value database", 4);

// The toy embedder produces coarse vectors, so we use a low threshold here.
const { contextTexts, sources, scores } = similarityResponse(matches, { similarityThreshold: 0.1 });
console.log("Top context:", contextTexts[0], `(similarity ${scores[0]?.toFixed(3)})`);

// Pin the top-ranked document and confirm its chunk drops out of the results.
const top = sources[0];
const pinnedId = sourceIdentifier({ title: top.title, published: top.published });
const filtered = similarityResponse(matches, { similarityThreshold: 0.1, filterIdentifiers: [pinnedId] });
console.log(`After pinning "${top.title}", top context:`, filtered.contextTexts[0]);
```

The first query ranks the chunks by similarity to the question. After adding the top match's identifier to `filterIdentifiers`, that chunk is skipped and the next-best match surfaces instead — exactly how pinned documents are kept out of the retrieved context. The full runnable version lives in [`sample/src/vector-search.js`](sample/src/vector-search.js).

## How It Works Under the Hood

| Operation | Valkey Command | What It Does |
|-----------|---------------|--------------|
| KNN search | `FT.SEARCH idx "*=>[KNN k @vector $BLOB AS score]" PARAMS 2 BLOB <f32le> DIALECT 2 RETURN 3 text metadata score LIMIT 0 k` | Rank the index by similarity to the bound query vector |
| Distance → similarity | (client-side) | `similarity = clamp(1 - cosineDistance, 0, 1)` |
| Threshold filter | (client-side) | Drop matches with `similarity < similarityThreshold` |
| Pinned exclusion | (client-side) | Skip matches whose `sourceIdentifier` is in `filterIdentifiers` |

The KNN ranking happens in Valkey; scoring, sorting, thresholding, and pinned-source exclusion happen client-side because they depend on AnythingLLM's per-request parameters.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Search returns 0 results right after ingest | Indexing is asynchronous; poll `FT.INFO num_docs` until it reaches the expected count (see [03](03-production.md)). |
| `Syntax error` on the query | Ensure `dialect: 2` is set — vector queries require DIALECT 2. |
| Everything filtered out | Your `similarityThreshold` is too high for the toy embedder; lower it (e.g. `0.1`) to confirm the pipeline, then tune. |
| Pinned doc still appears | The chunk's `metadata` must contain the same `title` + `published` used to build the pinned identifier. |

[← Back: 01 Getting Started](01-getting-started.md) · [Next: 03 Production Operations →](03-production.md)
