/**
 * Shared helpers for the AnythingLLM + Valkey cookbook samples.
 *
 * These mirror the AnythingLLM Valkey provider's design (per-namespace HNSW
 * index over `allm:{ns}:` HASH keys with a FLOAT32 little-endian `vector`
 * field) using GLIDE's typed GlideFt API.
 */

import {
  GlideClient,
  GlideFt,
  RequestError,
  ProtocolVersion,
} from "@valkey/valkey-glide";

// Dimension of the toy embedder below. A stand-in for a real embedding model
// (e.g. OpenAI text-embedding-3-small outputs 1536 dims).
export const DIM = 8;

/**
 * Toy embedder: maps text to a DIM-dimensional unit vector by hashing char
 * codes. Distinct text yields a distinct direction, which is what COSINE
 * similarity needs — never search with a constant/uniform vector.
 */
export function embed(text = "") {
  const v = new Array(DIM).fill(0);
  for (let i = 0; i < text.length; i++) v[i % DIM] += text.charCodeAt(i);
  const mag = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
  return v.map((x) => x / mag);
}

// Encode a numeric vector as a FLOAT32 little-endian Buffer (what valkey-search
// expects). Node Buffers are little-endian on all supported platforms.
export const floatToBuffer = (values) =>
  Buffer.from(Float32Array.from(values).buffer);

// Coerce a GlideString reply value (string | Buffer) to a string.
export const toStr = (v) => (Buffer.isBuffer(v) ? v.toString("utf-8") : `${v}`);

export const indexName = (ns) => `allm_idx_${ns}`;
export const keyPrefix = (ns) => `allm:${ns}:`;

/**
 * Build the GLIDE connection config the way the provider's Valkey.connection()
 * does: either a redis(s):// endpoint URL or discrete host/port + credentials.
 */
export function buildConfig(env = process.env) {
  let host = env.VALKEY_VECTOR_DB_HOST || "localhost";
  let port = Number(env.VALKEY_VECTOR_DB_PORT || 6379);
  let username = env.VALKEY_VECTOR_DB_USERNAME || null;
  let password = env.VALKEY_VECTOR_DB_PASSWORD || null;
  let useTLSFromUrl = false;

  if (env.VALKEY_VECTOR_DB_ENDPOINT) {
    const url = new URL(env.VALKEY_VECTOR_DB_ENDPOINT);
    if (url.hostname) host = url.hostname;
    if (url.port) port = Number(url.port);
    if (url.username) username = decodeURIComponent(url.username);
    if (url.password) password = decodeURIComponent(url.password);
    if (url.protocol === "rediss:") useTLSFromUrl = true; // rediss:// implies TLS
  }

  const config = {
    addresses: [{ host, port }],
    useTLS: String(env.VALKEY_VECTOR_DB_USE_TLS) === "true" || useTLSFromUrl,
    // GLIDE defaults to 250ms — too low off-localhost. 5000ms is the provider
    // default; tune to your network's tail latency.
    requestTimeout: Number(env.VALKEY_VECTOR_DB_REQUEST_TIMEOUT || 5000),
    // RESP2 keeps module replies (FT.SEARCH/FT.INFO/SCAN) as predictable arrays.
    protocol: ProtocolVersion.RESP2,
  };

  // Attach credentials when EITHER a username or password is set. Username-only
  // ACL users are valid; gating only on password would silently connect as the
  // unauthenticated default user.
  if (username || password) {
    config.credentials = {
      username: username || undefined,
      password: password || undefined,
    };
  }
  return config;
}

export const connect = () => GlideClient.createClient(buildConfig());

/**
 * Create the per-namespace HNSW index if it does not already exist. Drops a
 * stale index first only when `forceFresh` is set (used by samples for clean
 * re-runs). dropindex/info throw RequestError when the index is absent — a safe
 * no-op — so we catch only that narrow case (never a bare catch-all).
 */
export async function ensureIndex(client, ns, dims = DIM, { forceFresh = false } = {}) {
  if (forceFresh) {
    try {
      await GlideFt.dropindex(client, indexName(ns));
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }
  } else {
    try {
      await GlideFt.info(client, indexName(ns));
      return; // already exists
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }
  }

  await GlideFt.create(
    client,
    indexName(ns),
    [
      {
        type: "VECTOR",
        name: "vector",
        attributes: {
          algorithm: "HNSW",
          type: "FLOAT32",
          dimensions: dims,
          distanceMetric: "COSINE",
        },
      },
    ],
    { dataType: "HASH", prefixes: [keyPrefix(ns)] }
  );
}

// Upsert one chunk as a HASH: vector (bytes) + text + metadata (JSON string).
export async function upsertChunk(client, ns, id, vector, metadata) {
  await client.hset(`${keyPrefix(ns)}${id}`, {
    vector: floatToBuffer(vector),
    text: metadata.text || "",
    metadata: JSON.stringify(metadata),
  });
}

