# Valkey as a job queue and admission gate for llm-d

Use Valkey as the durable job queue and the admission (quota) gate behind a real
distributed-inference system. This cookbook points [llm-d](https://llm-d.ai)'s
async batch processor at Valkey, submits a batch of inference jobs, and shows the
work living in Valkey: a sorted set holding the queued jobs in priority order,
and a second sorted set enforcing a per-user admission quota.

Both patterns are reusable on their own: a priority work queue and a
sliding-window rate limiter, both built on the Valkey sorted set. llm-d is the
real-world example that exercises them. llm-d is pointed at Valkey by a
connection URL alone.

## The Valkey feature

A **sorted set** (ZSET) orders members by a score. That one structure does two
jobs here:

- **Priority job queue** (`request-sortedset`). Each job is a member of the
  sorted set, scored by its deadline plus a monotonic enqueue sequence. Jobs come
  off the queue in score order, so higher-priority jobs go first and ties break in
  submission order. llm-d enqueues with a Lua script for atomicity; the async
  processor pops the next job, dispatches it, and removes it.
- **Admission quota** (`quota:userid:<id>`). The quota gate records each admitted
  request as a scored member in a per-user sorted set and counts the members
  inside a time window. When the count reaches the limit, further requests are
  refused until the window rolls forward: a sliding-window rate limiter.

## What you'll have working at the end

A three-container stack (Valkey, llm-d's async batch processor, and a stub
inference backend) plus a small job producer. A notebook submits jobs and reads
Valkey directly so you can watch:

- the queue fill in priority order and drain as jobs dispatch,
- results come back from the backend,
- a burst past the quota get refused, with the refusals visible both in Valkey's
  quota sorted set and in the processor's `quota_exhausted` metric.

The whole stack is lightweight (no GPU, no model download) and runs on any
machine with a container runtime and Compose.

## How it works

```
  producer  --submit-->  Valkey (request-sortedset)  <--poll--  async-processor
                         Valkey (quota:userid:*)      <--gate--  async-processor
  async-processor  --dispatch admitted jobs-->  llm-sim (/v1/completions)
  async-processor  --write results-->  Valkey (result-list)  --read-->  producer
```

The services (defined in [`docker-compose.yml`](docker-compose.yml)):

- **valkey**. The store. Holds `request-sortedset` (the queue), the
  `quota:userid:*` sorted sets (the gate), and `result-list` (results).
- **async-processor**. llm-d's real async batch component
  (`ghcr.io/llm-d/llm-d-async`), unmodified, pointed at Valkey by the `url` in
  [`transport-config.json`](transport-config.json). It dequeues jobs, applies the
  `redis-quota` admission gate, and forwards admitted jobs to the backend.
- **llm-sim**. A stub inference backend
  ([`llm-d-inference-sim`](https://github.com/llm-d/llm-d-inference-sim)) that
  speaks the OpenAI `/v1/completions` API with instant fake completions. This
  cookbook is about Valkey holding the queue and quota, not about inference, so
  the backend is deliberately simulated: no GPU, no weights.

Jobs are submitted by a small **producer** (in [`producer/`](producer/)) built on
llm-d's public [`producer`](https://pkg.go.dev/github.com/llm-d/llm-d-async/producer)
Go library, so the jobs that land in Valkey are exactly what the async processor
expects. Its dependencies are committed to the repo (under
[`producer/vendor/`](producer/)) rather than downloaded at build time, so you
build it once as a container with no network access and no Go toolchain on your
machine.

### "Works with Valkey unchanged"

llm-d speaks the Redis serialization protocol, which Valkey implements, so it
talks to Valkey with no code change. llm-d's own Helm chart documents this:
"Compatible with any Redis-protocol server including Valkey" and that all
`redis.*` fields work unchanged when pointed at a Valkey endpoint. The only
configuration that points llm-d at Valkey is the `url` in `transport-config.json`.

## Prerequisites

- **A container runtime with Compose** (Docker Compose or compatible).
- **Memory.** A few GiB is plenty. The stack has no GPU, no model, and no
  Kubernetes, and runs in well under 1 GiB of container memory. 4 GiB for the
  runtime is comfortable.
- To build the producer image: just the container runtime, nothing else. You do
  not need a Go toolchain or network access for the build, because the producer's
  Go dependencies are already committed to this repo (under `producer/vendor/`)
  instead of being downloaded during the build.
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management, to open
  the notebook. Install it with the official installer:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  (or `brew install uv`, or see the uv docs for other platforms). `uv sync`
  reads `pyproject.toml` and `uv.lock` to reproduce the exact environment.

## Run it

The commands below use Docker. With Podman, run the same commands with `podman`
and `podman compose`; the notebook and the structural tests detect whichever of
`docker` or `podman` is installed (set `CONTAINER_ENGINE` to force one). If your
`podman compose` predates `--wait` (podman-compose 1.0.x, e.g. the one Ubuntu
24.04 ships), run `podman compose up -d` and wait until `podman compose ps` shows
every container healthy.

### 1. Build the producer image

```bash
docker build -t llm-d-valkey-producer ./producer
```

### 2. Start the stack

```bash
docker compose up -d --wait
docker compose ps
```

All three services should be `Up`; `valkey` reports `healthy`. The async
processor connects to Valkey and begins polling `request-sortedset`.

### 3. Open the notebook

```bash
uv sync
uv run jupyter lab queue-and-quota-with-valkey.ipynb
```

The notebook submits jobs through the producer container and reads the queue,
results, and quota state from Valkey with the Valkey client.

### 4. Tear down

```bash
docker compose down
```

## Notes on the setup

- **The async processor needs a kubeconfig to start, even off Kubernetes.** It
  builds a controller-runtime metrics server at startup, which calls
  `GetConfigOrDie()` unconditionally; off-cluster that fails unless some
  kubeconfig is present. [`kubeconfig-dummy.yaml`](kubeconfig-dummy.yaml) is a
  stub pointing at an unreachable API, mounted into the container with
  `KUBECONFIG` set. With `--metrics-endpoint-auth=false`, the processor never
  contacts a Kubernetes API, so the config only needs to parse.
- **The backend is a simulator.** Completions are fake; this cookbook
  demonstrates Valkey's role in queueing and admission, not inference quality. To
  run against a real model, point `igw_base_url` at any OpenAI-compatible
  endpoint.
- **Image pins.** All three images are pinned to released tags.
  `llm-d-async` is pinned to its `v1.0.0` release by digest, so the queue and
  gate behavior is reproducible.
- **Vendored producer dependencies.** `producer/vendor/` holds the producer's Go
  dependencies so the image builds with no network, which matters on locked-down
  or sandboxed setups where the build container cannot reach the Go module proxy.
  To update them, bump the versions in `producer/go.mod` and re-run
  `go mod tidy && go mod vendor` in `producer/`, then delete any Markdown that
  `go mod vendor` pulls in (`find producer/vendor -name '*.md' -delete`) so the
  third-party docs don't trip the repo's Markdown linter. Only the Go sources,
  `LICENSE` files, and `modules.txt` are needed to build.
