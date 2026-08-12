# Running AutoGPT's Valkey Layer in Production

> Authentication, TLS, announced shard addresses, timeouts and memory policy — the settings that decide whether AutoGPT's coordination layer works against a real deployment instead of a laptop.

**Advanced** · Python · ~25 min

**Who is this for:** Operators pointing a self-hosted AutoGPT platform at a Valkey cluster they run or buy, who need to know which deployment properties are hard requirements and which are tuning.

The cluster from [01 - Getting Started](01-getting-started.md) is deliberately insecure and deliberately local. This guide covers what changes when the deployment is real. The order matters: the announced-address section is the one that most often turns a correct-looking configuration into agent output that never arrives.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) and [02 - Coordination Patterns](02-coordination-patterns.md)
- A Valkey cluster you can reconfigure, or a managed cluster you can inspect
- `valkey-cli` available locally, or shell access to a node

## Step 1: Turn on authentication

AutoGPT's single-container distribution runs its shards with a password and keeps protected mode on. Two settings are needed, not one:

```text
requirepass  <password>
masterauth   <password>
```

`requirepass` makes clients authenticate. `masterauth` is what a replica uses to authenticate *to* its primary — omit it and replication silently fails to start on any deployment that has replicas. The single-container distribution runs no replicas but sets both, which is the right habit.

On the client side, credentials are part of the configuration:

```python
import os

from glide import (
    GlideClusterClient,
    GlideClusterClientConfiguration,
    NodeAddress,
    ServerCredentials,
)

password = os.environ["VALKEY_PASSWORD"]
config = GlideClusterClientConfiguration(
    addresses=[NodeAddress(os.environ["VALKEY_HOST"], 17000)],
    credentials=ServerCredentials(password=password),
    request_timeout=5000,
)
client = await GlideClusterClient.create(config)
```

Read the password from the environment or a secret store — never from a literal in source. AutoGPT reads it from `REDIS_PASSWORD`.

Once a password is set, protected mode stops mattering: Valkey's protected mode exists to refuse remote connections to an *unauthenticated* node. Keeping it on costs nothing and catches the case where the password is accidentally removed.

## Step 2: Encrypt the connection

Valkey needs certificates and `tls-port` configured server-side; the client side is one flag:

```python
config = GlideClusterClientConfiguration(
    addresses=[NodeAddress(os.environ["VALKEY_HOST"], 6379)],
    credentials=ServerCredentials(password=password),
    use_tls=True,
    request_timeout=5000,
)
```

The `valkey/valkey-bundle` image does not enable TLS by default, so the local cluster in this series is plaintext. Most managed offerings enable in-transit encryption as an option or a default — check which, because a client with `use_tls=False` against a TLS-only endpoint fails as a connection error with no hint about the cause.

## Step 3: Get announced addresses right

This is the requirement that most often bites, and the symptom is not an error.

A cluster client asks a node for the topology and gets back one address per shard — the address each shard *announces*. Those addresses must be reachable, as-is, from wherever the platform runs.

AutoGPT's backend adds a wrinkle. By default it rewrites every shard address it receives, replacing the host with the seed host it was configured with and keeping only the announced port. That rewrite exists for the local three-container development stack, where shards announce Compose hostnames that a host-native client cannot resolve. Set `REDIS_USE_ANNOUNCED_ADDRESS=true` to switch it off and use the announced addresses directly.

You need that variable set for any deployment where shards live at **distinct hostnames on a shared port** — which is exactly how managed clusters are addressed:

