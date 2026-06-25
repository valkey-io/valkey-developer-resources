# Production Operations with AnythingLLM + Valkey

**Advanced** · JavaScript · ~20 min

## What You'll Build

Cookbooks [01](01-getting-started.md) and [02](02-vector-search.md) covered ingestion and retrieval. This one covers the operational machinery AnythingLLM's Valkey provider relies on in production:

* **TLS, auth, and timeouts** — connecting to a hardened or remote Valkey
* **The dimension-change guard** — why switching embedding models forces a reset
* **Namespace lifecycle** — counting, deleting a namespace, and a full reset
* **Bounded cleanup** — `SCAN` + batched `DEL` for orphaned keys (never `KEYS`)
* **Cluster considerations** — what changes when Valkey runs in cluster mode

It assumes Valkey is running with the search module and `@valkey/valkey-glide@2.4.1` is installed (see [01](01-getting-started.md)).

> ⚠️ The earlier cookbooks connected without authentication for local development. This cookbook shows the production-hardened connection. Always enable authentication and TLS for any non-local deployment.

## Step 1: Connect with TLS, auth, and an explicit timeout

The provider builds its GLIDE config from environment variables. A production connection adds credentials, TLS, and a generous request timeout. The same fields are available in the admin UI.

```javascript
import { GlideClient, ProtocolVersion } from "@valkey/valkey-glide";

// Build the connection config the way the provider's Valkey.connection() does:
// either a redis(s):// endpoint URL, or discrete host/port + credentials.
function buildConfig(env = process.env) {
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
    // A rediss:// scheme OR an explicit "true" enables TLS.
    useTLS: String(env.VALKEY_VECTOR_DB_USE_TLS) === "true" || useTLSFromUrl,
    // GLIDE defaults to 250ms — far too low for TLS/remote endpoints. 5000ms
    // (5s) is the provider default; tune to your network's tail latency.
    requestTimeout: Number(env.VALKEY_VECTOR_DB_REQUEST_TIMEOUT || 5000),
    // RESP2 keeps module replies (FT.SEARCH/FT.INFO/SCAN) as predictable arrays.
    protocol: ProtocolVersion.RESP2,
  };

  // Attach credentials when EITHER a username or password is set. Username-only
  // ACL users are valid; gating only on password would silently connect as the
  // unauthenticated default user (NOAUTH/NOPERM errors later).
  if (username || password) {
    config.credentials = {
      username: username || undefined,
      password: password || undefined,
    };
  }
  return config;
}

const client = await GlideClient.createClient(buildConfig());
```

A connection test (used by the admin "save settings" path) should always close its probe client, even on failure, so it never leaks a socket:

```javascript
async function validateConnection(config) {
  let probe = null;
  try {
    probe = await GlideClient.createClient(config);
    await probe.ping();
    await probe.close();
    return { success: true, error: null };
  } catch (e) {
    if (probe) {
      try { await probe.close(); } catch { /* ignore close failures on cleanup */ }
    }
    return { success: false, error: e.message };
  }
}
```

## Step 2: Guard against embedding-dimension changes

Each per-namespace index has a **fixed** vector dimension (`DIM`). If you change the embedding model — say from a 384-dim model to a 1536-dim one — the existing index no longer matches the new vectors. `valkey-search` silently refuses to index wrong-length FLOAT32 buffers, so ingestion would report success while nothing becomes searchable (silent data loss).

The provider defends against this by reading the existing index's dimension from `FT.INFO` and refusing to write mismatched vectors:

