# Production Deployment with MetaGPT + Valkey

> Configure TLS, tune the HNSW index, monitor index health, and deploy `ValkeyVectorStore` against a managed Valkey service.

**Advanced** · Python · ~15 min

**Who is this for:** Python developers deploying the MetaGPT + Valkey RAG vector store beyond local development — securing connections, tuning the vector index, and monitoring a production deployment.

This cookbook covers hardening `ValkeyVectorStore` for production: encrypting connections, authenticating with ACL, tuning the HNSW index's recall/latency tradeoff, deploying against a managed Valkey
service, and monitoring index health.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - Vector Store for RAG](02-vector-store-rag.md)
- A Valkey Bundle 9.1.0 deployment (with the Search module) reachable from your application — self-hosted or managed
- Ability to configure TLS and ACLs on that deployment

## Step 1: TLS Encryption

Enable TLS to encrypt data in transit (required for any non-localhost deployment). The proposed MetaGPT config surface exposes this as `use_tls`:

```yaml
# config/config2.yaml (proposed — see 01-getting-started.md's Upstream Status)
valkey:
  host: "valkey.example.com"
  port: 6380
  use_tls: true
  password: "${VALKEY_PASSWORD}"
  index_name: "prod_rag"
  vector_dimensions: 1536
```

The standalone sample's `ValkeyVectorStore` takes the same option directly:

```python
from valkey_vector_store import ValkeyVectorStore

store = ValkeyVectorStore(
    host="valkey.example.com",
    port=6380,
    use_tls=True,
    password=os.environ["VALKEY_PASSWORD"],
    index_name="prod_rag",
    vector_dimensions=1536,
)
```

`use_tls=True` passes `use_tls=True` to `GlideClientConfiguration`, which enables TLS negotiation on the connection. Both the real upstream implementation and this cookbook's sample log a warning if
a password is configured with TLS disabled — sending credentials in cleartext — rather than silently proceeding (see `_connect()` in [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py)).

For cloud-managed Valkey (e.g., Amazon ElastiCache for Valkey, Amazon MemoryDB for Valkey, Google Cloud Memorystore for Valkey), TLS is typically mandatory.

## Step 2: Authentication

Set a password (and, on servers that support it, an ACL username) so the connection isn't anonymous:

```bash
# Run from bash (not inside valkey-cli). Replace 'yourpassword' with the actual password.
valkey-cli ACL SETUSER metagpt_rag_app on ">yourpassword" "~metagpt:rag:*" +JSON.SET +JSON.GET +DEL +SCAN +FT.CREATE +FT.SEARCH +FT.DROPINDEX +FT._LIST +FT.INFO +PING
```

This restricts the application user to only the key pattern and commands `ValkeyVectorStore` actually issues. Pass the password through `ValkeyVectorStore(password=...)` (or
`ValkeyStoreConfig.password` in the proposed upstream config) — never hardcode it in source.

## Step 3: Deploying on a Managed Valkey Service

`ValkeyVectorStore` needs only a reachable host, port, and (optionally) TLS/auth — it works the same way against a self-hosted Valkey or a managed service. Two examples on AWS:

