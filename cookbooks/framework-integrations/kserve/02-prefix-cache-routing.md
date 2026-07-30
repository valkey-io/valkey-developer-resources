# Prefix-Cache Routing with Valkey Shared Index

> Back the Endpoint Picker's KV-block index with a shared Valkey instance so multiple
> EPP replicas see the same cluster-wide cache state and route requests accurately.

**Intermediate** · Kubernetes · ~10 min

**Who is this for:** Platform teams running KServe's LLMInferenceService at scale
with multiple Endpoint Picker (EPP) replicas, who need consistent prefix-cache-aware
routing decisions across all replicas.

## Prerequisites

- Kubernetes cluster with KServe v0.18.0+ installed
- GPU nodes (for the inference pods)
- Familiarity with [01 - LMCache KV Offloading](01-lmcache-kv-offloading.md) concepts

> **Security:** This cookbook deploys Valkey without authentication for simplicity.
> For any production or multi-tenant deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and network policies.

## Background

KServe's Endpoint Picker uses a `precise-prefix-cache-scorer` plugin to route requests
to pods that already have relevant KV cache blocks. Each EPP replica maintains a
KV-block index that maps `(hash of token block) → (pod holding that block)`.

**The problem:** With the default in-memory index, each EPP replica only sees KV cache
events it received. If you have multiple EPP replicas for HA or load distribution,
each one fragments its own view → routing decisions degrade.

