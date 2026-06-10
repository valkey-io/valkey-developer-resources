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
- ~150 GB disk space (Dynamo container image is 20+ GB)

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

> **Multiple terminals:** The frontend is started in the background (`&`). Steps 3–4 can run sequentially in the same shell. Alternatively, open additional shells with `docker exec -it <container_id> bash`.

## Step 2b: Install valkey-glide

LMCache's Valkey connector uses the GLIDE client, which is not pre-installed in the Dynamo container. Install it:

```bash
pip install valkey-glide
python3 -c "from glide import GlideClient; print('valkey-glide: OK')"
```

## Step 3: Start the Dynamo Frontend

Dynamo requires a NATS server for internal runtime communication, even with file-based discovery:

```bash
docker run -d --name nats --network host nats:latest
```

Inside the Dynamo container, start the frontend:

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
LMCACHE_CHUNK_SIZE=128 \
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
- **`LMCACHE_MAX_LOCAL_CPU_SIZE`**: L1 cache capacity in GB (per-worker)
- **`LMCACHE_CHUNK_SIZE`**: Tokens per KV cache block (prompt must exceed this to trigger L2 storage)
- **`kv_connector: LMCacheConnectorV1`**: In-process KV cache connector
- **`kv_role: kv_both`**: This worker both stores and loads cached KV data

Wait until you see the worker register with the frontend. Verify with:

```bash
curl -sf http://localhost:8000/health && echo OK
```

## Step 5: Test the Integration

> **Note:** LMCache stores KV cache in chunks of 128 tokens (as configured above). Your prompt must exceed this threshold to trigger L2 storage. Short prompts stay in GPU memory only.

**First request (cold — computes and stores KV cache):**

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
      {"role": "system", "content": "You are an expert systems architect specializing in distributed computing, machine learning infrastructure, and high-performance computing. You provide extremely detailed, comprehensive technical explanations that cover theoretical foundations, practical implementation details, performance characteristics, failure modes, and optimization strategies. When explaining a concept, you always include: historical context and motivation, mathematical or algorithmic foundations where relevant, concrete implementation examples with code or pseudocode, performance analysis including time complexity and space complexity, common pitfalls and how to avoid them, comparison with alternative approaches, and real-world deployment considerations including monitoring, scaling, and maintenance."},
      {"role": "user", "content": "Explain the KV cache mechanism in transformer-based large language models. Cover how attention computation works, why caching key and value tensors eliminates redundant computation during autoregressive decoding, the memory implications of storing KV caches for long sequences, and how multi-tier caching hierarchies (GPU VRAM, host CPU RAM, remote distributed storage) can extend effective cache capacity beyond single-device memory limits."}
    ],
    "max_tokens": 50
  }'
```

LMCache stores the KV cache to L1 (CPU RAM) and L2 (Valkey).

**Second request (warm — cache hit):**

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
      {"role": "system", "content": "You are an expert systems architect specializing in distributed computing, machine learning infrastructure, and high-performance computing. You provide extremely detailed, comprehensive technical explanations that cover theoretical foundations, practical implementation details, performance characteristics, failure modes, and optimization strategies. When explaining a concept, you always include: historical context and motivation, mathematical or algorithmic foundations where relevant, concrete implementation examples with code or pseudocode, performance analysis including time complexity and space complexity, common pitfalls and how to avoid them, comparison with alternative approaches, and real-world deployment considerations including monitoring, scaling, and maintenance."},
      {"role": "user", "content": "Explain the KV cache mechanism in transformer-based large language models. Cover how attention computation works, why caching key and value tensors eliminates redundant computation during autoregressive decoding, the memory implications of storing KV caches for long sequences, and how multi-tier caching hierarchies (GPU VRAM, host CPU RAM, remote distributed storage) can extend effective cache capacity beyond single-device memory limits."}
    ],
    "max_tokens": 50
  }'
```

LMCache loads the KV cache from L1 or L2 — skipping prefill for cached chunks. Check the worker logs for:

```
LMCache hit tokens: 128
```

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

## Quick Launch Alternative

For production deployments using the MP sidecar architecture (requires LMCache with the `resp` L2 adapter, available in newer LMCache versions), Dynamo provides:

```bash
./examples/backends/vllm/launch/agg_lmcache_mp.sh
```

The in-process `LMCacheConnectorV1` approach shown above is simpler and works with the bundled LMCache version.

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
