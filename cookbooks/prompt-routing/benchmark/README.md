# Prompt-routing latency benchmark

> Optional and GPU-only. The rest of the recipe runs locally on CPU for free.
> This benchmark measures what the routing index buys you end to end:
> time-to-first-token with llm-d's precise prefix-cache routing, against
> random routing, on real GPUs.

The recipe notebook shows how llm-d's router keeps its index in Valkey. This
benchmark runs the real thing: four vLLM replicas emitting KV-cache events,
llm-d's router (the Endpoint Picker, behind Envoy) writing those events into
Valkey and routing on them, and a load generator that sends many users'
prompts built on a few long, shared system prompts.

No Kubernetes is involved. Every component is a container, and the router
reads its list of replicas from a file using llm-d's file-discovery plugin,
following llm-d's
[no-Kubernetes deployment guide](https://github.com/llm-d/llm-d/tree/main/guides/no-kubernetes-deployment).

## Results

Not run yet. This section will hold the measured numbers, the exact host,
and the command that produced them.

## What it compares

`scripts/run-benchmark.sh` runs the same workload once per routing strategy:

| Strategy | How the router picks a replica |
| --- | --- |
| `random` | At random. Each replica still has its own prefix cache, but requests aren't steered to it. |
| `approximate` | llm-d's default prefix-aware scorers, which estimate cache contents from the requests they've routed. No KV events, no Valkey. |
| `precise-memory` | Precise prefix-cache routing from vLLM's KV events, with the index in the router's memory. |
| `precise-valkey` | The same, with the index in Valkey. |

Before each strategy the script clears every replica's prefix cache and
flushes Valkey, so every strategy starts cold. All four use the same Envoy
and router path; only the router config changes.

Comparing `precise-memory` with `precise-valkey` shows what moving the index
out of the router process costs in latency. The reason to move it is that a
Valkey index outlives the router process and can be shared. A single-router
run like this one doesn't measure that benefit.

## What you need

- A Linux host with four NVIDIA GPUs of 24 GB or more (the defaults are
  sized for an AWS `g6.12xlarge`, 4x L4).
- Docker with the Compose plugin, the NVIDIA Container Toolkit, and
  `python3`.
- About 100 GB of free disk for images and model weights.
- Outbound internet access to pull images and the model. The default model,
  `Qwen/Qwen3-8B`, is ungated, so no Hugging Face token is needed.

To get such a host on AWS, see [`terraform/aws/`](terraform/aws/). Any other
NVIDIA host works the same way.

## Run it

```bash
cd cookbooks/prompt-routing/benchmark
cp .env.example .env        # optional: change the model or workload
sudo ./scripts/run-benchmark.sh
```

The first run downloads about 16 GB of weights and several GB of images, and
the vLLM replicas take a few minutes to start. After that, each strategy
takes a few minutes, depending on the workload settings.

When it finishes, the results are in `results/<run-id>/`:

- `summary.md`: the comparison table
- `run.yaml`: model, settings, image tags, GPUs, and the calibrated
  `peakPrefillThroughput`
- `<strategy>/`: inference-perf's per-stage and per-request reports, the
  router log, and `index.txt`, which records how many keys the router left in
  Valkey (nonzero only for `precise-valkey`)

Stop everything with `sudo docker compose down`.

## How it's wired

```text
loadgen (inference-perf)
   |
   v
envoy :8081  --ext_proc-->  EPP (router)  --reads/writes-->  valkey
   |                          ^
   |                          | KV-cache events (ZMQ :5556, replay :5559)
   v                          |
vllm-0 .. vllm-3  ------------+
```

| File | Purpose |
| --- | --- |
| `compose.yaml` | All services on one bridge network with fixed IPs |
| `vllm/serve-vllm.sh` | vLLM flags: block size 64, KV events, render endpoints, cached-token reporting |
| `epp/*.yaml` | Router config for each strategy, plus `endpoints.yaml` for file discovery |
| `envoy/envoy.yaml` | Envoy config, copied from llm-d's no-Kubernetes guide |
| `loadgen/shared-prefix.yaml` | inference-perf workload template |
| `scripts/run-benchmark.sh` | Runs everything, one strategy at a time |
| `scripts/benchctl.py` | Calibration, cache reset, and readiness helpers |
| `scripts/render.py`, `scripts/summarize.py` | Config templating and the results table |

### Workload

Sixteen system prompts of 4,096 tokens each, 64 users per prompt, a
256-token question, and 64 output tokens. Stage 0 (128 requests) warms the
caches and is left out of the summary. Then come 512 requests each at 8, 16,
and 32 concurrent users. The seed is fixed, so every strategy sees the same
prompts.

The sizes are chosen so the shared prefixes (about 65k tokens) don't fit in
one replica's KV cache but do fit across all four. With random routing, each
replica has to cache every prefix and keeps evicting. With prefix routing,
each replica holds about a quarter of them. If you change the model or GPU,
check the `GPU KV cache size` line in `results/<run-id>/vllm-0.log` and
adjust `NUM_PREFIXES` or `SYSTEM_PROMPT_LEN` to keep that relationship.

### Calibration

The precise strategies estimate each replica's prefill time from
`peakPrefillThroughput`, which depends on the model and GPU. The script
measures it before the first strategy runs. It sends random-token prompts of
`MAX_NUM_BATCHED_TOKENS` tokens straight to `vllm-0` and divides by the
median time-to-first-token, the same method llm-d's
[calibration recipe](https://github.com/llm-d/llm-d/tree/main/guides/recipes/router/calibration)
uses. Set `PEAK_PREFILL_THROUGHPUT` in `.env` to reuse a value you measured
earlier.

## Versions

| Component | Image |
| --- | --- |
| vLLM | `docker.io/vllm/vllm-openai:v0.30.0` |
| llm-d router (EPP) | `ghcr.io/llm-d/llm-d-router-endpoint-picker:v1.0.0` |
| Envoy | `docker.io/envoyproxy/envoy:distroless-v1.33.2` |
| Valkey | `docker.io/valkey/valkey:9.0.7` |
| inference-perf | `quay.io/inference-perf/inference-perf:v0.7.0` (amd64 only) |

## Limits

- One router replica. llm-d's precise routing guide also runs a single
  replica, because its in-flight load accounting is local to each process.
- Valkey runs as a single node without authentication, on a private Docker
  network.
- vLLM runs with `VLLM_SERVER_DEV_MODE=1` so the script can reset prefix
  caches between strategies. That exposes extra admin endpoints, which are
  reachable only on the benchmark's Docker network.
