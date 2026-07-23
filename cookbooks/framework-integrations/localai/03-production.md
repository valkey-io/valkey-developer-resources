# Production Configuration for LocalAI + Valkey

> Configure the `valkey-store` backend per store with a LocalAI model config: connection address, authentication, TLS, and `FLAT` vs `HNSW` index tuning.

**Advanced** · Python · ~25 min

**Who is this for:** Operators taking the `valkey-store` backend beyond localhost — connecting to a remote Valkey, securing it with auth + TLS, and choosing an index algorithm for their corpus size.

Guides [01](01-getting-started.md) and [02](02-vector-search.md) used the
zero-config path: with no model config, the backend connects to
`localhost:6379` with FLAT/COSINE defaults. In production you'll want a specific
server, credentials, and an index tuned for your data. LocalAI expresses all of
that through a **model config** named after the store.

## Prerequisites

- Completed [01](01-getting-started.md) and [02](02-vector-search.md).
- A Valkey Search server you can reach (localhost is fine for following along).
- LocalAI's models directory path (the `--models`/`LOCALAI_MODELS_PATH` you
  launched with).

## Step 1: Configure a store with a model config

Each store resolves its own config, keyed by the `store` name. Create a YAML in
your models directory whose `name` matches the store you'll use in
`/stores/*` requests. Because config is per store, different stores in one
LocalAI process can point at different servers or use different index settings.

`models/faces.yaml`:

```yaml
name: faces
backend: valkey-store
options:
  - addr:valkey.internal:6379
  - index_algo:HNSW
  - distance_metric:COSINE
```

`options` is a list of `key:value` strings (split on the **first** `:`, so
`addr:host:6379` keeps its embedded colon). With a config in place, requests to
that store don't even need the `backend` field — the config selects it:

```bash
curl -sS -X POST http://localhost:8080/stores/set \
  -H "Content-Type: application/json" \
  -d '{"store":"faces","keys":[[0.1,0.2,0.3]],"values":["alice"]}'
```

## Step 2: Supply credentials without hardcoding them

Never put a password directly in the YAML that lives in your models directory.
The backend supports **env-indirection**: name an environment variable that
holds the credential, and the backend reads it at load time.

```yaml
name: faces
backend: valkey-store
options:
  - addr:valkey.internal:6379
  - username_env:MY_VALKEY_USER      # reads $MY_VALKEY_USER
  - password_env:MY_VALKEY_PASSWORD  # reads $MY_VALKEY_PASSWORD
  - tls:true
```

Then launch LocalAI with those variables set:

```bash
export MY_VALKEY_USER=localai
export MY_VALKEY_PASSWORD='...'      # from your secret manager, not the shell history
LOCALAI_BACKENDS_PATH="$(pwd)/backends" ./local-ai run --address 127.0.0.1:8080
```

The direct `username` / `password` options still work and take precedence when
both are set, but `*_env` keeps secrets out of the config file.

## Step 3: Enable TLS for any non-localhost connection

> **Security:** `tls` defaults to `false` (plaintext). Whenever Valkey is not
> on `localhost`, or you send a password, set `tls:true` — otherwise credentials
> and vectors travel the network unencrypted.

```yaml
options:
  - addr:valkey.example.com:6379
  - tls:true
  - tls_ca_cert:/etc/localai/valkey-ca.pem  # PEM bundle for a private/self-signed CA
```

The TLS server name (SNI) is derived from the host portion of `addr`, so
certificate verification works for both hostname and IP endpoints.
`tls_skip_verify:true` disables verification entirely — for local testing only.

## Step 4: Choose an index algorithm

`FLAT` does an exact brute-force scan of every vector; `HNSW` builds an
approximate-nearest-neighbour graph that trades a little recall for a large
speedup on big corpora.

