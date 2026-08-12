# Getting Started with AutoGPT and Valkey

> Stand up the three-shard Valkey cluster the AutoGPT platform expects, connect to it with valkey-glide, and confirm the coordination layer works end to end.

**Beginner** · Python · ~10 min

**Who is this for:** Python developers self-hosting the AutoGPT platform who need to understand — and verify — the Valkey cluster it depends on for caching, locking, rate limiting and agent-output streaming.

[AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) is an open-source platform for building and running continuous AI agents, developed by the Significant-Gravitas project. Alongside PostgreSQL and RabbitMQ, its backend depends on a Valkey-compatible engine for a specific set of jobs: caching, distributed locking, rate limiting, spend and usage counters, session metadata, pending-message buffers, and the server-sent-event streams that carry agent output to the browser.

Valkey is the engine inside AutoGPT's [single-container distribution](https://github.com/Significant-Gravitas/AutoGPT/tree/dev/autogpt_platform/single-container), which starts three `valkey-server` processes and forms them into a cluster before the backend boots. (That distribution lives on AutoGPT's `dev` branch and has not reached a tagged release yet.) This guide reproduces that topology on its own, so you can exercise and troubleshoot the coordination layer without running the whole platform.

One thing to know before you start: **AutoGPT's backend always connects with a cluster client, so a single standalone node will not work.** That is a deliberate choice — running a real multi-shard cluster in development means cross-slot bugs surface on a laptop rather than in production. Everything below therefore uses a cluster, never a lone node.

## Prerequisites

- Docker or Podman
- Python 3.9 or newer
- The `valkey-glide` client (installed in Step 2) — the only third-party dependency in this series
- No LLM API key. This series covers AutoGPT's coordination layer only, so nothing here calls a model provider.

## Step 1: Start a three-shard Valkey cluster

The [`sample/`](sample/) directory ships a Compose file that reproduces AutoGPT's topology: three shards on `127.0.0.1:17000`, `17001` and `17002`, no replicas, each announcing `127.0.0.1`.

```bash
cd sample
docker compose up -d
```

The image is pinned:

```yaml
services:
  valkey-cluster:
    image: valkey/valkey-bundle:8.1.9
```

Set `VALKEY_VERSION` to run a different one — CI exercises this series against 8.1.x and 9.x:

```bash
VALKEY_VERSION=9.1.2 docker compose up -d
```

> **Note:** All examples use `docker`. Substitute `podman` if that is your container runtime — the commands are identical.

All three shards run inside one container, exactly as they do in AutoGPT's distribution. That detail matters: cluster clients follow the addresses a cluster *announces*, and shards sharing one network namespace can all announce `127.0.0.1` and still gossip with each other. Three separate containers each announcing `127.0.0.1` would talk only to themselves.

Wait for the cluster to form. The Compose healthcheck reports healthy only once every slot is assigned, not merely when the process is up:

```bash
docker compose ps
```

Confirm it directly:

```bash
docker compose exec valkey-cluster valkey-cli -p 17000 cluster info
```

Look for `cluster_state:ok` and `cluster_known_nodes:3`.

> ⚠️ **Security:** This cluster runs with no authentication and no TLS, and disables protected mode so a published port can reach it. It is bound to `127.0.0.1` only, so it is not reachable from outside your machine — but do not copy this configuration to a shared host. AutoGPT's own distribution sets a password instead; [03 - Production](03-production.md) covers authentication, TLS and announced addresses. See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 2: Install the client

Use a virtual environment — never a system-wide install:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

That pins one dependency:

```text
valkey-glide==2.5.1
```

AutoGPT's own backend uses redis-py's cluster client. This series uses `valkey-glide` because it is the Valkey project's own client and speaks the same cluster protocol to the same topology — nothing below depends on which of the two you pick.

## Step 3: Connect

A cluster client needs one seed address and discovers the rest of the topology from it. This is the whole connection:

```python
import asyncio

from glide import (
    GlideClusterClient,
    GlideClusterClientConfiguration,
    NodeAddress,
)

# GLIDE's default request timeout is 250 ms, which is tight enough to fail
# spuriously against anything but localhost. Start at 5000 ms and lower it
# once you have measured your own p99.
REQUEST_TIMEOUT_MS = 5000


async def main():
    config = GlideClusterClientConfiguration(
        addresses=[NodeAddress("127.0.0.1", 17000)],
        request_timeout=REQUEST_TIMEOUT_MS,
    )
    client = await GlideClusterClient.create(config)
    try:
        print(await client.info())
    finally:
        # Always release the connection, even if the body raised.
        await client.close()


asyncio.run(main())
```

Two things are worth noticing. First, a cluster client refuses to connect to a standalone node, so reaching the line after `create` already proves the cluster is formed — the same requirement AutoGPT's backend imposes on whatever deployment you point it at. Second, `request_timeout` is set explicitly rather than left at the default, so a wedged shard surfaces as a timeout instead of a hang.

## Step 4: Run the sample

[`sample/main.py`](sample/main.py) exercises the three patterns AutoGPT depends on — sharded pub/sub, a single-flight lock, and a fixed-window counter:

```bash
.venv/bin/python main.py
```

```text
Connected to Valkey cluster via 127.0.0.1:17000
  sharded pub/sub: delivered 'execution step 1 complete' to 1 subscriber
  distributed lock: acquired by 3f2a9c81, contender refused, released
  rate counter: 2 hits in window, 60s left, window not extended
All three AutoGPT coordination patterns verified.
```

Each line is an assertion, not a log statement: the sample fails loudly if a message is not delivered, if a second lock acquisition succeeds, or if a rate-limit window gets extended when it should not. It clears its own keys on entry and exit, so it is safe to rerun.

[02 - Coordination Patterns](02-coordination-patterns.md) walks through what each of those three does and why AutoGPT needs it.

## Step 5: Tear down

```bash
docker compose down
```

The cluster keeps no volumes — it is cache-only, so every `docker compose up` starts from empty state.

## How It Works

| Component | Role |
| --- | --- |
| AutoGPT backend | Issues the cache and coordination commands: locks, counters, session metadata, pending-message buffers |
| Valkey cluster (3 shards) | Serves those commands, and routes sharded pub/sub by channel slot |
| `valkey-glide` cluster client | Discovers the topology from a seed address and routes each command to the shard that owns its slot |
| Compose healthcheck | Gates startup on `cluster_state:ok`, so no client connects before every slot is assigned |
| Hash tags (`{...}`) | Keep an execution's keys and channel on one shard, so multi-key commands stay legal |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_HOST` | — | `127.0.0.1` | Seed node host for the sample. Other shards are discovered from it. |
| `VALKEY_PORT` | — | `17000` | Seed node port. |
| `VALKEY_PASSWORD` | — | — | Password, if the cluster requires one. This Compose stack does not; AutoGPT's distribution does. |
| `VALKEY_VERSION` | — | `8.1.9` | Bundle tag Compose runs. Read by Compose only, not by the sample. |
| `request_timeout` | — | `250` ms | Client-side per-request deadline. Set it explicitly; the default is too tight for anything but localhost. |

On the AutoGPT side the same settings are named `REDIS_HOST`, `REDIS_PORT` and `REDIS_PASSWORD` — engine-neutral names it keeps for backward compatibility. [03 - Production](03-production.md) lists them, along with the cluster-specific variables that decide whether a managed deployment works at all.

---

[02 - Coordination Patterns →](02-coordination-patterns.md)
