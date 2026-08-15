# LMCache + Valkey Cookbook Sample

Runnable code for the [LMCache + Valkey cookbook series](../README.md).

> **Scope:** This sample exercises LMCache's real config-loading and
> key-generation code (`lmcache.v1.config.load_engine_config_with_overrides`,
> `lmcache.utils.CacheEngineKey`) against a real local Valkey server. It does
> **not** run vLLM or require a GPU. Running the full inference pipeline
> (vLLM + LMCache + Valkey, with actual TTFT reduction) additionally requires
> an NVIDIA GPU — see [LMCache's own example](https://github.com/LMCache/LMCache/tree/v0.5.2/examples/kv_cache_reuse/remote_backends/valkey)
> for that walkthrough.

## Prerequisites

- Docker
- Python 3.10 or newer (LMCache requires `>=3.10,<3.14`)
- No API keys or external services needed

## Setup

Run these commands from this directory:

```bash
docker compose up -d --wait
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> **Use `pip`, not `uv`, for this install.** PyPI has no pre-built wheel for `lmcache==0.5.2` — only
> a source distribution, which `pip` builds locally and correctly detects "no GPU" on a CPU-only
> machine, excluding CUDA-only dependencies. `uv pip install` resolves this same sdist differently
> and pulls in `cupy-cuda13x` (Linux/Windows only, no macOS wheel), which fails hard on macOS with
> `No solution found when resolving dependencies`. This is an LMCache packaging quirk, not something
> this cookbook controls — stick with `pip` until upstream publishes platform-specific wheels.

## Running Tests

```bash
.venv/bin/python -m pytest test_lmcache_valkey.py -v
```

Tests verify (all CPU-only, no GPU):

- LMCache's real config loader accepts standalone, cluster, and TLS/serverless configs
- LMCache's real config loader rejects invalid configs
- The MP-mode `--l2-adapter` JSON generator produces expected fields, and the generated dict
  round-trips through LMCache's real `ValkeyL2AdapterConfig.from_dict` parser
- Host-string parsing rejects unsafe characters (CWE-1284)
- `CacheEngineKey`-based cache keys are deterministic and match LMCache's real wire format
- Real Valkey store/hit/miss round trips, including cross-instance sharing

## Running the Scripts

```bash
# 01 - Getting started: load a real LMCache config, store/inspect a simulated chunk
python getting_started.py

# 02 - KV cache sharing: two simulated instances sharing a chunk via Valkey
python kv_cache_sharing.py

# 03 - Production config generator + validator + monitor
python production_deployment.py --mode standalone --monitor
python production_deployment.py --mode cluster --host my-cluster.endpoint:6379
python production_deployment.py --mode serverless --host my-cache.serverless.region.cache.amazonaws.com:6379
python production_deployment.py --mode mp --host 127.0.0.1:6379
python production_deployment.py --mode mp --host my-cluster.endpoint:6379 --cluster-mode
```

## Sample Scripts

| Script | Cookbook | Description |
| -------- | --------- | -------------- |
| `common.py` | — | Shared LMCache config loading, key generation, and GLIDE client helpers |
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Load a real LMCache config, store/inspect a simulated KV cache chunk |
| `kv_cache_sharing.py` | [02 - KV Cache Sharing](../02-kv-cache-sharing.md) | Two simulated instances sharing a chunk via a real Valkey backend |
| `production_deployment.py` | [03 - Production Deployment](../03-production-deployment.md) | Generate + validate configs (standalone/cluster/serverless/MP mode), monitor cache stats |

## Environment Variables

| Variable | Default | Description |
| ---------- | --------- | -------------- |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `LMCACHE_LOG_LEVEL` | `WARNING` (set by `common.py`) | LMCache's own log verbosity. LMCache defaults to `INFO`, which dumps its entire internal config (100+ fields) on every load; `common.py` quiets this for readable sample output. Set to `INFO` yourself to see the full dump. |

## Why Not Run vLLM Directly?

LMCache's Valkey connector is normally driven by vLLM during real inference,
which requires a Linux machine with an NVIDIA GPU — it hooks into vLLM's
internal KV cache tensors. That can't run in this repo's CI or on most
readers' laptops. Instead of shipping untested vLLM/GPU code (as the
original version of this cookbook did), this sample exercises the parts of
the integration that genuinely run anywhere: LMCache's config parsing and
its Valkey key format, verified against `lmcache==0.5.2` and executed
against a real Valkey server.

## Teardown

```bash
docker compose down
```
