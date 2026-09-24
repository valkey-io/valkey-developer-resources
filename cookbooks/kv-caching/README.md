# Building a KV Cache for vLLM with Valkey

Serve an LLM behind two vLLM instances that share one KV cache in Valkey, and
watch a prompt prefix that one instance computes get reused by the other instead
of being recomputed.

When an LLM answers a prompt it first computes attention key/value (KV) tensors
for every input token — the prefill step. That work is thrown away after
each request, so whenever a later request shares a prefix with an earlier one
(a multi-turn chat, a shared system prompt, a reused RAG passage), prefill
recomputes the same KV from scratch. Caching that KV and reloading it skips the
recompute: you pay for prefill once and reuse it.

[LMCache](https://github.com/LMCache/LMCache) is the KV-cache layer that plugs
into vLLM. It can store KV in local memory, on disk, or in a remote backend; this
cookbook runs a standalone LMCache server backed by **Valkey**. vLLM's own
built-in prefix cache only covers what a single engine holds and is not shared
with other engines — so use Valkey when several vLLM instances should share a cache.

## What you'll have working at the end

A running four-container stack — Valkey, a standalone LMCache server, and two
vLLM replicas — and a notebook that walks a multi-turn chat through it. You'll
see a cold request store its KV in Valkey, a warm request read that KV back
(faster, no re-prefill), and a **second replica reuse the first replica's cached
prefix** — cross-instance reuse an in-process cache can't do. The whole thing
runs on CPU.

## How it works

The notebook drives four containers (defined in
[`docker-compose.yml`](docker-compose.yml)):

```
  valkey          one shared KV-cache store (LMCache's L2 backend)
  lmcache-server  standalone LMCache server: L1 in its own memory, L2 -> Valkey
  vllm-a          vLLM replica A, KV connector pointed at the LMCache server
  vllm-b          vLLM replica B, same connector, same LMCache server

  How a KV chunk flows on CPU:

  vLLM (prefill)  ->  LMCacheMPConnector  ->  lmcache-server (L1)  ->  Valkey (L2)
```

The CPU build has no in-worker KV connector, so both replicas hand their KV to
the standalone LMCache server over the multi-process connector. The server writes
through to Valkey (its L2 backend), which is what makes one replica's KV visible
to the other.

## Prerequisites

- **A container runtime with Compose** (Docker Compose or compatible).
- **Memory.** The default two-replica walkthrough needs about **16 GiB** of RAM
  for your container runtime (each vLLM replica is ~4–5 GiB; the LMCache server
  and Valkey add a little more). On a smaller machine (~10 GiB) you can run a
  single replica — see the "Running on a smaller machine" section in the notebook.
- **Python 3.12** for the notebook client.
- **Disk.** The stack pulls about 5 GiB on first run (the vLLM CPU image ~3.7 GiB,
  the Valkey image ~0.4 GiB, and the model ~1 GiB).

## Getting started

Run these once, from a terminal, in this directory
(`cookbooks/kv-caching/`).

**1. Clone the repository and switch to the notebook folder:**

```bash
git clone https://github.com/valkey-io/valkey-samples.git
cd valkey-samples/cookbooks/kv-caching
```

**2. Start the stack** (Valkey, the LMCache server, and both vLLM replicas).
This checks that the runtime exposes enough memory first, then blocks until every
container is healthy:

```bash
docker_memory_bytes="$(docker info --format "{{.MemTotal}}")"
if [ "$docker_memory_bytes" -lt 16732614656 ]; then
  echo "This two-replica example needs about 16 GiB of Docker memory (this check allows a little under, for container-runtime overhead). Increase the Docker memory limit and retry."
else
  docker compose up -d --wait
  docker compose ps -a
fi
```

Both `vllm-a` and `vllm-b` must be `Up` and `healthy`. The first run takes a few
minutes while Docker pulls the image, the containers install pinned packages, and
the model downloads; later runs reuse the cached image layers and model volume.

**3. Create the notebook environment and kernel:**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name kv-caching-valkey
```

**4. Open the notebook and run it:**

```bash
.venv/bin/jupyter lab kv-caching-with-valkey.ipynb
```

Select the `kv-caching-valkey` kernel, then run the cells top to bottom. Each
cell prints what to look for — key counts and Valkey `GET` calls — so you can
watch the cache fill and get reused.

**5. Tear down when you're done:**

```bash
docker compose down
```

## Running on a smaller machine (one replica)

The default walkthrough runs two vLLM replicas to show cross-instance cache
sharing, which needs about 16 GiB. If your machine has less (about 10 GiB is
enough), run a single replica instead. You still see the core win — a cold turn
stores its KV in Valkey and a warm turn reads it back — just not cross-replica
sharing.

Start only replica A (Compose also starts `valkey` and `lmcache-server`, which
it depends on):

```bash
docker compose up -d --wait vllm-a
```

Then run the notebook as usual, but skip the one cell that calls the second
replica — it's the cell under **"A second replica hits the first replica's
cache,"** marked in the notebook as the only cell to skip in single-replica mode.

## What's in this directory

| File | Purpose |
| --- | --- |
| [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) | The cookbook — run this |
| [`docker-compose.yml`](docker-compose.yml) | Starts Valkey, the LMCache server, and two vLLM replicas |
| [`lmcache_config.yaml`](lmcache_config.yaml) | Documents the Valkey L2 adapter spec — the line that makes Valkey the LMCache backend |
| [`requirements.txt`](requirements.txt) | Pinned Python dependencies for the notebook's client |
| [`test_lmcache_valkey.py`](test_lmcache_valkey.py) | Tests: config + compose wiring always; live cache-hit signals when the stack is up |

## Running the tests

The config and compose-wiring tests run without the stack. The live tests
exercise the cache-hit signals and run only when the stack is up:

```bash
docker compose up -d --wait
.venv/bin/python -m pytest test_lmcache_valkey.py -v
```
