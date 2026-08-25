# LMCache + Valkey

> Offload LLM KV caches to Valkey with LMCache — store, share, and reload real KV-cache tensors on CPU, no GPU required to follow along.

**Who is this for:** Developers who want to self-deploy LLMs and optimize inference throughput and latency. This series explains what KV caching is and shows how to set up KV caching with Valkey and [LMCache](https://github.com/LMCache/LMCache), so you can watch a real cache hit end-to-end on your own machine.

## Format

These cookbooks are **Jupyter notebooks** — run the cells as you read. Each notebook drives LMCache's real Valkey connector against a real Valkey server on CPU; the full vLLM inference path (which needs a Linux/GPU host) is documented as an optional extension in chapter 03.

## Prerequisites

- Docker (to run Valkey locally)
- Python 3.10 or newer (LMCache requires `>=3.10,<3.14`)
- No API keys, GPU, or paid services needed for the notebooks

Set up once, from this directory:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name lmcache
```

Then open the notebooks with the `lmcache` kernel (`jupyter lab` / `jupyter notebook`, or VS Code).

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Intro to KV Caching with Valkey](01-intro-to-kv-caching-with-valkey.ipynb)</nobr> | What KV caching is, and a real store-and-load of a KV tensor through LMCache's Valkey connector. | Beginner, ~15 min, Python |
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
