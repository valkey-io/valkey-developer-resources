# KV Cache Sharing Across Instances

> Share computed KV caches across multiple vLLM instances through Valkey. One instance computes, the entire fleet benefits — cutting redundant prefill across your serving cluster.

**Intermediate** · Python · ~20 min

## Why Share KV Caches?

In production LLM serving, multiple vLLM instances handle the same system prompts, few-shot examples, and frequently asked questions. Without sharing, each instance recomputes identical KV caches independently — wasting GPU cycles.

With Valkey as a centralized L2 store:

```
Instance A computes KV cache for prompt → stores to Valkey
Instance B receives same prompt → loads from Valkey, skips prefill
```

This is especially impactful for:
- **System prompts**: Every request shares the same prefix
- **RAG pipelines**: Retrieved context chunks repeat across users
- **Multi-turn chat**: Conversation history is reprocessed on each turn

## Prerequisites

- 2+ GPUs (one per vLLM instance)
- Docker installed
- Completed [01 - Getting Started](01-getting-started.md)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

## Step 2: Create Shared Configuration

Create `lmcache_config.yaml` — both instances will use the same config:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://localhost:6379"
remote_serde: "cachegen"
```

> **Note:** We use `cachegen` serialization here instead of `naive`. CacheGen compresses KV tensors before storing, reducing network bandwidth and Valkey memory usage at the cost of slight CPU overhead — a good trade-off for cross-instance sharing.

**Important:** For cross-process KV cache sharing, all instances must use the same `PYTHONHASHSEED` to ensure consistent chunk hashing:

```bash
export PYTHONHASHSEED=0
```

## Step 3: Launch Instance A (GPU 0)

```bash
PYTHONHASHSEED=0 \
LMCACHE_CONFIG_FILE=lmcache_config.yaml \
CUDA_VISIBLE_DEVICES=0 \
vllm serve Qwen/Qwen3-8B \
    --gpu-memory-utilization 0.8 \
    --port 8000 \
    --kv-transfer-config \
    '{"kv_connector":"LMCacheConnectorV1", "kv_role":"kv_both"}'
```

## Step 4: Launch Instance B (GPU 1)

In a separate terminal:

```bash
PYTHONHASHSEED=0 \
LMCACHE_CONFIG_FILE=lmcache_config.yaml \
CUDA_VISIBLE_DEVICES=1 \
vllm serve Qwen/Qwen3-8B \
    --gpu-memory-utilization 0.8 \
    --port 8001 \
    --kv-transfer-config \
    '{"kv_connector":"LMCacheConnectorV1", "kv_role":"kv_both"}'
```

Wait until both instances report `Uvicorn running`.

## Step 5: Populate the Cache via Instance A

Send a request to Instance A:

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "You are a helpful AI assistant specializing in distributed systems. Explain the CAP theorem and its implications for modern databases.",
    "max_tokens": 50,
    "temperature": 0
  }' | python -m json.tool
```

Instance A logs:

```
LMCache INFO: Storing KV cache for 42 out of 42 tokens for request ...
```

## Step 6: Retrieve from Cache via Instance B

Send the same request to Instance B:

```bash
curl -s http://localhost:8001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "You are a helpful AI assistant specializing in distributed systems. Explain the CAP theorem and its implications for modern databases.",
    "max_tokens": 50,
    "temperature": 0
  }' | python -m json.tool
```

Instance B logs:

```
LMCache INFO: Reqid: ..., Total tokens 42, LMCache hit tokens: 41, need to load: 2
```

Instance B loaded the KV cache from Valkey without recomputing it — the prefill phase was skipped entirely.

## Step 7: Measure the Improvement

Use a simple timing script to quantify the difference:

```python
import requests
import time

PROMPT = (
    "You are a helpful AI assistant specializing in distributed systems. "
    "Explain the CAP theorem and its implications for modern databases."
)

payload = {
    "model": "Qwen/Qwen3-8B",
    "prompt": PROMPT,
    "max_tokens": 1,
    "temperature": 0,
}

# Cold request to Instance A (computes + stores)
t0 = time.perf_counter()
requests.post("http://localhost:8000/v1/completions", json=payload)
cold_ms = (time.perf_counter() - t0) * 1000

# Warm request to Instance B (loads from Valkey)
t0 = time.perf_counter()
requests.post("http://localhost:8001/v1/completions", json=payload)
warm_ms = (time.perf_counter() - t0) * 1000

print(f"Instance A (cold): {cold_ms:.0f}ms")
print(f"Instance B (warm): {warm_ms:.0f}ms")
print(f"Speedup: {cold_ms / warm_ms:.1f}x")
```

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  vLLM + LMCache   │  vLLM + LMCache
│  Instance A  │     │  Instance B  │
│  (GPU 0)     │     │  (GPU 1)     │
└──────┬───────┘     └──────┬───────┘
       │  store              │  load
       │                     │
       ▼                     ▼
┌─────────────────────────────────────┐
│            Valkey (L2)              │
│   Shared KV cache storage           │
│   valkey://localhost:6379            │
└─────────────────────────────────────┘
```

Both instances read and write to the same Valkey store. The chunk hashing ensures that identical prompt prefixes map to the same keys regardless of which instance computed them.

## Prefix Sharing

KV cache sharing works at the **prefix level**, not just exact matches. If Instance A processes:

```
"You are a helpful AI assistant. What is 2+2?"
```

And Instance B later processes:

```
"You are a helpful AI assistant. Explain quantum computing."
```

Instance B will hit the cache for the shared prefix ("You are a helpful AI assistant.") and only compute the KV cache for the diverging suffix.

## Serialization Options

| Format | Speed | Size | Best For |
|--------|-------|------|----------|
| `naive` | Fastest | Largest | Single-instance, local network |
| `cachegen` | Moderate | ~4× smaller | Cross-instance, bandwidth-constrained |

For multi-instance sharing over a network, `cachegen` typically wins because the reduced transfer size more than compensates for compression overhead.

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
