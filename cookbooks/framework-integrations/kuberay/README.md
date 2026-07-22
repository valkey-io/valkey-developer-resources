# Ray/KubeRay + Valkey

> Use Valkey as the GCS fault tolerance backend for Ray clusters on Kubernetes — a BSD-3 licensed, wire-compatible drop-in replacement for Redis.

**Who is this for:** Platform engineers and ML engineers running Ray on Kubernetes (via KubeRay) who want GCS fault tolerance with an open-source, Linux Foundation-governed metadata store.

## Prerequisites

- Kubernetes cluster (minikube, kind, or EKS/GKE)
- `kubectl` configured
- KubeRay operator installed ([installation guide](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/raycluster-quick-start.html))
- No special credentials needed

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Deploy Valkey + RayCluster with GCS fault tolerance. Verify the cluster connects to Valkey. | Beginner, ~15 min, Kubernetes |
| 02 | <nobr>[Detached Actor Recovery](02-actor-recovery.md)</nobr> | Create a detached actor, kill the head node, verify state survives via Valkey-backed GCS. | Intermediate, ~20 min, Kubernetes, Python |

## Why Valkey for GCS Fault Tolerance?

Ray's Global Control Service (GCS) stores cluster metadata — actor locations, placement groups, task lineage. By default, this state lives in-memory on the head node. If the head crashes, it's lost.

GCS fault tolerance externalizes this state to a Redis-protocol store. Valkey is wire-compatible with Redis and provides:

- **BSD-3 license** (vs Redis's dual RSALv2/SSPLv1)
- **Linux Foundation governance** — vendor-neutral, community-driven
- **Drop-in compatibility** — same RESP protocol, same `--requirepass`, same port
- **No code changes** — Ray's `redisAddress` config works with Valkey unmodified
