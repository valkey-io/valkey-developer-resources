# KServe + Valkey Cookbook

> Use Valkey as the high-performance backend for KServe's LLM inference stack —
> offload KV cache via LMCache, share prefix-cache state across EPP replicas,
> and serve features from Feast's online store.

## Cookbooks

| # | Title | Description | Level |
| --- | --- | --- | --- |
| 01 | <nobr>[LMCache KV Offloading](01-lmcache-kv-offloading.md)</nobr> | Offload vLLM's KV cache to Valkey via LMCache for multi-replica cache sharing. | Intermediate, ~15 min, Kubernetes |
| 02 | <nobr>[Prefix-Cache Routing](02-prefix-cache-routing.md)</nobr> | Back the EPP's KV-block index with a shared Valkey instance for consistent routing. | Intermediate, ~10 min, Kubernetes |
| 03 | <nobr>[Feast Feature Store](03-feast-feature-store.md)</nobr> | Use Valkey as Feast's online store for low-latency feature serving in KServe transformers. | Beginner, ~10 min, Kubernetes |

## Prerequisites

- Kubernetes cluster with [KServe v0.18.0](https://kserve.github.io/website/docs/getting-started/quickstart-guide) or later
- `kubectl` configured for your cluster
- Valkey 9.1.0+ (plain `valkey/valkey` — no search module needed)
- For LMCache samples: GPU nodes with `nvidia.com/gpu` resource

## How KServe Uses Valkey

KServe's LLM inference stack (`LLMInferenceService`) integrates with Valkey in three places:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                        KServe LLMInferenceService                         │
├─────────────────────┬────────────────────────┬───────────────────────────┤
│  LMCache + vLLM     │  Endpoint Picker (EPP) │  Feast Transformer        │
│  ─────────────────  │  ────────────────────  │  ───────────────────────  │
│  KV cache chunks    │  KV-block index        │  Feature vectors          │
│  SET/GET via GLIDE  │  (llm-d-kv-cache)      │  (feast-redis client)     │
│  valkey://host:6379 │  ValkeyConfig          │  connection_string        │
└────────┬────────────┴───────────┬────────────┴──────────────┬────────────┘
         │                        │                           │
         ▼                        ▼                           ▼
    ┌──────────┐           ┌──────────┐                ┌──────────┐
    │  Valkey  │           │  Valkey  │                │  Valkey  │
    │  (data)  │           │  (index) │                │ (features)│
    └──────────┘           └──────────┘                └──────────┘
```

1. **LMCache KV offloading** — vLLM uses LMCache's `ValkeyConnector` (via `valkey-glide-sync`)
   to store/retrieve KV cache chunks to a remote Valkey instance. Enables cache sharing across
   inference replicas without GPU memory duplication.

2. **Shared prefix-cache index** — The Endpoint Picker's `precise-prefix-cache-scorer` plugin
   uses `llm-d-kv-cache`'s Valkey backend to maintain a cluster-wide view of which pods hold
   which KV-cache blocks. Needed for accurate routing in multi-replica EPP deployments.

3. **Feast online store** — KServe's Feast transformer reads feature vectors from Valkey at
   inference time (using Feast's `redis` online store type, which works against Valkey
   unmodified via wire-protocol compatibility).

## Quick Start

```bash
# Deploy LMCache + Valkey KV offloading (requires GPU)
kubectl apply -f https://raw.githubusercontent.com/kserve/kserve/master/docs/samples/llmisvc/lmcache-valkey-offloading/llmisvc-lmcache-valkey.yaml
```

## Upstream Status

> **Note:** Both upstream PRs are currently **open**:
>
> - [kserve/kserve#5841](https://github.com/kserve/kserve/pull/5841) — Sample manifests for
>   LMCache KV offloading, shared prefix-cache index, and Feast online store.
> - [kserve/website#703](https://github.com/kserve/website/pull/703) — Documentation for
>   the Valkey backend option in the KV offloading and Feast guides.
>
> The samples have been validated end-to-end on GPU (g5.2xlarge, A10G) with KServe v0.18.0
> and vLLM v0.25.1 + LMCache 0.5.1.

## References

- [KServe LLMInferenceService Documentation](https://kserve.github.io/website/docs/model-serving/generative-inference/)
- [LMCache Documentation](https://docs.lmcache.ai/)
- [LMCache Valkey Storage Backend](https://docs.lmcache.ai/kv_cache/storage_backends/valkey.html)
- [llm-d-kv-cache (prefix-cache index)](https://github.com/llm-d/llm-d-kv-cache)
- [Feast Online Store — Redis/Valkey](https://docs.feast.dev/reference/online-stores/redis)
- [Valkey Documentation](https://valkey.io/docs/)

---

[← Back to Valkey Samples](../../../README.md)
