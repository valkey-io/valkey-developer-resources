# Ray/KubeRay + Valkey Sample

Kubernetes manifests for deploying a RayCluster with Valkey-backed GCS fault tolerance.

## Prerequisites

- Kubernetes cluster (minikube, kind, EKS, GKE)
- `kubectl` configured
- KubeRay operator installed:

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator
```

## How to Run

```bash
# Deploy Valkey + RayCluster
kubectl apply -f ray-cluster.external-valkey.yaml

# Wait for pods
kubectl get pods -w

# Verify Valkey has GCS data
kubectl exec deploy/valkey -- valkey-cli -a "5241590000000000" --no-auth-warning DBSIZE
```

## Expected Output

After ~60 seconds, all pods should be Running:

```text
NAME                                          READY   STATUS    RESTARTS   AGE
valkey-7d4f8b6c9-xxxxx                        1/1     Running   0          45s
raycluster-external-valkey-head-xxxxx         1/1     Running   0          30s
raycluster-external-valkey-worker-small-xxx   1/1     Running   0          25s
```

`DBSIZE` should return a value > 0 (GCS metadata stored in Valkey).

## Test Detached Actor Recovery

```bash
# Create detached actor
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/detached_actor.py

# Increment counter
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/increment_counter.py
# Output: 1

# Kill head node
kubectl delete pod $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name | sed 's|pod/||')

# Wait for new head (~30-60s)
kubectl get pods -w -l ray.io/cluster=raycluster-external-valkey

# Verify actor survived
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/increment_counter.py
# Output: 2 (counter state preserved!)
```

## Teardown

```bash
kubectl delete -f ray-cluster.external-valkey.yaml
```

## Images Used

| Image | Version | Purpose |
|-------|---------|---------|
| `valkey/valkey` | `8.1.8-alpine` | GCS fault tolerance backend |
| `rayproject/ray` | `2.52.0` | Ray head + worker |

## Reference

- [KubeRay PR #5015](https://github.com/ray-project/kuberay/pull/5015) — upstream Valkey support
- [Ray GCS FT docs](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/gcs-ft.html)
