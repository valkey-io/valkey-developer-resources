# Getting Started with LocalAI + Valkey

> Stand up Valkey and LocalAI, select the `valkey-store` backend, and store & retrieve your first vectors over the `/stores/*` REST API.

**Beginner** · Python · ~20 min

**Who is this for:** Python developers running self-hosted LocalAI who want a durable, restart-surviving vector store instead of the in-memory default — without changing any application code.

LocalAI ships a pluggable vector store behind its `/stores/*` HTTP endpoints.
The default `local-store` backend keeps everything in memory, so all vectors are
lost on restart and `Find` is an O(N) scan. The `valkey-store` backend swaps that
for [Valkey Search](https://valkey.io/), giving you persistence and a real vector
index — selected per request with a single `"backend"` field. This guide gets a
working round-trip going; [02](02-vector-search.md) covers similarity search and
persistence, and [03](03-production.md) covers auth, TLS, and index tuning.

## Prerequisites

- Docker or Podman installed (for Valkey)
- Python 3.10+ (the sample needs `requests` and `python-dotenv` — see [`sample/requirements.txt`](sample/requirements.txt))
- A Go 1.26+ toolchain **only until the PR merges** — you build the backend from
  the [`valkey-store` PR branch](https://github.com/mudler/LocalAI/pull/10770).
  Once it ships in the backend gallery this step disappears.

## Step 1: Start Valkey

The backend needs a Valkey server with the **Valkey Search** (`FT.*`) module. The
`valkey/valkey-bundle` image ships it:

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:8.1.7
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Confirm the Search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Look for a module named "search" in the output.
```

## Step 2: Build the `valkey-store` backend

> **Temporary — pending upstream merge.** The `valkey-store` backend is added in
> [mudler/LocalAI#10770](https://github.com/mudler/LocalAI/pull/10770) and is not
> yet in the released backend gallery. Until it merges, build it from the PR
> branch. Once merged, you'll instead install it with
> `local-ai backends install valkey-store` and can skip this step.

```bash
# Clone the PR branch. To pin exactly, use the PR head commit instead of the
# branch name: git clone https://github.com/daric93/LocalAI.git && git checkout <sha>
git clone --branch feature/valkey-store-backend \
  https://github.com/daric93/LocalAI.git
cd LocalAI

# Generate the gRPC stubs the backend links against, then build the backend.
# CGO_ENABLED=0 keeps it a static, dependency-free binary.
make protogen-go
CGO_ENABLED=0 go build -o backend/go/valkey-store/valkey-store ./backend/go/valkey-store/
```

You now have a `valkey-store` backend binary. It's a gRPC process that LocalAI
starts on demand; you don't run it directly.

## Step 3: Start LocalAI with the backend registered

Build the LocalAI server from the same checkout and point it at a models
directory and the backend:

```bash
# Build the server (from the LocalAI checkout).
CGO_ENABLED=0 go build -o local-ai ./cmd/local-ai

# LocalAI discovers Go backends from a backends directory laid out as
# <backends>/<name>/run.sh. Stage the built backend there:
mkdir -p ./backends/valkey-store
cp backend/go/valkey-store/valkey-store backend/go/valkey-store/run.sh ./backends/valkey-store/

# Launch. LOCALAI_BACKENDS_PATH tells LocalAI where to find the backend.
LOCALAI_BACKENDS_PATH="$(pwd)/backends" ./local-ai run --address 127.0.0.1:8080
```

Wait for the log line reporting the API is listening on `127.0.0.1:8080`.

> ⚠️ **Security:** Binding to `127.0.0.1` keeps LocalAI's unauthenticated
> `/stores/*` API (vector read/write/delete) reachable only from this machine.
> Never bind to `:8080` (all interfaces) on a shared network or public-IP host
> without adding authentication in front of it.

## Step 4: Store your first vectors

Every `/stores/*` request takes an optional `backend` field. Passing
`"valkey-store"` (or the `"valkey"` alias) routes the operation to Valkey. The
`store` field names an isolated namespace — think of it as a table.

`keys` are equal-length float32 vectors; `values` are opaque strings stored
alongside each vector. Here we use tiny 3-dimensional vectors so the example is
easy to read:

```bash
curl -sS -X POST http://localhost:8080/stores/set \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "valkey-store",
    "store": "quickstart",
    "keys":   [[0.1, 0.2, 0.3], [0.9, 0.1, 0.0]],
    "values": ["first document", "second document"]
  }'
```

The first `Set` for a store lazily creates the Valkey Search index at the
dimension of the vectors you send (here, 3). Every later vector in that store
must have the same length.

## Step 5: Read them back

`Get` returns the value stored under an **exact** vector match (nearest-neighbour
search is `Find`, covered in [02](02-vector-search.md)):

```bash
curl -sS -X POST http://localhost:8080/stores/get \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "valkey-store",
    "store": "quickstart",
    "keys":   [[0.1, 0.2, 0.3]]
  }'
# => {"keys":[[0.1,0.2,0.3]],"values":["first document"]}
```

Missing keys are simply omitted from the response (not an error), so a `Get` for
a vector you never stored returns empty `keys`/`values`.

## Step 6: Do it from Python

The [`sample/`](sample/) directory has a complete client. The core of it is a
thin wrapper over `requests`:

```python
import requests

# One session, reused for every request (Rule 17: expensive objects once).
SESSION = requests.Session()
BASE_URL = "http://localhost:8080"
BACKEND = "valkey-store"  # route /stores/* to Valkey
STORE = "quickstart"      # namespace / "table" name
TIMEOUT = 5.0             # seconds; raise for slow networks or large batches


def stores_set(keys, values):
    resp = SESSION.post(
        f"{BASE_URL}/stores/set",
        json={"backend": BACKEND, "store": STORE, "keys": keys, "values": values},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


def stores_get(keys):
    resp = SESSION.post(
        f"{BASE_URL}/stores/get",
        json={"backend": BACKEND, "store": STORE, "keys": keys},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


try:
    stores_set([[0.1, 0.2, 0.3], [0.9, 0.1, 0.0]], ["first document", "second document"])
    result = stores_get([[0.1, 0.2, 0.3]])
    # Assert the round-trip (Rule 27): a silent empty result would mean the
    # write never landed.
    assert result["values"] == ["first document"], f"unexpected: {result}"
    print("round-trip OK:", result)
finally:
    SESSION.close()
```

## How It Works

| Component | Role |
|-----------|------|
| Python client | Sends float32 vectors + values to LocalAI over HTTP `/stores/*`. |
| LocalAI `/stores/*` | REST endpoints; the `backend` field selects the store implementation. |
| `valkey-store` backend | gRPC process; turns Set/Get/Delete/Find into Valkey commands. |
| Valkey Search (`FT.*`) | Stores each vector as a HASH (`vec` + `val` fields) and serves KNN. Persists via RDB/AOF. |

Under the hood, a `Set` becomes one `HSET` per vector (the key is a
prefix + the vector's bytes, so identical vectors upsert), a `Get` is an `HGET`,
and the index is created once with `FT.CREATE ... VECTOR FLAT ... DISTANCE_METRIC COSINE`.
We prove those exact commands in [02](02-vector-search.md).

## Configuration Reference

The client-side knobs used above:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `BASE_URL` | ✓ | — | LocalAI server address. |
| `BACKEND` | — | `local-store` | Store backend; `valkey-store` routes to Valkey. |
| `STORE` | ✓ | — | Store namespace (isolated keyspace + index). |
| `TIMEOUT` | — | `5.0` | Per-request HTTP timeout in seconds; raise for large batches. |

Server- and Valkey-side options (connection address, auth, index algorithm) are
configured through a LocalAI **model config** — see [03](03-production.md).

---

[02 - Vector Search & Persistence →](02-vector-search.md)