/**
 * KNN search. The query vector is bound via PARAMS ($BLOB) — never
 * string-interpolated — and DIALECT 2 is required for vector queries. Returns
 * an array of flat { field: value } objects.
 */
export async function knnSearch(client, ns, queryVector, topN = 4) {
  const [, docs] = await GlideFt.search(
    client,
    indexName(ns),
    `*=>[KNN ${topN} @vector $BLOB AS score]`,
    {
      params: [{ key: "BLOB", value: floatToBuffer(queryVector) }],
      returnFields: [
        { fieldIdentifier: "text" },
        { fieldIdentifier: "metadata" },
        { fieldIdentifier: "score" },
      ],
      limit: { offset: 0, count: topN },
      dialect: 2,
    }
  );
  return docs.map((doc) =>
    Object.fromEntries(doc.value.map((f) => [toStr(f.key), toStr(f.value)]))
  );
}

// Convert a COSINE distance into a clamped [0, 1] similarity. distance 0 -> 1.0,
// distance 1 -> 0.0. Returns 0 for non-numeric input.
export function distanceToSimilarity(distance) {
  if (distance === null || Number.isNaN(distance)) return 0;
  return Math.max(0, Math.min(1, 1 - distance));
}

// Mirror of AnythingLLM's sourceIdentifier: a stable id for a chunk's PARENT
// document. Chunks without title+published get a random id so they are never
// accidentally filtered as "pinned".
export function sourceIdentifier(meta = {}) {
  if (!meta.title || !meta.published) return `random-${Math.random()}`;
  return `title:${meta.title}-timestamp:${meta.published}`;
}

const SCAN_COUNT = 1000; // COUNT hint per SCAN iteration
const MAX_SCAN_ITERATIONS = 100_000; // safety cap so SCAN can never loop forever
const DELETE_BATCH_SIZE = 100; // keys per DEL call

// Bounded SCAN over a MATCH pattern. Never uses KEYS (which is O(N) and blocks
// the server). Stops at the iteration cap to guard against an unbounded loop.
export async function scanKeys(client, matchPattern) {
  const keys = [];
  let cursor = "0";
  let iterations = 0;
  do {
    const reply = await client.customCommand([
      "SCAN",
      cursor,
      "MATCH",
      matchPattern,
      "COUNT",
      String(SCAN_COUNT),
    ]);
    cursor = Array.isArray(reply) ? toStr(reply[0]) : "0";
    const batch =
      Array.isArray(reply) && Array.isArray(reply[1]) ? reply[1] : [];
    for (const k of batch) keys.push(toStr(k));
    if (++iterations >= MAX_SCAN_ITERATIONS) break;
  } while (cursor !== "0");
  return keys;
}

// Delete keys in bounded batches (respects DEL arg limits).
export async function deleteKeys(client, keys) {
  for (let i = 0; i < keys.length; i += DELETE_BATCH_SIZE) {
    const batch = keys.slice(i, i + DELETE_BATCH_SIZE);
    if (batch.length) await client.del(batch);
  }
}

// O(1) namespace vector count via FT.INFO. An unknown-index error means the
// namespace is absent (count 0); any other error is a real outage and rethrows.
export async function namespaceCount(client, ns) {
  try {
    const info = await GlideFt.info(client, indexName(ns));
    return Number(info.num_docs ?? 0) || 0;
  } catch (e) {
    if (e instanceof RequestError) return 0;
    throw e;
  }
}

// Poll FT.INFO num_docs until it reaches `expected` or we time out. Indexing is
// asynchronous, so we poll rather than sleep blindly. The deadline caps the loop.
export async function waitForIndexCount(client, ns, expected, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const count = await namespaceCount(client, ns);
    if (count === expected || Date.now() >= deadline) return count;
    await new Promise((r) => setTimeout(r, 100)); // 100ms between polls
  }
}

// Drop a namespace's index then sweep any orphaned chunk keys (always, even if
// the drop failed) so a partial failure can't leave dangling vectors.
export async function deleteNamespace(client, ns) {
  try {
    await GlideFt.dropindex(client, indexName(ns));
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
  }
  await deleteKeys(client, await scanKeys(client, `${keyPrefix(ns)}*`));
  return true;
}

// Full reset: drop every managed index (allm_idx_*) and remove every allm:* key.
export async function reset(client) {
  let list = [];
  try {
    list = await GlideFt.list(client);
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
  }
  for (const raw of list) {
    const name = toStr(raw);
    if (!name.startsWith("allm_idx_")) continue;
    try {
      await GlideFt.dropindex(client, name);
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }
  }
  await deleteKeys(client, await scanKeys(client, "allm:*"));
  return { reset: true };
}