| Algorithm | When to use | Trade-off |
|-----------|-------------|-----------|
| `FLAT` (default) | Small/medium corpora — roughly **< 100,000 vectors** | Exact results; latency grows linearly with corpus size |
| `HNSW` | Large corpora — roughly **≥ 100,000 vectors** | Approximate results; sub-linear query latency, more memory + build time |

The 100,000-vector figure is a rule of thumb — the crossover depends on your
dimension, latency budget, and recall tolerance; benchmark with your own data.
Select HNSW and tune its graph in the config:

```yaml
options:
  - index_algo:HNSW
  - hnsw_m:16                 # graph degree: neighbours per node. Higher = better recall, more memory.
  - hnsw_ef_construction:200  # build-time candidate list. Higher = better graph, slower builds.
  - hnsw_ef_runtime:10        # query-time candidate list. Higher = better recall, slower queries.
```

> The algorithm is fixed when the index is first created. To change it for an
> existing store, drop the index (`FT.DROPINDEX` in Valkey) or use a new store
> name — the next `Set` recreates it with the new settings.

## Step 5: Set a request timeout for remote servers

`request_timeout_ms` bounds every command the backend sends. The default
`5000` ms is generous for localhost; keep it comfortably above your slowest
expected KNN or bulk-index round-trip when Valkey is remote — too low and a
legitimate large `Find` or index back-fill fails spuriously.

```yaml
options:
  - request_timeout_ms:5000   # per-command timeout in ms; raise for remote/high-latency servers
```

## Configuration Reference

All options go in the model config's `options:` list as `key:value` strings.
When no config exists for a store, the backend uses these defaults against
`localhost:6379`.

| Option | Default | Description |
|--------|---------|-------------|
| `addr` | `localhost:6379` | Valkey server address (`host:port`). |
| `username` | *(empty)* | ACL username (plaintext in config). |
| `password` | *(empty)* | Password / ACL secret (plaintext in config). |
| `username_env` | *(empty)* | Env var holding the username. Preferred over `username`. |
| `password_env` | *(empty)* | Env var holding the password. Preferred over `password`. |
| `tls` | `false` | Enable TLS. Required for any non-localhost connection. |
| `tls_ca_cert` | *(empty)* | Path to a PEM CA bundle (self-signed / private CA). |
| `tls_skip_verify` | `false` | Skip certificate verification. Insecure — testing only. |
| `client_name` | `localai-valkey-store` | Connection name shown in `CLIENT LIST`. Always set. |
| `db` | `0` | Logical Valkey DB (`SELECT n`). |
| `index_algo` | `FLAT` | `FLAT` (exact) or `HNSW` (approximate ANN). |
| `hnsw_m` | `16` | HNSW graph degree (HNSW only). |
| `hnsw_ef_construction` | `200` | HNSW build-time candidate list (HNSW only). |
| `hnsw_ef_runtime` | `10` | HNSW query-time candidate list (HNSW only). |
| `distance_metric` | `COSINE` | `COSINE`, `L2`, or `IP`. |
| `request_timeout_ms` | `5000` | Per-command timeout in milliseconds. |

## Operational notes

- **Standalone only.** This backend targets a standalone Valkey Search server
  (one server per namespace/model). Valkey Cluster is not a supported target
  yet — index coordination across shards is out of scope for this backend, so
  don't point it at a cluster endpoint expecting sharded search.
- **Identify LocalAI's connections.** Every connection is named
  `localai-valkey-store` (configurable via `client_name`), so you can spot
  LocalAI's traffic with `valkey-cli CLIENT LIST`.
- **Namespace isolation is automatic.** Each store gets a collision-resistant
  key prefix and index name derived from its name, so many stores can share one
  Valkey server (or one logical `db`) without clashing.
- **Durability is Valkey's job.** Configure RDB/AOF on the Valkey side to match
  your durability needs — see [Valkey persistence](https://valkey.io/topics/persistence/).

---

[<- 02 - Vector Search & Persistence](02-vector-search.md)