**The solution:** Point all EPP replicas at the same Valkey instance. The
[`llm-d-kv-cache`](https://github.com/llm-d/llm-d-kv-cache) library supports a
`ValkeyConfig` backend that stores the block index in Valkey instead of in-memory.

## When to Use This

| Deployment | Recommended Index |
| --- | --- |
| Single EPP replica | In-memory (default) — nothing to share |
| Multiple EPP replicas (HA) | Valkey — consistent routing across replicas |
| Large fleet (many pods) | Valkey — centralized view of all pods' cache state |

## Step 1: Deploy the Manifest

The manifest includes:

- `LLMInferenceService` with `precise-prefix-cache-scorer` configured for Valkey
- Valkey `Deployment` + `Service` for the shared index

```yaml
# Key configuration change (inside the scorer parameters):
indexerConfig:
  kvBlockIndexConfig:
    valkeyConfig:
      address: "valkey://valkey:6379"
      backendType: "valkey"
    enableMetrics: true
    metricsLoggingInterval: 60000000000  # Log every 60s (nanoseconds)
```

Full manifest:

> **Note:** The `ChildName` template expression in the YAML below (inside the
> `--kv-events-config` JSON) is a KServe controller template function. It resolves
> to the EPP Service name at admission time and only works inside
> `LLMInferenceService.spec.template`. Do not copy this expression into a plain
> `Deployment` spec — it will not be resolved.

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: LLMInferenceService
metadata:
  name: qwen2-7b-kv-cache-routing-valkey
spec:
  model:
    uri: hf://Qwen/Qwen2.5-7B-Instruct
    name: Qwen/Qwen2.5-7B-Instruct
  replicas: 2
  router:
    scheduler:
      config:
        inline:
          apiVersion: inference.networking.x-k8s.io/v1alpha1
          kind: EndpointPickerConfig
          plugins:
            - type: single-profile-handler
            - type: precise-prefix-cache-scorer
              parameters:
                tokenProcessorConfig:
                  blockSize: 64
                  hashSeed: "42"
                kvEventsConfig:
                  zmqEndpoint: "tcp://*:5557"
                indexerConfig:
                  kvBlockIndexConfig:
                    valkeyConfig:
                      address: "valkey://valkey:6379"
                      backendType: "valkey"
                    enableMetrics: true
                    metricsLoggingInterval: 60000000000
            - type: kv-cache-utilization-scorer
            - type: queue-scorer
            - type: active-request-scorer
              parameters:
                requestTimeout: "2m"
                idleThreshold: 0
                maxBusyScore: 0
            - type: max-score-picker
          schedulingProfiles:
            - name: default
              plugins:
                - pluginRef: precise-prefix-cache-scorer
                  weight: 3
                - pluginRef: kv-cache-utilization-scorer
                  weight: 2
                - pluginRef: queue-scorer
                  weight: 2
                - pluginRef: active-request-scorer
                  weight: 3
                - pluginRef: max-score-picker
    route: {}
    gateway: {}
  template:
    containers:
      - name: main
        env:
          - name: VLLM_ADDITIONAL_ARGS
            value: >-
              --prefix-caching-hash-algo sha256_cbor
              --block-size 64
              --kv_transfer_config '{"kv_connector":"NixlConnector","kv_role":"kv_both"}'
              --kv-events-config '{"enable_kv_cache_events":true,"publisher":"zmq","endpoint":"tcp://{{ ChildName .ObjectMeta.Name `-epp-service` }}:5557","topic":"kv@${POD_IP}@Qwen/Qwen2.5-7B-Instruct"}'
          - name: POD_IP
            valueFrom:
              fieldRef:
                apiVersion: v1
                fieldPath: status.podIP
          - name: PYTHONHASHSEED
            value: "42"
        resources:
          limits:
            cpu: "4"
            memory: 32Gi
            nvidia.com/gpu: "1"
          requests:
            cpu: "2"
            memory: 16Gi
            nvidia.com/gpu: "1"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: valkey
  labels:
    app: valkey
spec:
  replicas: 1
  selector:
    matchLabels:
      app: valkey
  template:
    metadata:
      labels:
        app: valkey
    spec:
      containers:
        - name: valkey
          image: valkey/valkey:9.1.0
          ports:
            - containerPort: 6379
          resources:
            limits:
              memory: 1Gi
            requests:
              memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
  name: valkey
spec:
  selector:
    app: valkey
  ports:
    - protocol: TCP
      port: 6379
      targetPort: 6379
```

Apply:

```bash
kubectl apply -f llm-inference-service-qwen2-7b-gpu-kv-cache-routing-valkey.yaml
```

## Step 2: Verify the Index in Valkey

Once inference pods are running and serving requests:

```bash
# Check that the EPP is writing block entries to Valkey
kubectl exec deploy/valkey -- valkey-cli DBSIZE

# List some keys (block hashes mapped to pod IPs)
kubectl exec deploy/valkey -- valkey-cli KEYS '*' | head -20
```

The index stores mappings from `(block_hash) → (pod_ip)` so the EPP knows which
pod to route a request to based on its token prefix.

## How It Works

```text
┌──────────────┐   KV events (ZMQ)   ┌──────────────┐
│  vLLM Pod 1  │─────────────────────▶│  EPP         │
└──────────────┘                      │  Replica 1   │──┐
                                      └──────────────┘  │
                                                        │  Read/Write
┌──────────────┐   KV events (ZMQ)   ┌──────────────┐  │  block index
│  vLLM Pod 2  │─────────────────────▶│  EPP         │──┼──────────────▶ ┌────────┐
└──────────────┘                      │  Replica 2   │  │               │ Valkey │
                                      └──────────────┘  │               │ :6379  │
                                                        │               └────────┘
                                      ┌──────────────┐  │
                                      │  EPP         │──┘
                                      │  Replica N   │
                                      └──────────────┘
```

1. vLLM pods publish KV cache events via ZMQ when blocks are allocated/evicted
2. EPP replicas receive events and update the shared Valkey index
3. On each incoming request, EPP hashes the prompt's token blocks
4. EPP looks up which pod holds matching blocks (via Valkey)
5. Request is routed to the pod with the highest cache hit ratio

## Configuration Parameters

| Parameter | Description |
| --- | --- |
| `valkeyConfig.address` | Valkey connection URL (`valkey://host:port`) |
| `valkeyConfig.backendType` | Must be `"valkey"` |
| `enableMetrics` | Expose Prometheus metrics for index operations |
| `metricsLoggingInterval` | How often to log metrics (nanoseconds) |
| `blockSize` | Must match vLLM's `--block-size` |
| `hashSeed` | Must match `PYTHONHASHSEED` in vLLM pods |

## Memory Requirements

The index is lightweight — each entry is a hash-to-pod mapping. Even with millions
of cache blocks across dozens of pods, the Valkey instance needs only hundreds of MB.
The 512Mi/1Gi resource specification in the manifest is generous for most deployments.

## Troubleshooting

### EPP logs show "failed to connect to Valkey"

- Verify Valkey pod is running: `kubectl get pods -l app=valkey`
- Check the address in `valkeyConfig` matches the Service name and port
- Ensure EPP and Valkey are in the same namespace (or use FQDN)

### Routing doesn't improve with shared index

- Confirm multiple EPP replicas are running (check the EPP deployment)
- Send repeated prompts with shared prefixes to trigger cache hits
- Check `kubectl exec deploy/valkey -- valkey-cli DBSIZE` grows with usage

### PYTHONHASHSEED mismatch

The `hashSeed` in the scorer config and `PYTHONHASHSEED` in vLLM pods must match.
If they don't, block hashes won't align and the index becomes useless.

---

[→ Next: Feast Feature Store](03-feast-feature-store.md) · [← Back to LMCache KV Offloading](01-lmcache-kv-offloading.md)
