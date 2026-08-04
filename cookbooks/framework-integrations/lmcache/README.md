# LMCache + Valkey

> Offload LLM KV caches to Valkey with LMCache, verified against LMCache's real config-loading and key-generation code — no GPU required to follow along.

**Who is this for:** Python developers evaluating [LMCache](https://github.com/LMCache/LMCache) as
a KV cache layer for vLLM who want to understand exactly what it writes to Valkey before deploying
it on GPU hardware.

## Prerequisites

- Docker or Podman
- Python 3.10 or newer
- No API keys, GPU, or paid services needed for the default path in this repo

## Scope

LMCache's Valkey connector is normally driven by vLLM during live inference,
which requires a Linux machine with an NVIDIA GPU. This cookbook series does
not run that pipeline — instead it exercises the real LMCache config-loading
and Valkey key-generation code (`lmcache==0.5.2`) against a real local
Valkey server, so every command here runs on CPU and in CI. For the full
GPU-based inference walkthrough with actual TTFT measurements, see
[LMCache's own example](https://github.com/LMCache/LMCache/tree/v0.5.2/examples/kv_cache_reuse/remote_backends/valkey).

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Load a real LMCache config, connect to Valkey, and store/inspect a simulated KV cache chunk under LMCache's real key format. | Beginner, ~15 min, Python |
| 02 | <nobr>[KV Cache Sharing](02-kv-cache-sharing.md)</nobr> | Two simulated instances sharing a KV cache chunk through a centralized Valkey store. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Production Deployment](03-production-deployment.md)</nobr> | Cluster mode, TLS/ElastiCache Serverless, the current recommended MP-mode adapter, worker tuning, and cache-hit monitoring. | Advanced, ~20 min, Python |