- **[Amazon ElastiCache for Valkey](https://aws.amazon.com/elasticache/)** — fully managed, in-region Valkey clusters. Use the cluster's configuration endpoint as `host`, enable **in-transit
  encryption** (TLS) and **auth token** (password) when creating the cluster, and set `use_tls=True` here.
- **[Amazon MemoryDB for Valkey](https://aws.amazon.com/memorydb/)** — fully managed, multi-AZ durable Valkey. Same connection shape as ElastiCache: TLS and an auth token, pointed at the cluster
  endpoint.

Other providers' managed Valkey/Redis OSS-compatible offerings (e.g., Google Cloud Memorystore) work the same way: point `host` / `port` at the managed endpoint and enable TLS and authentication as
that provider requires. Whichever you choose, confirm the managed service's Valkey build includes the **Search module** — `ValkeyVectorStore` cannot create its `FT.SEARCH` index without it, and a
managed instance running plain Valkey (no Search module) will fail on `ensure_index()` with `Unknown command 'FT.CREATE'`.

```python
store = ValkeyVectorStore(
    host=os.environ["VALKEY_HOST"],   # e.g. your ElastiCache/MemoryDB configuration endpoint
    port=int(os.environ.get("VALKEY_PORT", "6379")),
    use_tls=True,
    password=os.environ["VALKEY_PASSWORD"],
    index_name="prod_rag",
    prefix="metagpt:rag:",
    vector_dimensions=1536,
    request_timeout=int(os.environ.get("VALKEY_REQUEST_TIMEOUT_MS", "5000")),
)
```

Increase `request_timeout` for any deployment where the client and server aren't in the same availability zone — GLIDE's own default (250ms) is tuned for same-host or same-AZ latency, not cross-region
hops.

## Step 4: Tuning the HNSW Index

The HNSW parameters below are exposed by GLIDE's `VectorFieldAttributesHnsw` (verified against the installed `glide_sync` package) but are **not currently exposed as constructor arguments** by either
the real upstream `ValkeyVectorStore` or this cookbook's standalone reimplementation — both hardcode Valkey Search's own defaults. If you need to tune them, extend `ensure_index()` to pass these
through:

| Parameter | GLIDE Field | Module API Name | Default | Maximum | Effect |
| --- | --- | --- | --- | --- | --- |
| Initial capacity | `initial_cap` | `INITIAL_CAP` | `1024` | — | Pre-allocates index memory for this many vectors |
| Max edges per node | `number_of_edges` | `M` | `16` | `512` | Higher values build a denser graph, trading index memory and build time for potentially better recall |
| Vectors examined at build time | `vectors_examined_on_construction` | `EF_CONSTRUCTION` | `200` | `4096` | Higher values examine more candidates while building the graph, trading index build time for potentially better recall |
| Vectors examined at query time | `vectors_examined_on_runtime` | `EF_RUNTIME` | `10` | `4096` | Higher values examine more candidates per query, trading query-time compute for potentially better recall |

```python
from glide_sync import DistanceMetricType, VectorFieldAttributesHnsw, VectorType

attributes = VectorFieldAttributesHnsw(
    dimensions=1536,
    distance_metric=DistanceMetricType.COSINE,
    type=VectorType.FLOAT32,
    initial_cap=4096,                     # pre-size for a known corpus
    number_of_edges=32,                   # denser graph than the default 16
    vectors_examined_on_construction=400, # more thorough index build than the default 200
    vectors_examined_on_runtime=20,       # examine more candidates per query than the default 10
)
```

Every parameter here trades index build time, index memory, or per-query compute for recall — the right values depend on your corpus size and latency budget, so benchmark against your own workload
rather than adopting these example values directly. If recall matters more than query speed for your use case, raise `EF_RUNTIME` and `EF_CONSTRUCTION` first; if you need to bound worst-case memory,
cap `M` and set `initial_cap` to your expected corpus size instead of relying on the default.

For an exact accuracy match with no tuning at all, use `vector_algorithm="FLAT"` instead of `"HNSW"` — `VectorFieldAttributesFlat` only exposes `initial_cap` (default `1024`), since a flat index has
no graph to tune. See [HNSW vs FLAT Index](02-vector-store-rag.md#hnsw-vs-flat-index) in the previous cookbook for when each is the better fit.

## Step 5: Monitoring

Track index health and growth with `FT.INFO`:

```bash
# Document count and index status
docker exec valkey valkey-cli FT.INFO prod_rag
# For a remote/managed deployment, drop the docker exec prefix and connect
# valkey-cli directly to the server (with --tls and -a as needed).
```

Watch these fields in the output:

- **`num_docs`** — growing unexpectedly beyond your source corpus size can indicate `delete()` isn't being called when source documents are removed or re-chunked
- **`indexing`** — `1` means the index is still catching up on recently written documents; sustained `1` for a large corpus can indicate the writer is outpacing the indexer
- Memory reported by `FT.INFO` / `INFO memory` — HNSW's graph structure uses more memory than FLAT for the same corpus; watch this if you raise `number_of_edges` per Step 4

Because `add()` and `query()` are both fully synchronous, timeouts and connection errors surface immediately as Python exceptions rather than as silent, deferred failures — wrap calls in `try` /
`except` at your application boundary and log the reported error, rather than swallowing it.

## Production Best Practices

- **Run standalone, not cluster, unless you hash-tag your keys.** As covered in [02 - Vector Store for RAG](02-vector-store-rag.md#how-it-works-under-the-hood), `add()`'s atomic batch write relies on
  every key in the batch hashing to the same slot. The document keys (`<prefix><doc_id>`) carry no hash tag, so a cluster deployment will scatter them across slots and the atomic-batch write will
fail. Deploy standalone (or a single-shard cluster) unless you extend the key format with a shared hash tag.
- **Never build the KNN filter expression from unsanitized input.** As covered in [02 - Vector Store for RAG](02-vector-store-rag.md#how-it-works-under-the-hood), the filter portion of the
`FT.SEARCH` query must stay a hardcoded literal (or a value validated against an allowlist) — only the vector itself should ever come from a bound parameter.
- **Call `disconnect()` in a `finally` block.** Each `ValkeyVectorStore` owns one GLIDE connection, opened lazily on first use. Leaking it under load exhausts connection pools on the server side.
- **Retry `add()` on failure without re-inserting duplicates.** A failed batch reports how many documents were durably written before the failure (see the `RuntimeError` message in `add()`); resume
from that offset rather than re-running the whole batch.
- **Match `vector_dimensions` to your embedding model exactly.** A mismatch raises `ValueError` at query time (`query()` checks this explicitly) rather than silently truncating or padding the vector.

## How It Works

| Component | Role |
| --- | --- |
| TLS (`use_tls`) | Encrypts the connection between the application process and Valkey |
| ACL user | Restricts the application to specific commands and key patterns |
| `VectorFieldAttributesHnsw` | Exposes `M` / `EF_CONSTRUCTION` / `EF_RUNTIME` / `INITIAL_CAP` for tuning the HNSW graph |
| `FT.INFO` | Reports document count, indexing status, and memory usage for monitoring |
| Per-process `GlideClient` | Each process owns its own connection; no shared state or locking required |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `host` | — | `localhost` | Valkey server host (or managed-service endpoint) |
| `port` | — | `6379` | Valkey server port |
| `password` | — | `None` | Auth password |
| `use_tls` | — | `False` | Enable TLS (required for most managed/remote deployments) |
| `request_timeout` | — | `5000` | Request timeout in milliseconds |
| `index_name` | — | `metagpt_rag` | Name of the `FT.SEARCH` index |
| `prefix` | — | `metagpt:rag:` | Key prefix for stored documents (no hash tag — standalone only) |
| `vector_dimensions` | — | `1536` | Embedding dimension — must match your model exactly |
| `distance_metric` | — | `COSINE` | `COSINE`, `L2`, or `IP` |
| `vector_algorithm` | — | `HNSW` | `HNSW` (tunable, approximate) or `FLAT` (exact, only `initial_cap` tunable) |
| `client_name` | — | `metagpt_rag_client` | Connection name shown in `CLIENT LIST` |

---

[← 02 - Vector Store for RAG](02-vector-store-rag.md) | [README →](README.md)
