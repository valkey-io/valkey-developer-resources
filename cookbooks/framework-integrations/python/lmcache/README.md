# KV Caching with Valkey

> Use Valkey as the shared KV-cache store for vLLM inference, wired up through LMCache — a cache that survives restarts and is shared across every replica.

When an LLM answers a prompt it first computes attention key/value tensors for every input token (the *prefill* step), then throws that work away. Any later request that shares a prompt prefix — the next turn of a chat, a shared system prompt, RAG over the same documents — would recompute exactly the same KV. [LMCache](https://github.com/LMCache/LMCache) caches that KV and reloads it on a prefix match, so prefill happens once: lower cost per request and a shorter time-to-first-token. Valkey is where that KV lives. Unlike vLLM's built-in prefix cache, which sits inside one engine process and dies with it, a Valkey-backed cache is bigger, shared across replicas, and survives restarts.

This cookbook is a single [Jupyter notebook](kv-caching-with-valkey.ipynb): run a real multi-turn chat against a two-replica vLLM + LMCache + Valkey stack and watch a cold turn populate Valkey, a warm turn hit the cached prefix, and a second replica reuse the first replica's cache.

**Who is this for:** Developers self-deploying LLMs with vLLM who want to cut redundant prefill work and improve inference latency.

## Prerequisites

- A container runtime with Compose support (e.g. Docker Engine / Docker CLI) to run valkey locally.
- **Memory for two model servers.** Give the Docker VM **at least 10 GiB** of RAM (Docker Desktop: Settings → Resources → Memory) — each vLLM replica needs roughly 3–4 GiB. On a smaller machine, run one replica and skip the two-replica step.
- Python 3.10–3.13 for the notebook client (LMCache requires `>=3.10,<3.14`).

The stack runs on CPU with `facebook/opt-125m`, which is small and ungated — no GPU and no Hugging Face token required. Exact versions are pinned in [`requirements.txt`](requirements.txt) and [`docker-compose.yml`](docker-compose.yml).

## Setup

Start the stack (Valkey + both vLLM replicas) from this directory:

```bash
docker compose up -d --wait
```

`--wait` blocks until every container is healthy. The first run is slow — the vLLM image is large and each replica compiles the model on startup — so allow several minutes.

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

The entire integration is one line — the `remote_url` in [`lmcache_config.yaml`](lmcache_config.yaml), which both replicas load:

```yaml
remote_url: "valkey://valkey:6379"
```

See the [LMCache Valkey/Redis backend docs](https://docs.lmcache.ai/kv_cache/redis.html) for other backends and options.

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

## What's in this directory

| File | Purpose |
| --- | --- |
| [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) | The cookbook: a multi-turn chat end-to-end on a real vLLM + LMCache + Valkey stack |
| `docker-compose.yml` | Starts Valkey + two vLLM replicas (`vllm-a`, `vllm-b`) sharing one Valkey |
| `lmcache_config.yaml` | LMCache config both replicas load; the one line pointing LMCache at Valkey |
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

The KV cache lives in the Valkey container's memory: it survives a vLLM replica restarting, and is cleared by `docker compose down` unless you add a persistent volume and enable Valkey persistence. The `hf-cache` volume holding the model weights persists across `down`/`up`, so later runs skip the re-download.
