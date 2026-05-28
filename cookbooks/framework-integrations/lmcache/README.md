# Valkey with LMCache

> Accelerate LLM inference by offloading KV caches to Valkey. From first connection to a multi-instance production deployment with 3-10× TTFT reduction.

> **⚠️ Note:** These cookbooks and [sample code](sample/) have not been validated on hardware. LMCache requires vLLM running on a Linux NVIDIA GPU — it intercepts internal KV tensors during inference and cannot run on CPU-only machines, macOS, or against remote LLM APIs. Content is based on LMCache's official documentation and source code.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install LMCache + vLLM, connect to Valkey as a remote KV cache backend, and demonstrate TTFT improvement on repeated prompts. | Beginner, ~15 min, Python |
| 02 | <nobr>[KV Cache Sharing](02-kv-cache-sharing.md)</nobr> | Share KV caches across multiple vLLM instances through a centralized Valkey store, enabling fleet-wide cache reuse. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Deployment](03-production-deployment.md)</nobr> | Deploy with cluster mode, TLS, ElastiCache Serverless, worker tuning, and cache-hit monitoring. | Advanced, ~20 min, Python |
