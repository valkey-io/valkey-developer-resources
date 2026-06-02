# Production Deployment on AWS

> Deploy Dynamo + Valkey on EKS with ElastiCache Serverless, TLS, disaggregated serving, and observability.

**Advanced** · Python · ~30 min

This cookbook covers deploying the full Dynamo + LMCache + Valkey stack on AWS using EKS for GPU workloads and ElastiCache Serverless for the KV cache backend.

## Architecture on AWS

```
┌─────────────────────────────────────────────────────────┐
│                        EKS Cluster                       │
│                                                         │
│  ┌──────────┐   ┌──────────────────────────────────┐   │
│  │ Frontend │   │         Worker Node Pool          │   │
│  │  (CPU)   │   │  ┌────────┐ ┌────────┐ ┌──────┐ │   │
│  │  + KV    │   │  │Worker 0│ │Worker 1│ │ ...  │ │   │
│  │  Router  │   │  │(GPU)   │ │(GPU)   │ │      │ │   │
│  └────┬─────┘   │  └───┬────┘ └───┬────┘ └──┬───┘ │   │
│       │         └──────┼──────────┼─────────┼─────┘   │
│       │                │          │         │          │
└───────┼────────────────┼──────────┼─────────┼──────────┘
        │                │          │         │
        │                └──────────┼─────────┘
        │                           │
        │              ┌────────────▼────────────┐
        │              │  ElastiCache Serverless  │
        │              │       (Valkey)           │
        │              │  - Auto-scales           │
        │              │  - TLS in transit        │
        │              │  - Multi-AZ             │
        │              └─────────────────────────┘
```

## Step 1: Provision ElastiCache Serverless

```bash
aws elasticache create-serverless-cache \
  --serverless-cache-name dynamo-kv-cache \
  --engine valkey \
  --major-engine-version 8 \
  --cache-usage-limits "DataStorage={Maximum=30,Unit=GB},ECPUPerSecond={Maximum=100000}" \
  --security-group-ids sg-xxxx \
  --subnet-ids subnet-xxxx subnet-yyyy
```

Note the endpoint:
```bash
aws elasticache describe-serverless-caches \
  --serverless-cache-name dynamo-kv-cache \
  --query 'ServerlessCaches[0].Endpoint'
```

This gives you something like: `dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379`

## Step 2: Configure TLS for LMCache

ElastiCache Serverless requires TLS. LMCache's Valkey connector supports TLS via the URL scheme:

```bash
# lmcache.env for production
LMCACHE_CHUNK_SIZE=256
LMCACHE_LOCAL_CPU=True
LMCACHE_MAX_LOCAL_CPU_SIZE=10.0
LMCACHE_REMOTE_URL=valkeys://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379
LMCACHE_REMOTE_SERDE=naive
```

Note: `valkeys://` (with the `s`) enables TLS. This is the standard convention for Valkey TLS connections.

## Step 3: Deploy Dynamo on EKS

Create the Kubernetes manifests using Dynamo's Helm chart:

```bash
helm repo add dynamo https://ai-dynamo.github.io/dynamo/charts
helm repo update

helm install dynamo-inference dynamo/dynamo \
  --namespace inference \
  --create-namespace \
  --set frontend.replicas=2 \
  --set worker.replicas=4 \
  --set worker.gpu.count=1 \
  --set worker.gpu.type=nvidia.com/gpu \
  --set worker.model=Qwen/Qwen3-8B \
  --set worker.env.LMCACHE_REMOTE_URL="valkeys://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379" \
  --set worker.env.LMCACHE_CHUNK_SIZE=256 \
  --set worker.env.LMCACHE_LOCAL_CPU=True \
  --set worker.env.LMCACHE_MAX_LOCAL_CPU_SIZE=10.0 \
  --set worker.env.LMCACHE_REMOTE_SERDE=naive \
  --set router.strategy=prefix_aware \
  --set router.cacheAware=true
```

## Step 4: Enable Disaggregated Serving

Dynamo supports separating prefill (compute-heavy) from decode (memory-bound) into different worker pools. This maximizes GPU utilization:

