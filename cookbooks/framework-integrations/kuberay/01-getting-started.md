# Getting Started

> Deploy a RayCluster on Kubernetes with Valkey-backed GCS fault tolerance — the cluster metadata survives head node restarts.

**Beginner** · Kubernetes · ~15 min

**Who is this for:** Platform engineers who want to set up Ray GCS fault tolerance using Valkey instead of Redis, with a single `kubectl apply`.

## How GCS Fault Tolerance Works

Ray's Global Control Service (GCS) runs on the head node and stores cluster metadata: actor registrations,
placement groups, resource availability. Without fault tolerance, a head crash loses all this state.

With GCS FT enabled, Ray persists GCS state to an external Redis-protocol store. On head restart, GCS reloads from the store and the cluster recovers.

```text
┌─────────────┐         ┌──────────┐
│  Ray Head   │◄───────►│  Valkey  │  (GCS state persisted here)
│  (GCS)      │  RESP   │  :6379   │
└─────────────┘         └──────────┘
       ▲
       │ gRPC
┌──────┴──────┐
│ Ray Workers │
└─────────────┘
```

## Prerequisites

- Kubernetes cluster running (minikube, kind, EKS, GKE, etc.)
- `kubectl` configured and pointing at your cluster
- KubeRay operator installed:

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator
```

## Step 1: Review the Manifest

> ⚠️ **Security:** This sample uses a weak default password and disables `protected-mode` for simplicity.
> For any non-localhost or production deployment, generate a strong password (`openssl rand -base64 32`),
> enable TLS, and use network policies to restrict access.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

The sample deploys everything in one file:

| Resource | Purpose |
|----------|---------|
| `Secret/valkey-password-secret` | Valkey password (change for production) |
| `ConfigMap/valkey-config` | Valkey server configuration |
| `Deployment/valkey` | Valkey 8.1.8 server pod |
| `Service/valkey` | ClusterIP service on port 6379 |
| `ConfigMap/ray-example` | Python scripts for testing actors |
| `RayCluster/raycluster-external-valkey` | Ray cluster with GCS FT pointing at Valkey |

The key configuration is in the RayCluster spec:

```yaml
spec:
  gcsFaultToleranceOptions:
    redisAddress: "valkey:6379"
    redisPassword:
      valueFrom:
        secretKeyRef:
          name: valkey-password-secret
          key: password
```

Ray uses `redisAddress` for any Redis-protocol store — Valkey is wire-compatible, so no code changes are needed.

## Step 2: Deploy

```bash
kubectl apply -f sample/ray-cluster.external-valkey.yaml
```

Watch the pods come up:

```bash
kubectl get pods -w
```

Expected output (after ~60s):

```text
NAME                                          READY   STATUS    RESTARTS   AGE
valkey-7d4f8b6c9-xxxxx                        1/1     Running   0          45s
raycluster-external-valkey-head-xxxxx         1/1     Running   0          30s
raycluster-external-valkey-worker-small-xxx   1/1     Running   0          25s
```

## Step 3: Verify Valkey Connection

Check that the Ray head connected to Valkey by examining GCS logs:

```bash
kubectl logs -l ray.io/cluster=raycluster-external-valkey \
  -c ray-head --tail=50 | grep -i "redis\|valkey\|external storage"
```

You should see lines indicating GCS connected to the external store.

Verify Valkey has GCS data:

```bash
kubectl exec deploy/valkey -- valkey-cli -a "REPLACE-ME-WITH-STRONG-PASSWORD" --no-auth-warning DBSIZE
```

Expected: `(integer) N` where N > 0 (GCS has written metadata).

## Step 4: Access the Ray Dashboard

```bash
kubectl port-forward svc/raycluster-external-valkey-head-svc 8265:8265
```

Open [http://localhost:8265](http://localhost:8265) — you should see the cluster with 1 head + 1 worker.

## How It Works

| What Happens | Where |
|-------------|-------|
| KubeRay reads `gcsFaultToleranceOptions` | RayCluster controller |
| Sets `RAY_REDIS_ADDRESS` env on head pod | KubeRay operator |
| GCS connects to Valkey on startup | Ray head process |
| Cluster metadata persisted via RESP | Valkey `HSET`/`HGET` |
| On head restart, GCS reloads from Valkey | Ray GCS recovery |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `gcsFaultToleranceOptions.redisAddress` | Yes | — | Valkey host:port (e.g., `valkey:6379`) |
| `gcsFaultToleranceOptions.redisPassword` | No | — | Password via Secret reference |
| `gcsFaultToleranceOptions.externalStorageNamespace` | No | RayCluster UID | Isolation namespace in Valkey |

## Cleanup

```bash
kubectl delete -f sample/ray-cluster.external-valkey.yaml
```

---

[02 - Detached Actor Recovery →](02-actor-recovery.md)
