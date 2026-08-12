# AutoGPT + Valkey — Cookbook Sample

Runnable code for the [AutoGPT + Valkey cookbook series](../README.md).

`main.py` exercises the three Valkey patterns AutoGPT's platform relies on for
its cache and coordination layer — sharded pub/sub, a single-flight lock, and a
fixed-window counter — against the same three-shard cluster topology AutoGPT's
single-container distribution forms at startup.

## Prerequisites

1. Python 3.9+
2. Docker or Podman

## Setup

```bash
docker compose up -d
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Wait for the cluster to report healthy before running the sample:

```bash
docker compose ps
```

## Running

```bash
.venv/bin/python main.py
```

Expected output:

```text
Connected to Valkey cluster via 127.0.0.1:17000
  sharded pub/sub: delivered 'execution step 1 complete' to 1 subscriber
  distributed lock: acquired by 3f2a9c81, contender refused, released
  rate counter: 2 hits in window, 60s left, window not extended
All three AutoGPT coordination patterns verified.
```

The sample clears its own keys on entry and exit, so it is safe to rerun.

## Teardown

```bash
docker compose down
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `127.0.0.1` | Seed node host. The client discovers the other shards from it. |
| `VALKEY_PORT` | `17000` | Seed node port. |
| `VALKEY_PASSWORD` | — | Password, if the cluster requires one. The compose stack here does not; AutoGPT's own distribution does. |
| `VALKEY_VERSION` | `8.1.9` | Read by `docker-compose.yml` only — the bundle tag to run. |

## Pointing the sample at AutoGPT's own cluster

If you are already running AutoGPT's single-container distribution, skip
`docker compose up` — it publishes the same three ports and would collide.
Supply the password AutoGPT generated instead:

```bash
VALKEY_PASSWORD=<the password from AutoGPT's environment> .venv/bin/python main.py
```

## Compatibility

Tested against `valkey/valkey-bundle:8.1.9` and `valkey/valkey-bundle:9.1.2`.
No version-specific features are used beyond Valkey 7.2-equivalent cluster
semantics (sharded pub/sub, `EXPIRE NX`).
