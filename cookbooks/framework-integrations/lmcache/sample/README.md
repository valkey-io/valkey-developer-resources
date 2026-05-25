# LMCache + Valkey Cookbook Sample

Runnable code for the [LMCache + Valkey cookbook series](../README.md).

> **⚠️ Untested:** This sample code has not been validated on hardware. LMCache requires vLLM running on a Linux machine with an NVIDIA GPU — it hooks into vLLM's internal KV cache tensors and cannot run on CPU-only machines, macOS, or against remote LLM APIs (Bedrock, OpenAI, Ollama, etc.). The code is based on LMCache's official documentation and examples but has not been executed end-to-end.

## Prerequisites

1. **Linux with NVIDIA GPU** (CUDA required — LMCache/vLLM do not run on macOS)
2. **Docker** (for Valkey)
3. **Python 3.10+**
4. **Sufficient GPU memory** — Qwen3-8B requires ~16 GB VRAM

## Setup

```bash
# Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# 01 - Getting started (single GPU)
python getting_started.py

# 02 - KV cache sharing (requires 2 GPUs)
python kv_cache_sharing.py

# 03 - Production config generator + monitoring
python production_deployment.py --mode standalone --monitor
python production_deployment.py --mode cluster --host my-cluster.endpoint:6379
python production_deployment.py --mode serverless --host my-cache.serverless.region.cache.amazonaws.com:6379
```

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `getting_started.py` | [01 - Getting Started](../01-getting-started.md) | Offload KV cache to Valkey, measure TTFT speedup on repeated prompts |
| `kv_cache_sharing.py` | [02 - KV Cache Sharing](../02-kv-cache-sharing.md) | Share KV cache across two vLLM instances via centralized Valkey |
| `production_deployment.py` | [03 - Production Deployment](../03-production-deployment.md) | Generate configs for standalone/cluster/serverless, monitor cache stats |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LMCACHE_CHUNK_SIZE` | `256` | Tokens per KV cache chunk |
| `LMCACHE_LOCAL_CPU` | `True` | Enable CPU L1 cache |
| `LMCACHE_MAX_LOCAL_CPU_SIZE` | `5.0` | L1 capacity in GB |
| `LMCACHE_REMOTE_URL` | `valkey://localhost:6379` | Valkey L2 backend URL |
| `LMCACHE_REMOTE_SERDE` | `naive` | Serialization format (`naive` or `cachegen`) |
| `LMCACHE_CONFIG_FILE` | — | Path to YAML config (alternative to env vars) |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **CUDA not available**: LMCache requires an NVIDIA GPU with CUDA. It does not run on CPU-only or macOS.
- **OOM on GPU**: Reduce `--gpu-memory-utilization` or use a smaller model.
- **"Cannot re-initialize CUDA in forked subprocess"**: Set `VLLM_WORKER_MULTIPROC_METHOD=spawn`.
- **0% cache hits across instances**: Ensure `PYTHONHASHSEED=0` is set on all instances.
