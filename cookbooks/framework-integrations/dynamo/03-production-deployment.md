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
│  └────┬─────┘   │  │+sidecar│ │+sidecar│ │      │ │   │
│       │         │  └───┬────┘ └───┬────┘ └──┬───┘ │   │
│       │         └──────┼──────────┼─────────┼─────┘   │
└───────┼────────────────┼──────────┼─────────┼──────────┘
        │                └──────────┼─────────┘
        │                           │
        │              ┌────────────▼────────────┐
        │              │  ElastiCache Serverless  │
        │              │       (Valkey)           │
        │              │  - Auto-scales ECPU      │
        │              │  - TLS in transit        │
        │              │  - Multi-AZ             │
        │              └─────────────────────────┘
```

## Step 1: Provision ElastiCache Serverless

```bash
# Replace sg-xxxx and subnet-xxxx/yyyy with your VPC security group and subnet IDs
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

## Step 2: Configure Valkey for LMCache

LMCache's Valkey connector uses the GLIDE client (installed via `pip install valkey-glide` if not already present in your container).

### Local / Non-TLS (private VPC)

```bash
LMCACHE_REMOTE_URL="valkey://my-valkey.internal:6379" \
LMCACHE_REMOTE_SERDE="naive" \
LMCACHE_LOCAL_CPU=true \
LMCACHE_MAX_LOCAL_CPU_SIZE=10.0 \
LMCACHE_CHUNK_SIZE=256 \
python3 -m dynamo.vllm \
  --model Qwen/Qwen3-8B \
  --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}'
```

### ElastiCache Serverless (TLS + Cluster Mode)

For ElastiCache Serverless, enable TLS and cluster mode via `extra_config`:

```bash
LMCACHE_REMOTE_URL="valkey://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379" \
LMCACHE_REMOTE_SERDE="naive" \
LMCACHE_LOCAL_CPU=true \
LMCACHE_MAX_LOCAL_CPU_SIZE=10.0 \
LMCACHE_CHUNK_SIZE=256 \
LMCACHE_EXTRA_CONFIG='{"tls_enable": true, "valkey_mode": "cluster", "valkey_password": "'${VALKEY_PASSWORD}'"}' \
python3 -m dynamo.vllm \
  --model Qwen/Qwen3-8B \
  --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}'
```

> **Note:** The GLIDE client natively supports TLS and cluster topology discovery. `valkey_mode: "cluster"` enables automatic node discovery from the seed endpoint.

## Step 3: Deploy Dynamo on EKS with DynamoGraphDeployment

Dynamo uses `DynamoGraphDeployment` CRDs for Kubernetes. First, install the Dynamo platform operator:

```bash
helm install dynamo-platform \
  oci://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-platform \
  --namespace dynamo-system \
  --create-namespace
```

Then create a `DynamoGraphDeployment` manifest:

```yaml
# dynamo-valkey-deployment.yaml
apiVersion: nvidia.com/v1beta1
kind: DynamoGraphDeployment
metadata:
  name: dynamo-valkey-inference
  namespace: inference
spec:
  backendFramework: vllm
  env:
    - name: HF_TOKEN
      valueFrom:
        secretKeyRef:
          name: hf-token
          key: token

  components:
    - name: Frontend
      type: frontend
      replicas: 2
      podTemplate:
        spec:
          containers:
            - name: main
              args:
                - --router-mode
                - kv
              env:
                - name: DYN_HTTP_PORT
                  value: "8000"

    - name: VllmWorker
      type: worker
      replicas: 4
      sharedMemorySize: 16Gi
      podTemplate:
        spec:
          containers:
            - name: main
              image: nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.1.1
              args:
                - --model
                - Qwen/Qwen3-8B
                - --kv-transfer-config
                - '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}'
              env:
                - name: LMCACHE_REMOTE_URL
                  value: "valkey://dynamo-kv-cache-xxxxx.serverless.use1.cache.amazonaws.com:6379"
                - name: LMCACHE_REMOTE_SERDE
                  value: "naive"
                - name: LMCACHE_LOCAL_CPU
                  value: "true"
                - name: LMCACHE_MAX_LOCAL_CPU_SIZE
                  value: "10.0"
                - name: LMCACHE_CHUNK_SIZE
                  value: "256"
                - name: LMCACHE_EXTRA_CONFIG
                  value: '{"tls_enable": true, "valkey_mode": "cluster"}'
                - name: VALKEY_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: valkey-auth
                      key: password
      resources:
        limits:
          nvidia.com/gpu: "1"
```

Apply:

```bash
kubectl apply -f dynamo-valkey-deployment.yaml
```

## Step 4: Disaggregated Serving

Dynamo supports separating prefill (compute-heavy) from decode (memory-bound) into different worker pools. This maximizes GPU utilization for high-throughput deployments.

Disaggregated mode activates automatically when prefill workers register alongside decode workers. Use the provided launch script (requires at least 2 GPUs):

