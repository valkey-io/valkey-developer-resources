# Detached Actor Recovery

> Prove GCS fault tolerance works: create a detached actor, kill the head node, watch Ray recover the actor from Valkey-backed state.

**Intermediate** · Kubernetes, Python · ~20 min

**Who is this for:** ML engineers who need to verify that long-running Ray actors (serving models, aggregating state) survive infrastructure disruptions when backed by Valkey.

## What Are Detached Actors?

Normal Ray actors die when their creator disconnects. **Detached actors** (`lifetime="detached"`) persist
beyond their creator — they live until explicitly killed or the cluster loses GCS state.

With GCS fault tolerance enabled, detached actor registrations are stored in Valkey. Even if the head node
crashes and restarts, the actor's registration is recovered from Valkey and the actor remains accessible.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (cluster running with Valkey)
- `kubectl` access to the cluster

## Step 1: Create a Detached Actor

Exec into the head pod and run the actor creation script:

```bash
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/detached_actor.py
```

This creates a `Counter` actor with `lifetime="detached"` in the `default_namespace` namespace.

The script:

```python
import ray

@ray.remote(num_cpus=1)
class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value

ray.init(namespace="default_namespace")
Counter.options(name="counter_actor", lifetime="detached").remote()
```

## Step 2: Increment the Counter

```bash
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/increment_counter.py
```

Expected output: `1`

Run it again: `2`, `3`, etc. The counter state lives in the worker process; the actor *registration* lives in GCS (backed by Valkey).

## Step 3: Verify GCS State in Valkey

Check that Valkey has the actor metadata:

```bash
kubectl exec deploy/valkey -- valkey-cli -a "REPLACE-ME-WITH-STRONG-PASSWORD" --no-auth-warning DBSIZE
```

The count should be > 0, confirming GCS data is persisted.

## Step 4: Kill the Head Node

Simulate a head node failure:

```bash
kubectl delete pod $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name | sed 's|pod/||')
```

Watch KubeRay create a new head pod:

```bash
kubectl get pods -w -l ray.io/cluster=raycluster-external-valkey
```

Wait until the new head pod is `Running` and `1/1 Ready` (~30-60s).

## Step 5: Verify Actor Recovery

Once the new head is running, the actor should still be accessible:

```bash
kubectl exec -it $(kubectl get pod -l ray.io/cluster=raycluster-external-valkey,ray.io/node-type=head -o name) \
  -- python /home/ray/samples/increment_counter.py
```

Expected output: the next number in sequence (e.g., `4` if you incremented 3 times before the kill).

**What happened:**

1. Head pod died → GCS process stopped
2. KubeRay restarted the head pod
3. New GCS process connected to Valkey
4. GCS reloaded actor registrations from Valkey
5. `ray.get_actor("counter_actor")` resolved successfully
6. The actor (running on the worker, which never died) continued from where it left off

## How It Works

```text
Before kill:
  Head (GCS) ──persists──► Valkey (actor registry)
  Worker ◄──resolves───── GCS

After head restart:
  New Head (GCS) ──reads──► Valkey (actor registry still intact)
  Worker ◄──resolves───── New GCS (same actor found)
```

The worker process with the `Counter` actor never died (only the head did). GCS fault tolerance ensures the new head can find and reconnect to existing actors.

## What Would Fail Without GCS FT?

Without `gcsFaultToleranceOptions`, killing the head means:

- All actor registrations lost
- `ray.get_actor("counter_actor")` raises `ValueError: Failed to look up actor`
- Workers become orphaned and eventually time out

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ValueError: Failed to look up actor` | GCS didn't recover | Check Valkey connectivity: `kubectl exec deploy/valkey -- valkey-cli ping` |
| Head pod stuck in `Pending` | Resource pressure | Check `kubectl describe pod` for scheduling issues |
| Counter resets to 1 | Worker was also killed | Only kill the head pod, not the worker |
| `ConnectionError` to Valkey | Secret mismatch | Verify password in Secret matches what Valkey started with |

## Cleanup

```bash
kubectl delete -f sample/ray-cluster.external-valkey.yaml
```

---

[← 01 - Getting Started](01-getting-started.md)
