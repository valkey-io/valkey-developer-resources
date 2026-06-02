# Valkey with NVIDIA Dynamo

> Use Valkey as the distributed KV cache backend for NVIDIA Dynamo's inference serving framework. From single-node setup to production multi-worker deployments with KV-aware routing.

> **⚠️ Note:** These cookbooks have not been validated on hardware. NVIDIA Dynamo requires Linux with NVIDIA GPUs (Ampere or later) and the Dynamo container image. Content is based on Dynamo's official documentation, LMCache integration guides, and the ai-dynamo/dynamo repository.

## What is Dynamo?

[NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo) is a high-throughput, low-latency distributed inference framework for serving generative AI and reasoning models at datacenter scale. It provides KV-aware request routing, multi-tier caching, and disaggregated prefill/decode serving across GPU clusters.

Valkey integrates with Dynamo through [LMCache](https://github.com/LMCache/LMCache), which serves as the KV cache management layer. LMCache's native Valkey connector stores KV cache blocks remotely, enabling cache sharing across all inference workers in the cluster.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Deploy Dynamo with Valkey as the distributed KV cache backend via LMCache. | Intermediate, ~25 min, Python |
| 02 | <nobr>[KV-Aware Routing](02-kv-cache-routing.md)</nobr> | Leverage Dynamo's KV router to direct requests toward workers with warm caches. | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production Deployment](03-production-deployment.md)</nobr> | Deploy on EKS with ElastiCache Serverless, TLS, disaggregated serving, and monitoring. | Advanced, ~30 min, Python |
