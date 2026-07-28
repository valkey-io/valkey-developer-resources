# LMCache KV Offloading with Valkey

> Offload vLLM's KV cache to a remote Valkey instance via LMCache — share cache
> across inference replicas, survive pod restarts, and reduce GPU memory pressure.

**Intermediate** · Kubernetes · ~15 min

**Who is this for:** ML engineers running multi-replica LLM inference on KServe who
want to share KV cache across pods without duplicating GPU memory, using Valkey as
the distributed cache backend.

## Prerequisites

- Kubernetes cluster with KServe v0.18.0+ installed
- GPU nodes (`nvidia.com/gpu` available)
- `kubectl` configured for your cluster
- Huggingface token (for gated models like Llama)

> **Security:** This cookbook deploys Valkey without authentication for simplicity.
> For any production or multi-tenant deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication (`requirepass`) and network policies.

## Background

When vLLM serves an LLM, it builds a KV cache in GPU memory for each request's token
sequence. Without offloading, this cache dies with the pod. LMCache intercepts vLLM's
KV cache lifecycle and stores chunks to a remote backend, so:

- A second request with the same prefix hits cache instead of re-computing attention
- Multiple replicas share the same cache (prompt reuse across pods)
- Cache survives pod restarts/reschedules

Valkey is the recommended backend because LMCache's `ValkeyConnector` uses
`valkey-glide-sync` (the official synchronous GLIDE client) for reliable, low-latency
access.

## Step 1: Create the Huggingface Secret

```bash
kubectl create secret generic hf-secret --from-literal=HF_TOKEN=<your-token>
```

## Step 2: Deploy the LMCache + Valkey Sample

The manifest includes three resources:

1. `ConfigMap` — LMCache configuration pointing at Valkey
2. Valkey `Deployment` + `Service` — single-replica `valkey/valkey:9.1.0`
3. `LLMInferenceService` — vLLM with LMCache enabled

```yaml
# llmisvc-lmcache-valkey.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lmcache-config
data:
  lmcache_config.yaml: |
    local_cpu: true         # Enable local CPU RAM cache (fast L1)
    chunk_size: 256         # Tokens per cache chunk
    max_local_cpu_size: 2.0 # GB for local CPU cache
    remote_url: "valkey://valkey:6379"   # Valkey as remote backend
    remote_serde: "naive"   # Serialization: "naive" or "cachegen"
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
              memory: 4Gi
            requests:
              memory: 2Gi
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
---
apiVersion: serving.kserve.io/v1alpha1
kind: LLMInferenceService
metadata:
  name: llama3-lmcache-valkey
spec:
  model:
    uri: hf://meta-llama/Llama-3.2-1B-Instruct
    name: meta-llama/Llama-3.2-1B-Instruct
  replicas: 2
  router:
    scheduler: {}
    route: {}
    gateway: {}
  template:
    containers:
      - name: main
        env:
          - name: HF_TOKEN
            valueFrom:
              secretKeyRef:
                name: hf-secret
                key: HF_TOKEN
                optional: false
          - name: VLLM_ADDITIONAL_ARGS
            value: "--max-model-len=10000 --kv-transfer-config '{\"kv_connector\":\"LMCacheConnectorV1\", \"kv_role\":\"kv_both\"}' --enable-chunked-prefill"
          - name: LMCACHE_USE_EXPERIMENTAL
            value: "True"
          - name: LMCACHE_CONFIG_FILE
            value: /lmcache/lmcache_config.yaml
          - name: LMCACHE_LOG_LEVEL
            value: "INFO"
        resources:
          limits:
            cpu: 6
            memory: 24Gi
            nvidia.com/gpu: "1"
          requests:
            cpu: 6
            memory: 24Gi
            nvidia.com/gpu: "1"
        volumeMounts:
          - name: lmcache-config-volume
            mountPath: /lmcache
            readOnly: true
    volumes:
      - name: lmcache-config-volume
        configMap:
          name: lmcache-config
          items:
            - key: lmcache_config.yaml
              path: lmcache_config.yaml
```

Apply:

```bash
kubectl apply -f llmisvc-lmcache-valkey.yaml
```

## Step 3: Wait for Ready State

```bash
# Watch Valkey come up
kubectl get pods -l app=valkey -w

# Watch the inference service
kubectl get llminferenceservice llama3-lmcache-valkey -w
```

The inference pods download the model from Huggingface on first start (several
minutes depending on network speed).

## Step 4: Verify KV Cache Offloading

Send an inference request:

```bash
SERVICE_URL=$(kubectl get llminferenceservice llama3-lmcache-valkey -o jsonpath='{.status.url}')
curl -X POST "${SERVICE_URL}/v1/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.2-1B-Instruct",
    "prompt": "Explain how KV cache offloading works in large language model serving. The key idea is",
    "max_tokens": 50
  }'
```