| Deployment shape | Announced addresses | Rewrite behaviour | Setting |
| --- | --- | --- | --- |
| One host, distinct ports (this series, AutoGPT's single container) | `127.0.0.1:17000`, `:17001`, `:17002` | Harmless — host is already the seed host | Either |
| Distinct hostnames, shared port (managed clusters) | `shard-1.example:6379`, `shard-2.example:6379` | **Collapses every shard onto the seed host** | `REDIS_USE_ANNOUNCED_ADDRESS=true` |
| Compose service names, host-native client | `valkey-0:17000`, `valkey-1:17001` | Required — the names do not resolve on the host | Leave the rewrite on |

When the rewrite collapses the topology, ordinary commands still appear to work: the seed node answers, and a `MOVED` redirect gets the client to the right place eventually. Sharded pub/sub does not recover, because it is routed by slot and there is no redirect to follow — the publish lands on a shard that has no subscribers, returns `0`, and the message is discarded. Agent output stops arriving and nothing logs an error. [02 - Coordination Patterns](02-coordination-patterns.md) shows the assertion that catches this.

Inspect what your cluster actually announces before you decide:

```bash
valkey-cli -h "$VALKEY_HOST" -p 17000 -a "$VALKEY_PASSWORD" --no-auth-warning cluster shards
```

Check that each shard reports a distinct `endpoint` and that every one of those endpoints resolves and connects from a host running the platform.

## Step 4: Confirm the deployment can serve the workload

Three properties are hard requirements. A deployment missing any of them cannot run the platform, and no configuration works around it:

1. **Cluster mode enabled.** The backend speaks only the cluster protocol. A single node, or a cluster-mode-disabled managed instance, is not usable — this is the constraint from 01.
2. **Sharded pub/sub** (`SPUBLISH`, `SSUBSCRIBE`, `SUNSUBSCRIBE`). No fallback path exists in the platform.
3. **Reachable announced addresses**, per Step 3.

The commands the platform issues imply this version floor:

| Requirement | Commands |
| --- | --- |
| Valkey 7.2-equivalent semantics | Sharded pub/sub (`SPUBLISH`/`SSUBSCRIBE`/`SUNSUBSCRIBE`), `EXPIRE … NX` |
| Valkey 6.2-equivalent semantics | `LPOP` with a `count` argument, `GETEX` |

Both `valkey/valkey-bundle:8.1.9` and `valkey/valkey-bundle:9.1.2` clear it; this series is tested against both.

The coordination layer uses **no modules** — no `FT.*`, `JSON.*`, `BF.*` or `TS.*` commands — so there is nothing extra to provision or license for it. It does use Streams, server-side scripts (`EVAL`) and transactions within a single hash slot, which a thin protocol proxy in front of a cluster may not implement in full. If you are running through a proxy, test those three specifically.

## Step 5: Set timeouts and retries deliberately

Defaults on both sides are wrong for a networked deployment in opposite directions — the client's are too tight, and a socket with no timeout is unbounded.

AutoGPT exposes its client tunables as environment variables:

| Variable | Default | What it bounds |
| --- | --- | --- |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | `5` s | Establishing a connection to a shard |
| `REDIS_SOCKET_TIMEOUT` | `30` s | A single read or write on an established connection |
| `REDIS_HEALTH_CHECK_INTERVAL` | `30` s | How often idle connections are probed, so a dead one is found before a request needs it |
| `REDIS_RETRY_ATTEMPTS` | `5` | Retries on a connection error, with backoff between them |

Raise the connect timeout if your cluster is across a region boundary; the platform's default assumes something closer. Lower `REDIS_SOCKET_TIMEOUT` if you would rather fail a request than let it hang for half a minute — the coordination commands here are all sub-millisecond server-side, so a 30-second read means something is badly wrong, not merely slow.

On the client in this series, the equivalent is `request_timeout`. Set it explicitly and catch what it raises:

```python
from glide import ClosingError, ConnectionError, RequestError, TimeoutError

try:
    await client.incr(RATE_KEY)
except TimeoutError:
    # Reachable precisely because request_timeout is set. Shed the request
    # rather than queueing behind a wedged shard.
    ...
except (ConnectionError, ClosingError):
    # Topology or reachability problem — retrying immediately will not help.
    ...
except RequestError:
    # The server rejected the command: auth, CROSSSLOT, wrong type.
    ...
```

Retries deserve one caution. Retrying a failed `INCR` can double-count, because the first attempt may have applied before the connection dropped. Rate counters tolerate that; spend counters tolerate it less well. Where exactness matters, make the operation idempotent rather than relying on the retry count.

## Step 6: Decide what happens when memory fills

AutoGPT's single-container distribution enables append-only persistence (`appendonly yes`) and sets no `maxmemory`, so its cluster never evicts — it grows until the container's limit stops it. For a development image that is the right trade: nothing silently disappears.

For a real deployment the choice is less comfortable, because the coordination layer mixes two kinds of data in one keyspace:

- **Regenerable:** cached lookups, session metadata. Losing these costs a round trip.
- **Load-bearing while live:** locks and rate-limit counters. Evicting a held lock lets a second worker into a guarded step; evicting a counter resets someone's allowance.

Every `maxmemory-policy` that evicts can take a lock or a counter — `allkeys-*` by definition, and `volatile-*` too, since locks and counters are precisely the keys that carry a TTL. So eviction is not a safe substitute for capacity. Size memory so eviction is an alarm rather than a routine, and treat locks as advisory, as [02 - Coordination Patterns](02-coordination-patterns.md) argues on independent grounds.

Persistence is a separate decision. Nothing in this layer is a system of record — PostgreSQL is — so persistence buys faster recovery, not durability of state you cannot rebuild. Choose it on restart behaviour, and remember that AOF `fsync` policy is the setting that governs its cost.

## Step 7: Verify before you cut over

Point the sample at the real cluster before you point the platform at it. It exercises all three patterns and asserts on each:

```bash
VALKEY_HOST=<host> VALKEY_PORT=<port> VALKEY_PASSWORD=<password> \
  .venv/bin/python sample/main.py
```

A pass tells you the deployment satisfies every hard requirement in Step 4, including the announced-address one — the sharded publish asserts a subscriber count of exactly `1`, which is the check that fails on a collapsed topology.

## Configuration Reference

AutoGPT-side variables. The names are engine-neutral and unchanged from before Valkey was an option:

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `REDIS_HOST` | — | `localhost` | Seed node host. The default only ever works for a local deployment. |
| `REDIS_PORT` | — | `6379` | Seed node port. Note the default is the standalone port, not the `17000` the bundled cluster uses. |
| `REDIS_PASSWORD` | — | — | Password, if the cluster requires one. |
| `REDIS_CLUSTER_HOST` | — | — | Takes precedence over `REDIS_HOST` when set. |
| `REDIS_CLUSTER_PORT` | — | — | Takes precedence over `REDIS_PORT` when set. |
| `REDIS_USE_ANNOUNCED_ADDRESS` | — | `false` | Use announced shard addresses as-is instead of rewriting them onto the seed host. Required for distinct-hostname deployments — see Step 3. |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | — | `5` | Connect timeout, seconds. |
| `REDIS_SOCKET_TIMEOUT` | — | `30` | Per-operation socket timeout, seconds. |
| `REDIS_HEALTH_CHECK_INTERVAL` | — | `30` | Idle-connection probe interval, seconds. |
| `REDIS_RETRY_ATTEMPTS` | — | `5` | Per-command retries, with exponential backoff from 0.1 s capped at 10 s. Applied to connection errors, timeouts and cluster-down errors only. |

Server-side settings referenced above:

| Setting | Recommended | Description |
| --- | --- | --- |
| `requirepass` | Set it | Client authentication. |
| `masterauth` | Same value | Replica-to-primary authentication. Required wherever replicas exist. |
| `protected-mode` | `yes` | Refuses remote connections to an unauthenticated node. |
| `cluster-enabled` | `yes` | Hard requirement — the backend has no standalone path. |
| `maxmemory-policy` | `noeviction` | Any evicting policy can drop a live lock or counter. Size for capacity instead. |
| `appendonly` | Your call | Faster restarts, not durability of anything irreplaceable. |

## Scope

This guide covers configuration that decides whether the layer works and whether it is secure. It does not cover capacity planning, failover testing or `fsync` tuning — those depend on your traffic and your recovery targets, and they need measurement against your own deployment rather than a recommended number.

---

[← 02 - Coordination Patterns](02-coordination-patterns.md)