```yaml
# values-disaggregated.yaml
prefillWorkers:
  replicas: 2
  gpu:
    type: nvidia.com/gpu
    count: 1  # high-compute GPUs (e.g., A100)
  env:
    LMCACHE_REMOTE_URL: "valkeys://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379"
    KV_ROLE: "kv_both"

decodeWorkers:
  replicas: 4
  gpu:
    type: nvidia.com/gpu
    count: 1  # memory-optimized GPUs
  env:
    LMCACHE_REMOTE_URL: "valkeys://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379"
    KV_ROLE: "kv_both"
```

```bash
helm upgrade dynamo-inference dynamo/dynamo \
  --namespace inference \
  -f values-disaggregated.yaml
```

With disaggregated serving:
1. Prefill workers compute KV caches and store them to Valkey
2. Decode workers load KV caches from Valkey and generate tokens
3. Valkey serves as the transfer medium between the two pools

## Step 5: Observability

### Prometheus Metrics

Dynamo exposes metrics at `/metrics` on the frontend. Scrape with:

```yaml
# ServiceMonitor for Prometheus Operator
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: dynamo-frontend
  namespace: inference
spec:
  selector:
    matchLabels:
      app: dynamo-frontend
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

### Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `dynamo_kv_router_cache_hit_ratio` | Cluster-wide cache hit rate | < 0.5 (investigate) |
| `lmcache_remote_latency_ms` | Valkey round-trip time | > 5ms (network issue) |
| `lmcache_remote_store_failures` | Failed writes to Valkey | > 0 (connectivity) |
| `dynamo_prefill_tokens_saved` | Tokens skipped via cache | Trending down = problem |
| ElastiCache `CurrConnections` | Active connections to Valkey | Near limit = scale |
| ElastiCache `BytesUsedForCache` | Memory utilization | > 80% = increase limit |

### ElastiCache CloudWatch Dashboard

```bash
aws cloudwatch get-metric-data \
  --metric-data-queries '[
    {"Id":"hits","MetricStat":{"Metric":{"Namespace":"AWS/ElastiCache","MetricName":"CacheHits","Dimensions":[{"Name":"ServerlessCacheName","Value":"dynamo-kv-cache"}]},"Period":60,"Stat":"Sum"}},
    {"Id":"misses","MetricStat":{"Metric":{"Namespace":"AWS/ElastiCache","MetricName":"CacheMisses","Dimensions":[{"Name":"ServerlessCacheName","Value":"dynamo-kv-cache"}]},"Period":60,"Stat":"Sum"}}
  ]' \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S)
```

## Step 6: Tuning for Agentic Workloads

Agentic inference (multi-turn, tool-calling) exhibits a WORM pattern — 11.7× more reads than writes. Optimize for this:

```bash
# Increase Valkey maxmemory for large conversation histories
# (ElastiCache Serverless auto-scales, but set a high ceiling)
aws elasticache modify-serverless-cache \
  --serverless-cache-name dynamo-kv-cache \
  --cache-usage-limits "DataStorage={Maximum=100,Unit=GB}"

# LMCache tuning for agentic workloads
LMCACHE_CHUNK_SIZE=512          # larger chunks for long contexts
LMCACHE_MAX_LOCAL_CPU_SIZE=20.0 # more L1 for hot conversation state
```

## Security Considerations

| Layer | Mechanism |
|-------|-----------|
| Network | VPC + Security Groups (EKS ↔ ElastiCache same VPC) |
| Transport | TLS via `valkeys://` scheme |
| Authentication | ElastiCache IAM auth or AUTH token |
| Data | KV cache blocks are binary tensors — not human-readable, but treat as sensitive |

For IAM authentication:

```bash
LMCACHE_REMOTE_URL=valkeys://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379
LMCACHE_REMOTE_AUTH_TOKEN=$(aws elasticache generate-auth-token --serverless-cache-name dynamo-kv-cache)
```

## Cost Estimation

| Component | Sizing | Approximate Cost |
|-----------|--------|-----------------|
| EKS worker nodes (4× g5.xlarge) | 4 GPUs, inference | ~$4.00/hr |
| EKS frontend (2× c5.xlarge) | Routing | ~$0.34/hr |
| ElastiCache Serverless | 30 GB, 100k ECPU/s | ~$0.50/hr (scales to 0 at idle) |

ElastiCache Serverless is ideal here — KV cache traffic is bursty (high during prefill, low during decode), and serverless scales ECPU automatically.

---

[← 02 - KV-Aware Routing](02-kv-cache-routing.md)
