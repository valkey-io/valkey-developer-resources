# Prompt routing with llm-d and Valkey

llm-d routes each prompt to the model server most likely to already hold its KV
cache, so that server can reuse the work instead of recomputing it. That
decision, called prompt routing, rests on an index: a map of which server holds
each block of a conversation's KV cache. This cookbook runs that index on Valkey.

The index records locations, not the cached tensors themselves. It answers the
router's "who has this prefix?" lookup and updates as blocks are evicted. Putting
it in Valkey is what lets a fleet of router replicas share one view and agree on
where each conversation is already warm.

[llm-d](https://github.com/llm-d/llm-d) puts a router in front of several model
servers. When a request arrives, the router's Endpoint Picker tries to send it to
a server that already holds the request's KV cache, so the server can reuse that
work instead of recomputing it. To do that, the router keeps an index: a map from
KV-cache block keys to the servers that cached those blocks. By default each
router replica keeps that index in its own memory, so replicas don't share what
they know. Point the index at Valkey and the map becomes one shared store, where
every replica reads and writes the same index and agrees on which server holds
each conversation.

This cookbook is about that index, the piece prompt routing is built on. It
drives llm-d's real indexer library
([`llm-d-kv-cache`](https://github.com/llm-d/llm-d-kv-cache)) against Valkey, so
the keys it writes are exactly what a live router stores. The router's live
routing decisions sit on top of this index and are out of scope here (see
[What this shows, and what it doesn't](#what-this-shows-and-what-it-doesnt)).

## What you'll have working at the end

A local Valkey holding an llm-d routing index, and a notebook that walks through
the router's view of it: a model server records the blocks it cached, the router
looks a conversation up and finds that server, and after the server evicts a
block you see the cached prefix shorten. You inspect the index directly with
`valkey-cli`, and the state is shared: a second router replica pointed at the
same Valkey would read the same index. It runs on CPU, with no model server or
GPU required.

## How it works

The demo uses only Valkey (defined in [`docker-compose.yml`](docker-compose.yml)):

```
  valkey                 the shared routing index (llm-d's KV-cache block -> pods map)
  cmd/prompt-routing      a Go program that drives the index the way the router's EPP does
```

A conversation's prompt is split into fixed-size token blocks. Each block has a
stable hash that depends on its content and every block before it, so a shared
prefix yields a shared run of block hashes. The index stores, for each block hash,
the set of servers that hold that block — the block's location, not its cached
tensors. The router scores a candidate server by how long a cached prefix it
holds: the run of leading blocks it has, stopping at the first one it is missing.

The chaining is what keeps routing stable as a chat grows. When the user adds a
paragraph, the conversation gains new trailing blocks, but its leading blocks
hash exactly as before. So a three-block conversation recorded on `vllm-a`, grown
to four blocks on the next turn, still matches `vllm-a` on its first three blocks,
which is the longest cached prefix. The router sends it back there, where only the
new block needs computing. The chain also explains why losing the *first* block
hurts most. The router can only trust a prefix up to the first gap, so evicting
the front block drops the reliable prefix to zero even while later blocks remain.

The notebook runs the program once per step — `record`, then `lookup`, then
`evict` — each as its own process against the one shared index. The index keys it
writes are plain Valkey types you can read yourself:

```
  <block-hash>     a hash whose fields are the servers holding that block
  engine:<hash>    a sorted set linking an engine block to its request blocks
```

## Prerequisites

- **A container runtime with Compose** (Docker Compose or compatible) for Valkey.
- **Go 1.25 or newer**, matching the `go` directive in `go.mod`.
- **Jupyter** with the **gophernotes** Go kernel (installed in Getting started).
  If `jupyter` is not on your `PATH`, it is probably a user install. Add its bin
  directory (on macOS, `~/Library/Python/<version>/bin`) to `PATH`, or run the
  commands below as `python3 -m jupyter ...`.
- **Memory.** Valkey's footprint here is tiny (a few MiB); any default container
  runtime allocation is enough.

## Getting started

Start Valkey:

```bash
docker compose up -d --wait
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Install the Go (gophernotes) Jupyter kernel:

```bash
go install github.com/gopherdata/gophernotes@v0.7.6
KDIR="$(jupyter --data-dir)/kernels/gophernotes"
mkdir -p "$KDIR"
cp "$(go env GOPATH)/pkg/mod/github.com/gopherdata/gophernotes@v0.7.6/kernel/"* "$KDIR"
chmod -R u+w "$KDIR"
sed "s|gophernotes|$(go env GOPATH)/bin/gophernotes|" < "$KDIR/kernel.json.in" > "$KDIR/kernel.json"
```

Then open the notebook in Jupyter and run the cells top to bottom:

```bash
jupyter notebook prompt-routing-with-valkey.ipynb
```

Each step runs the compiled program in `cmd/prompt-routing` against Valkey and
prints what to look for. A server records its cached blocks, the router looks the
conversation up and finds that server, and once the server evicts a block, the
cached prefix the router can rely on drops to zero. Because each step is a
separate process reading one shared index in Valkey, they mirror separate router
replicas agreeing on the same state.

To run the whole notebook without opening the UI, the same way CI does, execute
it headless instead:

```bash
VALKEY_HOST=127.0.0.1 VALKEY_PORT=6379 \
  jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=600 \
  --output /tmp/executed.ipynb prompt-routing-with-valkey.ipynb
```

This writes the executed copy to `/tmp/executed.ipynb` and prints little on
success. Each step's output lands in that file, not the terminal.

After running the notebook, look at the index Valkey holds:

```bash
docker compose exec valkey valkey-cli keys '*'
```

You'll see one hash per cached block (fields are the servers holding it) and the
`engine:<hash>` sorted sets that chain engine blocks to request blocks.

Tear down when you're done:

```bash
docker compose down
```

## What this shows, and what it doesn't

This cookbook is about the routing index itself: the shared state in Valkey.
It uses llm-d's released indexer code, so the index mechanics (the block-to-server
map, the prefix-chain scoring, the shared-across-replicas property) are real.

It does not stand up the full routing-and-serving path: model servers emitting
KV-cache events, the router tokenizing live prompts and scoring real traffic, or
the first-token-latency win that cache-aware routing produces end to end. That is
a Kubernetes and GPU deployment and is out of scope here. See llm-d's
[precise prefix-cache routing guide](https://github.com/llm-d/llm-d/tree/main/guides/precise-prefix-cache-routing)
for the full stack.

Current limits worth knowing:

- The demo connects to a single Valkey node, with no Valkey Cluster sharding and
  no IAM-style auth in this walkthrough.
- The router scores servers from this index plus its own load signals; the
  index records where blocks are cached, it is not a separate oracle the router
  queries for cache contents.
- This cookbook uses no authentication. A separate component, LMCache, has an
  open fix for passing Valkey credentials that is not yet in a release; it does
  not affect this no-auth demo, which does not use LMCache.

## How this relates to the KV caching cookbook

The [KV caching cookbook](../kv-caching/) runs two vLLM replicas that share one
KV cache in Valkey. Its notebook picks which replica serves each request by hand:
it calls replica A, then deliberately replica B, so it can show the second
replica reusing the first's cached tensors. That hardcoded choice stands in for a
router.

This cookbook is that missing piece, the index a router consults to make the
choice on its own. In a full deployment the two fit together. The router reads
this index to send a request to the already-warm replica, and that replica then
reloads the cached tensors from Valkey (what the KV caching cookbook shows)
instead of recomputing them. This cookbook holds the block-to-server locations;
the KV caching cookbook holds the tensors those locations point to.

Wiring llm-d's real router (its Endpoint Picker) in front of those replicas, with
the servers emitting the KV-cache events that populate this index, is the
Kubernetes and GPU deployment described above.

## What's in this directory

```
docker-compose.yml               starts Valkey (the routing index store)
prompt-routing-with-valkey.ipynb  the cookbook notebook (Go / gophernotes kernel)
cmd/prompt-routing/main.go        the demo program the notebook runs per step
go.mod / go.sum                  pins github.com/llm-d/llm-d-kv-cache v1.0.0
_build_notebook.py               regenerates the notebook (see note below)
```

The notebook cells run the compiled program in `cmd/prompt-routing` via `go run`
rather than interpreting llm-d's library in-kernel. The gophernotes interpreter
cannot load a dependency tree that large as Go plugins; compiling the program
normally runs llm-d's real indexer code without that limitation. Dependencies are
pinned in `go.mod` / `go.sum` and fetched from the Go module proxy on first run.
To regenerate the notebook after editing the program or prose, run
`python3 _build_notebook.py` (needs `nbformat`).