```javascript
import { GlideFt, RequestError } from "@valkey/valkey-glide";

// Returns the configured vector dimension of an index, or null if unknown.
// valkey-search nests `dimensions` inside the per-field attributes and the
// exact shape varies by version, so flatten the parsed FT.INFO reply into a
// token stream and take the value following a `dimensions`/`dim` key.
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

// Create the index if absent; if present, reject a dimension mismatch loudly.
async function getOrCreateIndex(client, indexName, keyPrefix, dimensions) {
  let info = null;
  try {
    info = await GlideFt.info(client, indexName);
  } catch (e) {
    if (!(e instanceof RequestError)) throw e; // RequestError == index absent
  }

  if (info) {
    const existing = indexDimension(info);
    if (dimensions && existing && existing !== dimensions) {
      throw new Error(
        `Dimension mismatch for ${indexName}: index is ${existing}-dim but ` +
        `incoming vectors are ${dimensions}-dim. Reset the vector store after ` +
        `changing the embedding model.`
      );
    }
    return; // exists and compatible — nothing to do
  }

  await GlideFt.create(
    client,
    indexName,
    [{
      type: "VECTOR",
      name: "vector",
      attributes: { algorithm: "HNSW", type: "FLOAT32", dimensions, distanceMetric: "COSINE" },
    }],
    { dataType: "HASH", prefixes: [keyPrefix] }
  );
}
```

Because the dimension is fixed per index, AnythingLLM routes a Valkey embedder change through a **full reset** (Step 4) rather than per-namespace deletes — the same constraint PGVector has.

## Step 3: Count and delete a namespace

`FT.INFO`'s `num_docs` gives the vector count for a namespace in one round trip. Deleting a namespace drops the index **and** sweeps any orphaned chunk keys, so a partial failure can never leave dangling vectors.

```javascript
// `client`, `GlideFt`, `RequestError` from above. indexName/keyPrefix per ns.

// O(1) count via FT.INFO; treat an unknown-index error as "namespace absent".
async function namespaceCount(client, indexName) {
  try {
    const info = await GlideFt.info(client, indexName);
    return Number(info.num_docs ?? 0) || 0;
  } catch (e) {
    if (e instanceof RequestError) return 0; // index doesn't exist yet
    throw e; // real outage (connection/auth) — propagate, don't mask as empty
  }
}

async function deleteNamespace(client, indexName, keyPrefix) {
  // Step 1: drop the index. It may not exist — that's fine.
  try {
    await GlideFt.dropindex(client, indexName);
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
  }
  // Step 2: ALWAYS clean chunk keys, even if step 1 failed, so no orphans remain.
  const keys = await scanKeys(client, `${keyPrefix}*`);
  await deleteKeys(client, keys);
  return true;
}
```

## Step 4: Bounded SCAN cleanup and full reset

