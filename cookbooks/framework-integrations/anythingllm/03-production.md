# Production Operations

> Harden AnythingLLM's Valkey provider for production: TLS/auth, connection probes, the embedding-dimension guard, namespace deletion with orphan sweeps, and full vector store reset.

**Advanced** · Node.js · ~20 min

**Who is this for:** Teams deploying AnythingLLM with Valkey in production who need secure connections, operational safety guards, and clean lifecycle management.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md) and [Vector Search](./02-vector-search.md)
- Valkey running with the search module
- Understanding of TLS certificates and ACL authentication (for the security sections)

> **Security note:** Production Valkey instances must use authentication and TLS.
> The patterns below show how to configure both.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for full hardening guidance.

## Connection Probe

AnythingLLM validates the Valkey connection when an admin saves vector database settings. The probe creates a short-lived client, sends a PING, and closes — always cleaning up even on failure:

```javascript
async function validateConnection(config) {
  let probe = null;
  try {
    probe = await GlideClient.createClient(config);
    await probe.ping();
    return { success: true, error: null };
  } catch (e) {
    return { success: false, error: e.message };
  } finally {
    if (probe) probe.close();
  }
}
```

This pattern:

- Reports connectivity issues before any data operations
- Never leaves open connections on failure
- Runs independently of the long-lived application client

## TLS and Authentication

### Password Authentication

```javascript
const config = {
  addresses: [{ host: "valkey.internal", port: 6379 }],
  credentials: { password: process.env.VALKEY_VECTOR_DB_PASSWORD },
  useTLS: true,
  requestTimeout: 5000,
  protocol: ProtocolVersion.RESP2,
};
```

### ACL Authentication (Username + Password)

```javascript
const config = {
  addresses: [{ host: "valkey.internal", port: 6379 }],
  credentials: {
    username: process.env.VALKEY_VECTOR_DB_USERNAME,
    password: process.env.VALKEY_VECTOR_DB_PASSWORD,
  },
  useTLS: true,
  requestTimeout: 5000,
  protocol: ProtocolVersion.RESP2,
};
```

Minimal ACL for the AnythingLLM provider:

```text
ACL SETUSER anythingllm on >password ~allm:* &allm_idx_* +ping +hset +del
    +scan +ft.create +ft.search +ft.dropindex +ft.info +ft.list +ft._list
```

### Endpoint URL (rediss:// implies TLS)

AnythingLLM also accepts a full endpoint URL. The `rediss://` protocol enables TLS automatically:

```bash
VALKEY_VECTOR_DB_ENDPOINT="rediss://user:pass@valkey.internal:6380"
```

## Request Timeout

The provider defaults to 5000ms per command. Tune this to your network's tail latency:

```bash
VALKEY_VECTOR_DB_REQUEST_TIMEOUT=5000
```

For cross-region connections (>100ms RTT), increase to 10000ms. For same-VPC connections (<1ms RTT), 2000ms is sufficient.

## Embedding Dimension Guard

If you change your embedding model (e.g., from 1536-dim to 3072-dim), existing indexes become incompatible. The provider detects this mismatch before writing:

```javascript
async function assertDimensionCompatible(client, ns, newDims) {
  let info;
  try {
    info = await GlideFt.info(client, indexName(ns));
  } catch (e) {
    if (e instanceof RequestError) return; // index absent — safe to create
    throw e;
  }

  const existingDims = extractDimensionFromInfo(info);
  if (newDims && existingDims && existingDims !== newDims) {
    throw new Error(
      `Dimension mismatch: index has ${existingDims}-dim vectors but ` +
        `incoming are ${newDims}-dim. Reset the vector store first.`,
    );
  }
}
```

When this fires, the admin must reset the vector store through the AnythingLLM UI before re-embedding with the new model.

## Namespace Deletion

Deleting a workspace's vectors requires two steps: drop the index, then sweep orphan keys. The sweep runs unconditionally — even if the drop fails (partial failure safety):

