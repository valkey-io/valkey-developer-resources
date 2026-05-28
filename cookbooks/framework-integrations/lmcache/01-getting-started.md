# Getting Started with LMCache + Valkey

> Offload LLM KV caches to Valkey and cut time-to-first-token by up to 10× on repeated or prefix-sharing prompts — in under 15 minutes.

**Beginner** · Python · ~15 min

LMCache is a KV cache management layer for LLM inference engines (vLLM, SGLang). Instead of recomputing attention key/value tensors for every request, LMCache stores them externally and reloads them when the same (or prefix-matching) prompt appears again. Valkey serves as the remote storage backend — a high-throughput, low-latency store that persists KV caches across requests and even across engine restarts.

## How It Works

```
Request arrives at vLLM
  → LMCache checks if KV cache exists in Valkey (L2)
  → HIT:  load cached tensors, skip prefill computation
  → MISS: compute KV cache normally, store to Valkey for next time
```

The result: subsequent requests with shared prefixes skip the expensive prefill phase entirely.

## Prerequisites

- Linux with NVIDIA GPU (CUDA)
- Docker installed (for Valkey)
- Python 3.10+
- Sufficient GPU memory to run a small LLM (e.g., Qwen3-8B needs ~16 GB)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Dependencies

```bash
pip install vllm lmcache
```

LMCache integrates directly with vLLM v1 via the `LMCacheConnectorV1` KV transfer connector.

## Step 3: Create the LMCache Configuration

Create a file named `lmcache_config.yaml`:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://localhost:6379"
remote_serde: "naive"
```

This configures:
- **chunk_size**: KV cache is split into 256-token chunks for storage
- **local_cpu**: Enable CPU memory as L1 cache (fast, limited capacity)
- **max_local_cpu_size**: Cap L1 at 5 GB
- **remote_url**: Valkey as the L2 backend (persistent, larger capacity)
- **remote_serde**: Serialization format for KV tensors

## Step 4: Launch vLLM with LMCache

```bash
PYTHONHASHSEED=0 \
LMCACHE_CONFIG_FILE=lmcache_config.yaml \
vllm serve Qwen/Qwen3-8B \
    --gpu-memory-utilization 0.8 \
    --kv-transfer-config \
    '{"kv_connector":"LMCacheConnectorV1", "kv_role":"kv_both"}'
```

Key parameters:
- `kv_connector`: Tells vLLM to use LMCache for KV cache management
- `kv_role`: `kv_both` means this instance both stores and loads cached KV data

Wait until you see `Uvicorn running on http://0.0.0.0:8000`.

## Step 5: Send a Request (Cold — No Cache)

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "Explain the architecture of transformer models in detail, covering attention mechanisms, positional encoding, and feed-forward layers.",
    "max_tokens": 50,
    "temperature": 0
  }' | python -m json.tool
```

In the vLLM logs you'll see:

```
LMCache INFO: Storing KV cache for 35 out of 35 tokens for request ...
```

The KV cache is now stored in Valkey.

## Step 6: Send the Same Request (Warm — Cache Hit)

```bash
curl -s http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "prompt": "Explain the architecture of transformer models in detail, covering attention mechanisms, positional encoding, and feed-forward layers.",
    "max_tokens": 50,
    "temperature": 0
  }' | python -m json.tool
```

Now the logs show:

```
LMCache INFO: Reqid: ..., Total tokens 35, LMCache hit tokens: 34, need to load: 2
```

The prefill computation was skipped — the KV cache was loaded directly from Valkey.

## Step 7: Verify Cache in Valkey

You can confirm data is stored in Valkey:

```bash
docker exec valkey valkey-cli DBSIZE
# (integer) > 0
```

## Offline Inference (Python API)

You can also use LMCache programmatically without the server:

```python
import os

os.environ["LMCACHE_CHUNK_SIZE"] = "256"
os.environ["LMCACHE_LOCAL_CPU"] = "True"
os.environ["LMCACHE_MAX_LOCAL_CPU_SIZE"] = "5.0"
os.environ["LMCACHE_REMOTE_URL"] = "valkey://localhost:6379"
os.environ["LMCACHE_REMOTE_SERDE"] = "naive"

from vllm import LLM, SamplingParams
from vllm.config import KVTransferConfig

llm = LLM(
    model="Qwen/Qwen3-8B",
    kv_transfer_config=KVTransferConfig(
        kv_connector="LMCacheConnectorV1",
        kv_role="kv_both",
    ),
    max_model_len=8000,
    gpu_memory_utilization=0.8,
)

sampling_params = SamplingParams(temperature=0, max_tokens=50)

# First run — cold, stores KV cache to Valkey
prompt = "Explain the architecture of transformer models in detail."
outputs = llm.generate([prompt], sampling_params)
print(f"First run: {outputs[0].outputs[0].text!r}")

# Second run — warm, loads KV cache from Valkey
outputs = llm.generate([prompt], sampling_params)
print(f"Second run: {outputs[0].outputs[0].text!r}")

# Cleanup
from lmcache.v1.cache_engine import LMCacheEngineBuilder
from lmcache.integration.vllm.utils import ENGINE_NAME
LMCacheEngineBuilder.destroy(ENGINE_NAME)
```

## What's Happening Under the Hood

| Layer | Storage | Latency | Capacity |
|-------|---------|---------|----------|
| GPU KV cache | VRAM | ~0 | Limited by `gpu_memory_utilization` |
| L1 (CPU) | System RAM | ~μs | `max_local_cpu_size` (5 GB default) |
| L2 (Valkey) | Network | ~ms | Bounded by Valkey instance memory |

When L1 fills up, LMCache evicts to L2 (Valkey). On a cache miss in L1, it checks L2 before recomputing. This tiered approach gives you GPU-speed for hot data and Valkey-backed persistence for the long tail.

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `chunk_size` | 256 | Tokens per KV cache chunk |
| `local_cpu` | true | Enable CPU L1 cache |
| `max_local_cpu_size` | 5.0 | L1 capacity in GB |
| `remote_url` | — | `valkey://host:port` for L2 backend |
| `remote_serde` | — | Serialization: `naive` (fast) or `cachegen` (compressed) |

---

[02 - KV Cache Sharing →](02-kv-cache-sharing.md)
