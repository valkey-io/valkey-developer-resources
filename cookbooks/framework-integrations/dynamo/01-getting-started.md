# Getting Started with Dynamo + Valkey

> Deploy NVIDIA Dynamo with Valkey as the distributed KV cache backend via LMCache — enabling sub-millisecond cache lookups for multi-worker inference.

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
- 30+ GB GPU memory (for a 7-8B parameter model)
- Network access to pull Dynamo container images

## Step 1: Start Valkey

```bash
docker run -d \
  --name valkey \
  -p 6379:6379 \
  valkey/valkey:latest \
  valkey-server --maxmemory 8gb --maxmemory-policy allkeys-lru
```

The `allkeys-lru` eviction policy ensures that when memory fills, the least-recently-used KV cache blocks are evicted first — keeping hot caches warm.

## Step 2: Pull the Dynamo Container

```bash
docker pull nvcr.io/nvidia/ai-dynamo/dynamo:latest
```

This image includes Dynamo, vLLM, and LMCache pre-installed.

## Step 3: Create the Dynamo Graph Configuration

Create `dynamo_graph.py`:

```python
from dynamo.sdk import service, depends, DynamoConfig
from dynamo.vllm import VllmEngine

FrontendConfig = DynamoConfig(
    name="frontend",
    port=8000,
)

WorkerConfig = DynamoConfig(
    name="worker",
    replicas=2,
)


@service(config=FrontendConfig)
class Frontend:
    worker = depends(Worker)

    async def generate(self, request):
        return await self.worker.generate(request)


@service(config=WorkerConfig)
class Worker:
    def __init__(self):
        self.engine = VllmEngine(
            model="Qwen/Qwen3-8B",
            gpu_memory_utilization=0.85,
            kv_transfer_config={
                "kv_connector": "LMCacheConnectorV1",
                "kv_role": "kv_both",
            },
        )

    async def generate(self, request):
        return await self.engine.generate(request)
```

## Step 4: Configure LMCache to Use Valkey

Set environment variables for the Dynamo workers. Create `lmcache.env`:

```bash
LMCACHE_CHUNK_SIZE=256
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=5.0
LMCACHE_REMOTE_URL=valkey://valkey:6379
LMCACHE_REMOTE_SERDE=naive
```

## Step 5: Launch Dynamo

```bash
docker run --gpus all --network host \
  --env-file lmcache.env \
  -v $(pwd)/dynamo_graph.py:/workspace/dynamo_graph.py \
  nvcr.io/nvidia/ai-dynamo/dynamo:latest \
  dynamo serve dynamo_graph:Frontend
```

Wait for all workers to report ready. You'll see log lines like:

```
[Worker-0] Uvicorn running on http://0.0.0.0:8001
[Worker-1] Uvicorn running on http://0.0.0.0:8002
[Frontend] Router ready, serving on http://0.0.0.0:8000
```

## Step 6: Test the Integration

**First request (cold — computes and stores KV cache):**

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "Explain how KV caching reduces inference latency in transformer models.",
    "max_tokens": 100,
    "temperature": 0
  }' | python -m json.tool
```

**Second request (warm — any worker can serve from Valkey):**

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "Explain how KV caching reduces inference latency in transformer models.",
    "max_tokens": 100,
    "temperature": 0
  }' | python -m json.tool
```

Even if the router sends this to a different worker, LMCache loads the KV cache from Valkey — skipping prefill entirely.

## Step 7: Verify Cache Storage

```bash
docker exec valkey valkey-cli INFO keyspace
# db0:keys=<N>,expires=0,avg_ttl=0
```

```bash
docker exec valkey valkey-cli DBSIZE
# (integer) > 0
```

## How the Tiers Work Together

| Tier | Backend | Latency | Scope |
|------|---------|---------|-------|
| GPU KV cache | VRAM | ~0 | Single request |
| L1 (CPU) | Host RAM | ~μs | Single worker |
| L2 (Valkey) | Network | ~ms | Entire cluster |

L1 is per-worker and fast. L2 (Valkey) is shared — when Worker 0 computes a KV cache and stores it to Valkey, Worker 1 can load it directly without recomputing. This is where the cluster-wide benefit comes from.

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