Never use `KEYS` to find chunk keys — it is O(N) and blocks the server. The provider uses a **bounded** `SCAN` loop (capped so a pathological keyspace can't spin forever) and deletes in batches.

```javascript
const SCAN_COUNT = 1000;          // COUNT hint per SCAN iteration
const MAX_SCAN_ITERATIONS = 100_000; // safety cap: SCAN can never loop forever
const DELETE_BATCH_SIZE = 100;    // keys per DEL call (avoids one huge command)

const toStr = (v) => (Buffer.isBuffer(v) ? v.toString("utf-8") : `${v}`);

// Bounded SCAN over a MATCH pattern. Returns every matching key, or stops at
// the iteration cap (logging a warning) to guard against an unbounded loop.
async function scanKeys(client, matchPattern) {
  const keys = [];
  let cursor = "0";
  let iterations = 0;
  do {
    const reply = await client.customCommand([
      "SCAN", cursor, "MATCH", matchPattern, "COUNT", String(SCAN_COUNT),
    ]);
    cursor = Array.isArray(reply) ? toStr(reply[0]) : "0";
    const batch = Array.isArray(reply) && Array.isArray(reply[1]) ? reply[1] : [];
    for (const k of batch) keys.push(toStr(k));
    if (++iterations >= MAX_SCAN_ITERATIONS) break; // never loop unbounded
  } while (cursor !== "0");
  return keys;
}

// Delete keys in bounded batches (respects DEL arg limits).
async function deleteKeys(client, keys) {
  for (let i = 0; i < keys.length; i += DELETE_BATCH_SIZE) {
    const batch = keys.slice(i, i + DELETE_BATCH_SIZE);
    if (batch.length) await client.del(batch);
  }
}

// Full reset: drop every managed index (allm_idx_*) and remove every allm:* key.
// Used when the embedding model — and therefore the vector dimension — changes.
async function reset(client) {
  let list = [];
  try {
    list = await GlideFt.list(client); // FT._LIST — all indexes on the server
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
  }
  for (const raw of list) {
    const name = toStr(raw);
    if (!name.startsWith("allm_idx_")) continue; // only our managed indexes
    try {
      await GlideFt.dropindex(client, name);
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }
  }
  await deleteKeys(client, await scanKeys(client, "allm:*"));
  return { reset: true };
}
```

`reset()` only touches indexes prefixed `allm_idx_` and keys prefixed `allm:`, so it is safe to run alongside other workloads on the same Valkey instance.

## Step 5: Poll for asynchronous indexing

`valkey-search` indexes new chunks asynchronously, so a search immediately after ingest may return nothing. In production code, poll `num_docs` with an explicit cap instead of a blind `sleep`:

```javascript
// Poll until num_docs reaches `expected` or we time out. The deadline cap
// guards against an index that never converges (e.g. wrong-dim vectors).
async function waitForIndexCount(client, indexName, expected, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  while (true) {
    const count = await namespaceCount(client, indexName);
    if (count === expected || Date.now() >= deadline) return count;
    await new Promise((r) => setTimeout(r, 100)); // 100ms between polls
  }
}
```

## Cluster considerations

The provider creates a standalone `GlideClient`, which is the right choice for the per-namespace design:

- **One index spans many keys.** An `allm_idx_{ns}` index watches every `allm:{ns}:*` HASH. In Valkey **Cluster**, those keys hash to different slots unless they share a hash tag, and cross-slot operations (like a multi-key `DEL` over scattered keys) are rejected. The provider's batched `DEL` works in standalone mode; to run on a cluster you would add a hash tag (e.g. `allm:{ {ns} }:`) so a namespace's keys colocate on one slot.
- **`valkey-search` on cluster** requires the coordinator and cluster-aware index management. If you need cluster mode, validate index creation and search against your topology before relying on it.

For most AnythingLLM deployments a single Valkey node (or a primary with replicas) is the simplest, fully-supported setup.

## How It Works Under the Hood

| Operation | Valkey Command | Notes |
|-----------|---------------|-------|
| Connection probe | `PING` | Validates host/credentials/TLS at save time |
| Dimension check | `FT.INFO {idx}` → `num_docs`, vector `dimension` | Rejects an embedder change that would corrupt the index |
| Namespace count | `FT.INFO {idx}` → `num_docs` | O(1); unknown-index error means "absent" |
| Delete namespace | `FT.DROPINDEX {idx}` + `SCAN` + `DEL` | Always sweeps orphan keys even if the drop fails |
| Reset | `FT._LIST` + `FT.DROPINDEX allm_idx_*` + `SCAN allm:* ` + `DEL` | Only touches managed indexes/keys |
| Key cleanup | `SCAN ... COUNT 1000` + batched `DEL` | Bounded loop; never `KEYS` |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `NOAUTH`/`NOPERM` errors | Set `VALKEY_VECTOR_DB_USERNAME`/`PASSWORD`; the provider attaches credentials when either is present. |
| TLS handshake fails | Use a `rediss://` endpoint or `VALKEY_VECTOR_DB_USE_TLS="true"`, and confirm the server presents a trusted certificate. |
| Ingestion "succeeds" but search is empty after a model change | You hit the dimension mismatch — run `reset()` after changing the embedding model. |
| `CROSSSLOT` errors | You're on Valkey Cluster without hash tags; colocate a namespace's keys with a hash tag or use a standalone instance. |
| Slow saves on a remote endpoint | Increase `VALKEY_VECTOR_DB_REQUEST_TIMEOUT`; the 250ms GLIDE default is too low off-localhost. |

[← Back: 02 Vector Search & Retrieval](02-vector-search.md)
