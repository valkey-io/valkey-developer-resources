# KV Caching with Valkey

> Use Valkey as the shared KV-cache store for vLLM inference, wired up through LMCache — a cache that survives restarts and is shared across every replica.

When an LLM answers a prompt it first computes attention key/value tensors for every input token (the *prefill* step), then throws that work away. Any later request that shares a prompt prefix — the next turn of a chat, a shared system prompt, RAG over the same documents — would recompute exactly the same KV. [LMCache](https://github.com/LMCache/LMCache) caches that KV and reloads it on a prefix match, so prefill happens once: lower cost per request and a shorter time-to-first-token. Valkey is where that KV lives. Unlike vLLM's built-in prefix cache, which sits inside one engine process and dies with it, a Valkey-backed cache is bigger, shared across replicas, and survives restarts.
This cookbook is a single [Jupyter notebook](kv-caching-with-valkey.ipynb): run a real multi-turn chat against a vLLM + LMCache + Valkey stack and watch a cold turn populate Valkey, a warm turn hit the cached prefix, and a second replica reuse the first replica's cache.

## Architecture

The stack has four containers, and a KV chunk flows through them like this:

```
vLLM (prefill)  ->  LMCacheMPConnector  ->  lmcache server (L1)  ->  Valkey (L2)
```

- **vLLM** (two replicas) runs inference and produces the KV state during prefill.
- **LMCache** moves that KV out of vLLM. On CPU, vLLM has no in-worker KV connector, so each replica uses the **multi-process connector** (`LMCacheMPConnector`) and hands its KV to a standalone `lmcache server`.
- **lmcache server** owns KV storage: a small L1 tier in its own memory, writing through to a second tier (L2).
- **Valkey** is that L2 tier, a shared store on the network that holds the KV so it outlives any one replica and stays reusable across replicas. What makes Valkey the backend is the server's L2 adapter spec (see [Pointing LMCache at Valkey](#pointing-lmcache-at-valkey)).

**Who is this for:** Developers self-deploying LLMs with vLLM who want to cut redundant prefill work and improve inference latency.

## Prerequisites

- A container runtime with Compose support (e.g. Docker Engine / Docker CLI) to run the stack locally.
- **Memory for the stack.** Give the Docker VM **at least 10 GiB** of RAM (Docker Desktop: Settings → Resources → Memory). Each vLLM replica needs roughly 3–4 GiB; the LMCache server and Valkey add a little more. On a smaller machine, run one replica and skip the two-replica step.
- Python 3.10–3.13 for the notebook client (LMCache requires `>=3.10,<3.14`).

The stack runs on CPU with `facebook/opt-125m`, which is small and ungated — no GPU and no Hugging Face token required. Exact versions are pinned in [`requirements.txt`](requirements.txt) and [`docker-compose.yml`](docker-compose.yml).

## Setup

Start the stack (Valkey, the LMCache server, and both vLLM replicas) from this directory:

```bash
docker compose up -d --wait
```

`--wait` blocks until every container is healthy. The first run is slow — the vLLM image is large, each replica compiles the model on startup, and the LMCache server installs its dependencies — so allow several minutes.

Then create the notebook environment and kernel:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name kv-caching-valkey
```

Start Jupyter and open the notebook with the `kv-caching-valkey` kernel:

```bash
.venv/bin/python -m jupyter lab   # or: jupyter notebook
```

VS Code works too: open the `.ipynb` and select the `kv-caching-valkey` kernel.

### Pointing LMCache at Valkey

The integration lives in the LMCache server's **L2 adapter**. In [`docker-compose.yml`](docker-compose.yml) the server starts with the command below, and its `--l2-adapter` spec is what makes Valkey the backing store:

```bash
lmcache server --l1-size-gb 2 --eviction-policy noop \
  --l2-adapter '{"type":"valkey","startup_nodes":"valkey:6379"}'
```

[`lmcache_config.yaml`](lmcache_config.yaml) documents the same spec and the options you are most likely to change (cluster mode, key prefix, TLS, auth). The server needs the `valkey-glide-sync` client for this adapter and installs it on startup; the plain async `valkey-glide` is not sufficient.

See the [LMCache Valkey backend docs](https://docs.lmcache.ai/kv_cache/valkey.html) for the full option set.

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

## What's in this directory

| File | Purpose |
| --- | --- |
| [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) | The cookbook: a multi-turn chat end-to-end on a real vLLM + LMCache + Valkey stack |
| `docker-compose.yml` | Starts Valkey, the LMCache server, and two vLLM replicas (`vllm-a`, `vllm-b`) sharing one Valkey |
| `lmcache_config.yaml` | Documents the Valkey L2 adapter spec — the line that makes Valkey the LMCache backend |
| `chat_template.jinja` | Minimal chat template so `opt-125m` can serve `/v1/chat/completions` |
| `requirements.txt` | Pinned Python dependencies for the notebook client |
| `test_lmcache_valkey.py` | CI tests: config + compose wiring always; live cache-hit signals when the stack is up |

## Running the tests

The config and compose-wiring tests run without the stack. The live tests exercise the cache-hit signals and run only when the stack is up:

```bash
docker compose up -d --wait
.venv/bin/python -m pytest test_lmcache_valkey.py -v
```

## Teardown

```bash
docker compose down
```

The KV cache lives in Valkey (the LMCache server's L2 tier): it survives a vLLM replica or the LMCache server restarting, and is cleared by `docker compose down` unless you add a persistent volume and enable Valkey persistence. The `hf-cache` volume holding the model weights persists across `down`/`up`, so later runs skip the re-download.
