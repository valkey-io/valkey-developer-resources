# Getting Started with Dynamo + Valkey

> Deploy NVIDIA Dynamo with Valkey as the distributed KV cache backend via LMCache, enabling cluster-wide KV cache reuse across inference workers.

**Intermediate** · Python · ~25 min

NVIDIA Dynamo orchestrates multiple inference workers with intelligent request routing. When paired with LMCache and Valkey, every worker can store and retrieve KV caches from a shared remote store. A prompt computed once on any worker benefits the entire cluster.

## Architecture

```
              ┌─────────────────────────┐
              │     Dynamo Frontend      │
              │   (HTTP + KV Router)     │
              └────────────┬────────────┘
                           │ routes requests
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼───┐  ┌────▼────┐  ┌───▼─────┐
        │ Worker 0 │  │Worker 1 │  │Worker 2 │
        │  vLLM    │  │  vLLM   │  │  vLLM   │
        │+LMCache  │  │+LMCache │  │+LMCache │
        │ sidecar  │  │ sidecar │  │ sidecar │
        └────┬─────┘  └────┬────┘  └────┬────┘
             │              │             │
             └──────────────┼─────────────┘
                            │
                    ┌───────▼───────┐
                    │    Valkey     │
                    │ (Shared L2)   │
                    └───────────────┘
```

## Prerequisites

- Linux with NVIDIA GPU (Ampere+, CUDA 12+)
- Docker with NVIDIA Container Toolkit
- Sufficient GPU memory for your model (e.g., Qwen3-0.6B needs ~2 GB, Qwen3-8B needs ~16 GB)
- Network access to pull Dynamo container images from `nvcr.io`

## Step 1: Start Valkey

```bash
docker run -d \
  --name valkey \
  --network host \
  valkey/valkey:8 \
  valkey-server --maxmemory 8gb --maxmemory-policy allkeys-lru
```

The `allkeys-lru` eviction policy ensures that when memory fills, the least-recently-used KV cache blocks are evicted first — keeping hot caches warm.

Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Pull the Dynamo Container

```bash
docker run --gpus all --network host --rm -it \
  nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.0.2
```

This image includes Dynamo, vLLM, and LMCache pre-installed.

> **Hugging Face token required for gated models.** Set `export HF_TOKEN=hf_…` before launching if using Llama, Kimi, or other gated models.

## Step 3: Start the LMCache Sidecar

Inside the container, launch the LMCache MP server. This is the out-of-process cache engine that manages L1 (CPU RAM) and L2 (Valkey) storage:

```bash
lmcache server \
  --l1-size-gb 5 \
  --eviction-policy LRU \
  --l2-adapter valkey \
  --l2-adapter-url valkey://localhost:6379 \
  --chunk-size 256 &
```

Configuration:
- **`--l1-size-gb 5`**: 5 GB of host RAM as fast L1 cache
- **`--eviction-policy LRU`**: Evict least-recently-used blocks when L1 is full
- **`--l2-adapter valkey`**: Use Valkey as the L2 persistent backend
- **`--l2-adapter-url`**: Valkey connection endpoint
- **`--chunk-size 256`**: Split KV cache into 256-token chunks

## Step 4: Start the Dynamo Frontend

In a separate terminal (or background the sidecar), start the frontend:

```bash
python -m dynamo.frontend \
  --discovery-backend file \
  --http-port 8000
```

`--discovery-backend file` avoids needing etcd for single-node setups.

## Step 5: Start a vLLM Worker

In another terminal, launch the vLLM backend worker with LMCache enabled:

```bash
python -m dynamo.vllm \
  --model Qwen/Qwen3-0.6B \
  --discovery-backend file \
  --gpu-memory-utilization 0.85 \
  --disable-hybrid-kv-cache-manager \
  --kv-transfer-config '{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both"}'
```

Key parameters:
- **`kv_connector: LMCacheMPConnector`**: Connects to the LMCache sidecar process
- **`kv_role: kv_both`**: This worker both stores and loads cached KV data
- **`--disable-hybrid-kv-cache-manager`**: Required when using LMCache for external KV management

Wait until you see the worker register with the frontend.

## Step 6: Test the Integration

**First request (cold — computes and stores KV cache):**

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Explain how KV caching reduces inference latency in transformer models."}],
    "max_tokens": 100
  }'
```

The LMCache sidecar stores the KV cache to L1 (CPU RAM) and L2 (Valkey).

**Second request (warm — cache hit):**

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Explain how KV caching reduces inference latency in transformer models."}],
    "max_tokens": 100
  }'
```

LMCache loads the KV cache from L1 or L2 — skipping the expensive prefill computation.

## Step 7: Verify Cache in Valkey

```bash
docker exec valkey valkey-cli DBSIZE
# (integer) > 0
```

## How the Tiers Work Together

| Tier | Backend | Latency | Scope |
|------|---------|---------|-------|
| GPU KV cache | VRAM | ~0 | Single request |
| L1 (CPU) | Host RAM via LMCache sidecar | ~μs | Single worker |
| L2 (Valkey) | Network via LMCache sidecar | ~1-5ms | Entire cluster |

L1 is per-worker and fast. L2 (Valkey) is shared — when Worker 0 computes a KV cache and stores it to Valkey, Worker 1 can load it directly without recomputing. This is where the cluster-wide benefit comes from.

## Quick Launch Script

Dynamo provides a launch script that automates the sidecar + frontend + worker startup:

```bash
./examples/backends/vllm/launch/agg_lmcache_mp.sh
```

This starts the LMCache MP server, Dynamo frontend, and a vLLM worker with `LMCacheMPConnector` in one command.

## What Dynamo Adds Over Raw vLLM + LMCache

| Feature | vLLM + LMCache | Dynamo + LMCache + Valkey |
|---------|----------------|---------------------------|
| KV cache offloading | ✓ | ✓ |
| Multi-worker routing | ✗ | ✓ (KV-aware) |
| Cache-aware scheduling | ✗ | ✓ |
| Disaggregated prefill/decode | ✗ | ✓ |
| Auto-scaling | ✗ | ✓ (via Kubernetes operator) |

---

[02 - KV-Aware Routing →](02-kv-cache-routing.md)
