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
        │ (GLIDE)  │  │ (GLIDE) │  │ (GLIDE) │
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

> **Note:** LMCache uses standard Valkey commands (`SET`/`GET`) for KV cache storage — no search or JSON modules are required. The base `valkey/valkey` image is sufficient.

```bash
docker run -d \
  --name valkey \
  --network host \
  valkey/valkey:9.1.0 \
  valkey-server --maxmemory 8gb --maxmemory-policy allkeys-lru
```

```bash
# Or with podman (for Valkey only — Dynamo container requires Docker + NVIDIA Container Toolkit):
podman run -d \
  --name valkey \
  --network host \
  valkey/valkey:9.1.0 \
  valkey-server --maxmemory 8gb --maxmemory-policy allkeys-lru
```

The `allkeys-lru` eviction policy ensures that when memory fills, the least-recently-used KV cache blocks are evicted first — keeping hot caches warm.

Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

> ⚠️ This example connects without authentication for local development. Always enable authentication and TLS for production deployments. See [03 - Production Deployment](03-production-deployment.md) for the secure configuration.

## Step 2: Pull the Dynamo Container

```bash
docker run --gpus all --network host --rm -it \
  -e HF_TOKEN \
  nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.1.1
```

This image includes Dynamo, vLLM, and LMCache pre-installed.

> **Hugging Face token required for gated models.** Set `export HF_TOKEN=hf_…` before launching if using Llama, Kimi, or other gated models. The `-e HF_TOKEN` flag forwards it into the container.

> **Multiple terminals:** Steps 3–5 each need their own shell inside the container. Open additional shells with `docker exec -it <container_id> bash`, or start `tmux` inside the container before proceeding.

## Step 2b: Install valkey-glide

LMCache's Valkey connector uses the GLIDE client, which is not pre-installed in the Dynamo container. Install it:

```bash
pip install valkey-glide
```

## Step 3: Start the Dynamo Frontend

Inside the container, start the frontend:

```bash
python3 -m dynamo.frontend \
  --discovery-backend file \
  --http-port 8000 &
```

`--discovery-backend file` avoids needing etcd for single-node setups.

## Step 4: Start a vLLM Worker with Valkey KV Cache

In the same container, launch the vLLM backend worker with LMCache configured to use Valkey via GLIDE:

```bash
LMCACHE_REMOTE_URL="valkey://localhost:6379" \
LMCACHE_REMOTE_SERDE="naive" \
LMCACHE_LOCAL_CPU=true \
LMCACHE_MAX_LOCAL_CPU_SIZE=5.0 \
LMCACHE_CHUNK_SIZE=256 \
python3 -m dynamo.vllm \
  --model Qwen/Qwen3-0.6B \
  --discovery-backend file \
  --gpu-memory-utilization 0.85 \
  --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}'
```

Key parameters:
- **`LMCACHE_REMOTE_URL`**: Valkey endpoint — LMCache uses GLIDE to connect
- **`LMCACHE_REMOTE_SERDE`**: Serialization format (`naive` = fast, uncompressed)
- **`LMCACHE_LOCAL_CPU`**: Enable CPU RAM as L1 cache (fast, per-worker)
- **`kv_connector: LMCacheConnectorV1`**: In-process KV cache connector
- **`kv_role: kv_both`**: This worker both stores and loads cached KV data

Wait until you see the worker register with the frontend. Verify with:

```bash
curl -sf http://localhost:8000/health && echo OK
```

## Step 5: Test the Integration

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

## Step 6: Verify Cache in Valkey

```bash
docker exec valkey valkey-cli DBSIZE
# (integer) > 0
```

## How the Tiers Work Together

| Tier | Backend | Latency | Scope |
|------|---------|---------|-------|
| GPU KV cache | VRAM | ~0 | Single request |
| L1 (CPU) | Host RAM via LMCache (in-process) | ~μs | Single worker |
| L2 (Valkey) | Network via GLIDE client | ~1-5ms | Entire cluster |

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

[← Back to Dynamo + Valkey](README.md) · [02 - KV-Aware Routing →](02-kv-cache-routing.md)
