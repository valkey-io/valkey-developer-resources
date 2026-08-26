# LMCache + Valkey

> Use Valkey as the KV-cache store for LLM inference, wired up through LMCache.

[LMCache](https://github.com/LMCache/LMCache) is a KV-cache layer for inference engines like vLLM. It saves the attention key/value tensors an LLM computes for a prompt so a later request with the same prefix can reload them instead of recomputing, which cuts time-to-first-token. Those tensors are larger than GPU memory can hold for long, so LMCache offloads them to an external store. Valkey is a good fit for that store: it is network-attached, shared across inference workers, and can be configured to persist. This series shows how to set that up and watch a cache hit end-to-end.

**Who is this for:** Developers self-deploying LLMs who want to cut redundant prefill work and improve inference latency. You do not need a GPU to follow along. The notebooks run LMCache's Valkey connector on CPU.

## Format

These cookbooks are **Jupyter notebooks**; run the cells as you read. Each notebook drives LMCache's Valkey connector against a Valkey server on CPU; the full vLLM inference path (which needs a Linux/GPU host) is documented as an optional extension in chapter 03.

## Prerequisites

- A container runtime with Compose support (e.g. Docker Engine / Docker CLI) to run Valkey locally
- Python 3.10 or newer (LMCache requires `>=3.10,<3.14`)

The notebooks run entirely on CPU against a local Valkey. Exact versions are pinned in [`requirements.txt`](requirements.txt) (tested with `lmcache==0.5.2`).

Follow the steps below to set up the environment, from this directory:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name lmcache
```

Then start Jupyter and open a notebook with the `lmcache` kernel:

```bash
.venv/bin/python -m jupyter lab   # or: jupyter notebook
```

VS Code works too: open a `.ipynb` and select the `lmcache` kernel.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Intro to KV Caching with Valkey](01-intro-to-kv-caching-with-valkey.ipynb)</nobr> | Why KV caching speeds up inference, then a store-and-load of a KV tensor through LMCache's Valkey connector. | Beginner, ~15 min, Python |
| 02 | <nobr>[Sharing KV Caches Across Instances](02-sharing-kv-caches-across-instances.ipynb)</nobr> | Two workers sharing one Valkey-backed cache — the second reads what the first wrote. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Scaling to Production](03-scaling-to-production.ipynb)</nobr> | Cluster mode, TLS, monitoring, and wiring the connector under a real vLLM server. | Advanced, ~20 min, Python |

## What's in this directory

| File | Purpose |
| --- | --- |
| `01`–`03` `.ipynb` | The cookbook notebooks |
| `common.py` | Shared helpers imported by the notebooks and tests |
| `lmcache_config.yaml` | Example LMCache config loaded in chapter 01 |
| `requirements.txt` | Pinned Python dependencies |
| `docker-compose.yml` | Starts Valkey on `127.0.0.1:6379` |
| `test_lmcache_valkey.py` | CI tests (config loading, key generation, real Valkey round trips) |

## Running the tests

```bash
docker compose up -d --wait
.venv/bin/python -m pytest test_lmcache_valkey.py -v
```

## Teardown

```bash
docker compose down
```