Check that cache chunks landed in Valkey:

```bash
kubectl exec deploy/valkey -it -- valkey-cli KEYS '*'
```

You should see keys like `meta-llama/Llama-3.2-1B-Instruct@0@1@<hash>@half` — one per
256-token chunk that LMCache offloaded.

Send the same prompt again and check the logs for cache hits:

```bash
kubectl logs -f $(kubectl get pods -l app=llama3-lmcache-valkey -o name | head -1) \
  -c kserve-container 2>&1 | grep "LMCache hit"
```

Expected output: `LMCache hit tokens: 256` (or a multiple of your `chunk_size`).

## How It Works

```text
┌──────────────────────────────────┐
│  vLLM + LMCacheConnectorV1       │
│                                  │
│  ┌──────────┐   ┌─────────────┐ │
│  │ GPU KV   │──▶│  LMCache    │ │     ┌──────────┐
│  │ cache    │   │  (Python)   │─┼────▶│  Valkey  │
│  └──────────┘   └─────────────┘ │     │  :6379   │
│                        │         │     └──────────┘
│                  local CPU RAM   │
│                  (L1 cache)      │
└──────────────────────────────────┘
```

1. vLLM computes attention → KV cache chunks fill GPU memory
2. LMCache intercepts chunks at `chunk_size` boundaries (256 tokens)
3. Chunks go to local CPU RAM first (fast L1), then to Valkey (persistent L2)
4. On cache hit: LMCache skips GPU computation, reads from Valkey → CPU → GPU
5. Multiple pods share the same Valkey instance → cross-replica cache reuse

## LMCache Configuration Reference

| Field | Default | Description |
| --- | --- | --- |
| `local_cpu` | `true` | Enable local CPU RAM as L1 cache |
| `chunk_size` | `256` | Tokens per cache chunk (tune for your model/workload) |
| `max_local_cpu_size` | `2.0` | GB allocated for local CPU cache |
| `remote_url` | (required) | Valkey URL: `valkey://host:port` |
| `remote_serde` | `naive` | Serialization: `naive` (fast) or `cachegen` (compressed) |

## VLLM_ADDITIONAL_ARGS Explained

```text
--max-model-len=10000           # Context window limit
--kv-transfer-config '{...}'    # Connects vLLM to LMCache's connector
--enable-chunked-prefill        # Required for LMCache to intercept chunk boundaries
```

**Why `VLLM_ADDITIONAL_ARGS` instead of container `args:`?** KServe's default LLM
template's entrypoint uses `eval "exec vllm serve ... $@"` which re-splits positional
arguments on whitespace, corrupting the embedded JSON. `VLLM_ADDITIONAL_ARGS` is
expanded inside the template's own quoting context, preserving the JSON intact.

## Tuning for Production

### Memory sizing

Each KV cache chunk is approximately:
`num_layers × 2 × num_heads × head_dim × chunk_size × dtype_size`

For Llama-3.2-1B (16 layers, 8 heads, 64 dim, FP16):
`16 × 2 × 8 × 64 × 256 × 2 bytes ≈ 8.4 MB per chunk`

Plan Valkey memory accordingly — e.g., 4 GB supports ~475 chunks.

### Persistence

Add `--appendonly yes` to Valkey's args for crash recovery:

```yaml
containers:
  - name: valkey
    image: valkey/valkey:9.1.0
    args: ["--appendonly", "yes"]
```

### Multiple replicas

Valkey handles concurrent writes from multiple inference replicas safely. The key
schema includes the model name, worker ID, layer, and content hash, so different
replicas writing the same chunk produce the same key (idempotent).

## Troubleshooting

### LMCache logs show "Connection refused"

- Verify Valkey pod is running: `kubectl get pods -l app=valkey`
- Confirm service DNS: `kubectl exec <pod> -- nslookup valkey`
- Check the `remote_url` in the ConfigMap matches the Service name

### No cache hits on repeated prompts

- Ensure `chunk_size` ≤ prompt length (cache only stores complete chunks)
- Check `--enable-chunked-prefill` is in `VLLM_ADDITIONAL_ARGS`
- Verify chunks exist: `kubectl exec deploy/valkey -- valkey-cli DBSIZE`

### OOMKilled on Valkey pod

Increase memory limits. Chunks are large — each is megabytes for big models.
Also check `max_local_cpu_size` to ensure LMCache isn't bypassing the CPU tier.

---

[→ Next: Prefix-Cache Routing](02-prefix-cache-routing.md) · [← Back to README](README.md)
