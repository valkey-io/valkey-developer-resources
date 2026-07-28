# Feast Feature Store with Valkey

> Use Valkey as Feast's online store for low-latency feature serving in KServe's
> predictive inference transformers — a drop-in replacement for Redis.

**Beginner** · Kubernetes · ~10 min

**Who is this for:** ML engineers using KServe's Feast transformer for real-time
feature enrichment who want to switch from Redis to Valkey for their online feature
store without changing application code.

## Prerequisites

- Kubernetes cluster with KServe installed
- Familiarity with [Feast](https://docs.feast.dev/) concepts (feature store, online store)
- An existing Feast feature repository (or willingness to create a simple one)

> **Security:** This cookbook deploys Valkey without authentication for simplicity.
> For any production or multi-tenant deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and network policies.

## Background

KServe's predictive inference pipeline supports a Feast transformer that enriches
inference requests with feature vectors at serving time. The transformer reads
features from Feast's online store — traditionally Redis.

Valkey is wire-protocol compatible with Redis, so Feast's `redis` online store type
works against Valkey unmodified. The only change is the connection string hostname.

## Step 1: Deploy Valkey

```yaml
# valkey.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: valkey-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: valkey-server
  template:
    metadata:
      labels:
        app: valkey-server
        name: valkey-server
    spec:
      containers:
        - name: valkey-server
          image: valkey/valkey:9.1.0
          args: ["--appendonly", "yes"]
          ports:
            - name: valkey-server
              containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: valkey-service
spec:
  type: ClusterIP
  selector:
    app: valkey-server
  ports:
    - protocol: TCP
      port: 6379
      targetPort: 6379
```

Apply:

```bash
kubectl apply -f valkey.yaml
```

Verify:

```bash
kubectl get pods -l app=valkey-server
kubectl exec deploy/valkey-server -- valkey-cli ping
# → PONG
```

## Step 2: Configure Feast to Use Valkey

In your Feast feature repository's `feature_store.yaml`:

```yaml
project: my_project
registry: data/registry.db
provider: local
online_store:
  type: redis
  connection_string: "valkey-service.default.svc.cluster.local:6379"
```

**Key point:** The `type` remains `redis` — Feast's Redis client speaks the same
wire protocol that Valkey implements. Only the `connection_string` hostname changes.

## Step 3: Update the Feature Store Initializer

If you're using KServe's sample
[`feature_store_initializer_entrypoint.sh`](https://github.com/kserve/kserve/blob/master/docs/samples/v1beta1/transformer/feast/feature_store_initializer_entrypoint.sh),
update the connection string:

```python
# Before (Redis):
connection_string = "redis-service.default.svc.cluster.local:6379"

# After (Valkey):
connection_string = "valkey-service.default.svc.cluster.local:6379"
```

Rebuild the feature store initializer image with this change.

## Step 4: Materialize Features to Valkey

Run Feast materialization to populate the online store:

```bash
feast materialize <start-date> <end-date>
```

Verify features landed in Valkey:

```bash
kubectl exec deploy/valkey-server -- valkey-cli DBSIZE
# Should show non-zero count

kubectl exec deploy/valkey-server -- valkey-cli KEYS '*' | head -5
# Feature keys from Feast
```

## Step 5: Deploy the KServe InferenceService with Feast Transformer

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: my-model-with-feast
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://my-bucket/my-model"
  transformer:
    containers:
      - name: feast-transformer
        image: my-registry/feast-transformer:latest
        env:
          - name: FEAST_FEATURE_STORE_YAML
            value: /feast/feature_store.yaml
        volumeMounts:
          - name: feast-config
            mountPath: /feast
    volumes:
      - name: feast-config
        configMap:
          name: feast-config
```

The transformer reads features from Valkey at inference time, enriches the request,
and forwards it to the predictor.

## How It Works

```text
┌──────────┐     ┌─────────────────┐     ┌───────────────┐     ┌───────────┐
│  Client  │────▶│ Feast Transformer│────▶│   Predictor   │────▶│  Response │
└──────────┘     └────────┬────────┘     └───────────────┘     └───────────┘
                          │
                    feature lookup
                          │
                   ┌──────▼──────┐
                   │   Valkey    │
                   │  (online    │
                   │   store)    │
                   └─────────────┘
```

1. Client sends inference request with entity keys (e.g., `user_id`)
2. Feast transformer looks up pre-computed features from Valkey
3. Features are appended to the request payload
4. Enriched request goes to the model predictor
5. Model returns prediction using real-time features

## Why Valkey Over Redis for Feast

| Consideration | Valkey |
| --- | --- |
| License | BSD (permissive, no usage restrictions) |
| Wire compatibility | Fully compatible with Redis protocol |
| Performance | Same or better (same codebase lineage) |
| Feast support | Works unmodified (`type: redis`) |
| Community | Active development, growing ecosystem |

## Troubleshooting

### Feast materializes but transformer can't read features

- Verify DNS resolution: the transformer pod must be able to resolve
  `valkey-service.default.svc.cluster.local`
- If they're in different namespaces, use the full FQDN in `connection_string`
- Check Valkey has data: `kubectl exec deploy/valkey-server -- valkey-cli DBSIZE`

### "Connection refused" from Feast client

- Confirm Valkey pod is healthy: `kubectl get pods -l app=valkey-server`
- Ensure the Service port (6379) matches what Feast is connecting to
- Check network policies aren't blocking intra-cluster traffic

### Features are stale

Feast materializes a point-in-time snapshot. Re-run `feast materialize` to refresh,
or set up a scheduled materialization job (e.g., via CronJob).

---

[← Back to Prefix-Cache Routing](02-prefix-cache-routing.md) · [← Back to README](README.md)