```javascript
async function deleteNamespace(client, ns) {
  // 1. Drop the index (idempotent — RequestError if absent)
  try {
    await GlideFt.dropindex(client, indexName(ns));
  } catch (e) {
    if (!(e instanceof RequestError)) throw e;
  }

  // 2. Sweep orphan keys with bounded SCAN
  const keys = await scanKeys(client, `${keyPrefix(ns)}*`);
  await deleteKeys(client, keys);
}
```

### Bounded SCAN

The provider never uses `KEYS` (O(N), blocks the event loop). Instead, it uses `SCAN` with:

- `COUNT 1000` hint per iteration (batch size)
- A safety cap of 100,000 iterations to prevent infinite loops
- Pattern matching via `MATCH` to scope to the namespace prefix

```javascript
async function scanKeys(client, matchPattern) {
  const keys = [];
  let cursor = "0";
  let iterations = 0;
  do {
    const reply = await client.customCommand([
      "SCAN", cursor, "MATCH", matchPattern, "COUNT", "1000",
    ]);
    cursor = toStr(reply[0]);
    for (const k of reply[1]) keys.push(toStr(k));
    if (++iterations >= 100_000) break;
  } while (cursor !== "0");
  return keys;
}
```

### Batched DEL

Keys are deleted in batches of 100 to respect command argument limits and avoid blocking:

```javascript
async function deleteKeys(client, keys) {
  for (let i = 0; i < keys.length; i += 100) {
    const batch = keys.slice(i, i + 100);
    if (batch.length) await client.del(batch);
  }
}
```

## Full Reset

The "Reset vector database" action drops every managed index and removes every managed key:

```javascript
async function reset(client) {
  // 1. List all indexes
  const list = await GlideFt.list(client);

  // 2. Drop only allm_idx_* indexes (leave non-AnythingLLM indexes alone)
  for (const raw of list) {
    const name = toStr(raw);
    if (!name.startsWith("allm_idx_")) continue;
    try {
      await GlideFt.dropindex(client, name);
    } catch (e) {
      if (!(e instanceof RequestError)) throw e;
    }
  }

  // 3. Sweep all allm:* keys
  const keys = await scanKeys(client, "allm:*");
  await deleteKeys(client, keys);
}
```

This is safe on shared Valkey instances — it only touches keys and indexes with the `allm` prefix.

## Cluster Considerations

For Valkey Cluster deployments:

| Concern | Approach |
| --- | --- |
| Slot routing | Each namespace's keys share a prefix (`allm:{ns}:`) but without hash tags, they distribute across slots. This is fine for non-atomic operations. |
| Index scope | FT.CREATE with a prefix routes to the node owning that slot range. Each namespace index lives on one node. |
| Multi-node SCAN | Use `client.customCommand(["SCAN", ...])` per node or let the GLIDE cluster client handle routing. |
| Atomic batches | Not needed — the provider's operations are independent per-key. |

For single-node deployments (the common case for AnythingLLM), no cluster-specific configuration is needed.

## Deployment Options

AnythingLLM connects to any Valkey instance with the search module. Common deployment targets:

| Target | Notes |
| --- | --- |
| Self-hosted (`valkey/valkey-bundle`) | Full control, includes search module |
| AWS ElastiCache for Valkey | Managed, supports search module (check version availability) |
| GCP Memorystore for Valkey | Managed, supports search module |
| Any Valkey-compatible service | Must include the `valkey-search` module |

Connection strings are generic `valkey://host:port` — no vendor-specific SDK required.

## Run the Integration Test

```bash
npm test -- --grep "Production"
```

## Configuration Reference

| Environment Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_VECTOR_DB_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_VECTOR_DB_PORT` | `6379` | Valkey server port |
| `VALKEY_VECTOR_DB_ENDPOINT` | — | Full URL (overrides host/port) |
| `VALKEY_VECTOR_DB_USERNAME` | — | ACL username |
| `VALKEY_VECTOR_DB_PASSWORD` | — | AUTH password |
| `VALKEY_VECTOR_DB_USE_TLS` | `false` | Enable TLS |
| `VALKEY_VECTOR_DB_REQUEST_TIMEOUT` | `5000` | Per-command timeout (ms) |

---

[← Vector Search & Retrieval](./02-vector-search.md) · [← Back to README](./README.md)