```bash
./examples/backends/vllm/launch/disagg_lmcache.sh
```

This starts:
1. Dynamo frontend
2. Decode worker on GPU 0 (uses `NixlConnector` for KV transfer from prefill)
3. Prefill worker on GPU 1 (uses `MultiConnector` with both LMCache and NIXL)

With disaggregated serving + Valkey:
- Prefill workers compute KV caches and store them via LMCache → Valkey
- Decode workers load KV caches from Valkey when the prefill worker's direct NIXL transfer isn't available
- Valkey serves as both a persistence layer and a fallback transfer medium

## Step 5: Observability

### Prometheus Metrics

Dynamo exposes metrics on the frontend HTTP port and the worker system port:

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

LMCache sidecars expose metrics on port 8080:

```bash
curl -s http://<worker-pod>:8080/metrics | grep '^lmcache_mp_'
```

Set `DYN_SYSTEM_PORT=8081` on workers to enable Dynamo's own metrics endpoint.

### Key Metrics to Monitor

| Metric Source | What to Watch | Alert Threshold |
|---------------|---------------|-----------------|
| Dynamo frontend `/metrics` | Router decision latency | > 10ms |
| LMCache sidecar `:8080/metrics` | L2 store/load latency | > 10ms (network issue) |
| LMCache sidecar `:8080/metrics` | L2 store failures | > 0 (connectivity) |
| ElastiCache `CurrConnections` | Active connections | Near limit = scale workers |
| ElastiCache `BytesUsedForCache` | Memory utilization | > 80% = increase data limit |

### ElastiCache CloudWatch Monitoring

```bash
# Requires GNU date (Linux). macOS: replace $(date -u -d '1 hour ago' ...) with $(date -u -v-1H ...)
aws cloudwatch get-metric-data \
  --metric-data-queries '[
    {"Id":"hits","MetricStat":{"Metric":{"Namespace":"AWS/ElastiCache","MetricName":"CacheHits","Dimensions":[{"Name":"ServerlessCacheName","Value":"dynamo-kv-cache"}]},"Period":60,"Stat":"Sum"}},
    {"Id":"misses","MetricStat":{"Metric":{"Namespace":"AWS/ElastiCache","MetricName":"CacheMisses","Dimensions":[{"Name":"ServerlessCacheName","Value":"dynamo-kv-cache"}]},"Period":60,"Stat":"Sum"}}
  ]' \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S)
```

## Step 6: Tuning for Agentic Workloads

Agentic inference (multi-turn, tool-calling) exhibits a WORM pattern — [11.7× more reads than writes](https://developer.nvidia.com/blog/full-stack-optimizations-for-agentic-inference-with-nvidia-dynamo/). Optimize for this:

```bash
# Increase ElastiCache data limit for large conversation histories
aws elasticache modify-serverless-cache \
  --serverless-cache-name dynamo-kv-cache \
  --cache-usage-limits "DataStorage={Maximum=100,Unit=GB}"
```

LMCache tuning for agentic workloads:

| Setting | Default | Agentic Recommendation | Why |
|---------|---------|------------------------|-----|
| `--chunk-size` | 256 | 512 | Larger chunks for long contexts |
| `--l1-size-gb` | 5 | 20 | More L1 for hot conversation state |
| `--eviction-policy` | LRU | LRU | Keeps frequently-accessed prefixes warm |

## Security Considerations

| Layer | Mechanism |
|-------|-----------|
| Network | VPC + Security Groups (EKS ↔ ElastiCache in same VPC) |
| Transport | TLS via `tls_enable: true` in `LMCACHE_EXTRA_CONFIG` |
| Authentication | `valkey_password` in `LMCACHE_EXTRA_CONFIG` (inject from K8s Secret) |
| Data | KV cache blocks are binary tensors — not human-readable, but treat as sensitive |

> **Security note:** Avoid passing passwords as CLI arguments (visible via `ps`). Use environment variables injected from Kubernetes Secrets as shown in the manifest above.

For IAM-based authentication, see the [ElastiCache IAM auth documentation](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/auth-iam.html).

## Cost Estimation

> As of June 2026, us-east-1. See [ElastiCache pricing](https://aws.amazon.com/elasticache/pricing/) and [EC2 pricing](https://aws.amazon.com/ec2/pricing/) for current rates.

| Component | Sizing | Approximate Cost |
|-----------|--------|-----------------|
| EKS worker nodes (4× g5.xlarge) | 4 GPUs, inference | ~$4.00/hr |
| EKS frontend (2× c5.xlarge) | Routing | ~$0.34/hr |
| ElastiCache Serverless | 30 GB, 100k ECPU/s | ~$0.50/hr (minimum baseline applies) |

ElastiCache Serverless is well-suited here — KV cache traffic is bursty (high during prefill, lower during decode), and serverless auto-scales ECPU to match demand.

---

[← 02 - KV-Aware Routing](02-kv-cache-routing.md)
