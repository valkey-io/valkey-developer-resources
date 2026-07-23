# LocalAI + Valkey — Cookbook Sample

Runnable code for the [LocalAI + Valkey cookbook series](../README.md).

This sample drives LocalAI's `/stores/*` REST API with the `valkey-store`
backend: it stores four vectors, does an exact Get, a KNN Find, and a Delete,
asserting the expected result at each step.

## Prerequisites

1. Python 3.10+
2. Docker or Podman (for Valkey)
3. A running LocalAI with the `valkey-store` backend registered.

   > **Temporary — pending upstream merge.** The `valkey-store` backend is added
   > in [mudler/LocalAI#10770](https://github.com/mudler/LocalAI/pull/10770) and
   > is not yet in a released image or the backend gallery. Build it from the PR
   > branch as described in [../01-getting-started.md](../01-getting-started.md)
   > (Steps 2-3). Once merged, install it with
   > `local-ai backends install valkey-store` and start LocalAI normally.

## Setup

Start Valkey (with a health check) via compose:

```bash
docker compose up -d   # starts Valkey Search on :6379
pip install -r requirements.txt
```

Or start Valkey manually:

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:8.1.7
pip install -r requirements.txt
```

> **Note:** Commands use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.

Then build and launch LocalAI with the backend registered — see
[../01-getting-started.md](../01-getting-started.md).

## Running

```bash
python main.py
```

Expected output (abridged):

```text
Storing 4 vectors in store 'cookbook-demo' via 'valkey-store'...
  Get [1,0,0] -> pos-x

Finding nearest neighbours of [1, 0, 0]:
   pos-x  sim=+1.000
   pos-y  sim=+0.000
   pos-z  sim=+0.000
   neg-x  sim=-1.000

Deleting [1, 0, 0]...
  confirmed removed

Done. Vectors persist in Valkey across a LocalAI restart.
```

## Teardown

```bash
docker compose down
```

## Environment Variables

The sample loads `.env` (copy `.env.example`). All have working defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCALAI_BASE_URL` | `http://localhost:8080` | LocalAI server base URL. |
| `STORE_BACKEND` | `valkey-store` | Store backend; routes `/stores/*` to Valkey. |
| `STORE_NAME` | `cookbook-demo` | Store namespace (isolated keyspace + index). |
| `REQUEST_TIMEOUT` | `5.0` | Per-request HTTP timeout in seconds. |

## Compatibility

Tested against Valkey Bundle 8.1.x. The `valkey-store` backend's own integration
suite runs against Valkey Bundle 9.x, so both lines are supported.
