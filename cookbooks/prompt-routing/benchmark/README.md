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

We ran this benchmark on an AWS `g4dn.12xlarge` (4x NVIDIA T4, 16 GB each)
in `ca-central-1`, provisioned with the Terraform in
[`terraform/aws/`](terraform/aws/), on 2026-10-28. Read the caveats below
before quoting these numbers.

### Many prefixes competing for cache

128 shared system prompts of 1,024 tokens each, four users per prompt, a
128-token question and 16 output tokens. The shared prefixes add up to about
131k tokens, more than the four replicas can cache between them (about 120k),
so every strategy has to evict. 256 warm-up requests, then 384 requests at
each concurrency level.

| Strategy | Concurrency | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Prompt tokens from cache | Requests/s |
| --- | --- | --- | --- | --- | --- | --- |
| random | 8 | 916 | 2,411 | 3,331 | 14% | 2.83 |
| approximate | 8 | 842 | 1,048 | 1,619 | 40% | 4.25 |
| precise-memory | 8 | 585 | 968 | 1,348 | 58% | 4.75 |
| precise-valkey | 8 | 577 | 977 | 1,337 | 58% | 4.75 |
| random | 16 | 1,461 | 4,554 | 9,095 | 11% | 2.82 |
| approximate | 16 | 940 | 1,408 | 2,096 | 38% | 5.14 |
| precise-memory | 16 | 897 | 1,205 | 2,060 | 57% | 6.25 |
| precise-valkey | 16 | 847 | 1,152 | 1,718 | 58% | 6.37 |

What this shows:

- Precise prefix-cache routing reused 58% of prompt tokens from cache,
  against 40% for the approximate scorer and 11-14% for random routing. At
  concurrency 8 it cut median time-to-first-token by 31% compared
  with the approximate scorer, and by about 37% compared with random.
- At concurrency 16, precise routing served 2.3 times the requests per second
  of random routing, and about 24% more than the approximate scorer.
- Keeping the index in Valkey instead of the router's memory made no
  measurable difference here: the two precise rows are within run-to-run
  noise of each other. After the `precise-valkey` run, Valkey held 5,312
  index keys written from vLLM's KV-cache events; after the other strategies
  it held none.

### Every prefix fits in cache

32 shared system prompts of 1,024 tokens, eight users per prompt, same
question and output lengths. The shared prefixes total about 33k tokens,
which fits in the replicas' combined cache with plenty to spare. 64 warm-up
requests, then 384 requests at each concurrency level.

| Strategy | Concurrency | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Prompt tokens from cache | Requests/s |
| --- | --- | --- | --- | --- | --- | --- |
| random | 4 | 261 | 933 | 1,565 | 62% | 3.07 |
| approximate | 4 | 183 | 265 | 810 | 91% | 4.47 |
| precise-memory | 4 | 195 | 279 | 833 | 91% | 4.32 |
| precise-valkey | 4 | 198 | 279 | 825 | 91% | 4.30 |
| random | 8 | 363 | 1,130 | 3,758 | 67% | 4.64 |
| approximate | 8 | 199 | 267 | 323 | 94% | 8.09 |
| precise-memory | 8 | 207 | 293 | 393 | 94% | 7.71 |
| precise-valkey | 8 | 206 | 286 | 353 | 94% | 7.75 |
| random | 16 | 897 | 1,846 | 3,053 | 64% | 5.89 |
| approximate | 16 | 234 | 348 | 454 | 94% | 12.60 |
| precise-memory | 16 | 249 | 361 | 613 | 94% | 12.10 |
| precise-valkey | 16 | 247 | 375 | 473 | 94% | 11.98 |

Any prefix-aware routing beats random here: at concurrency 16, median
time-to-first-token drops from 897 ms to under 250 ms and throughput roughly
doubles. But with this little cache pressure, the approximate scorer matches
precise routing and even comes out slightly ahead, though within noise. Precise routing
pays off when caches are under pressure and evicting, as in the first
workload, because it routes on what vLLM actually holds rather than on what
the router has sent where. Valkey held 3,960 index keys after the
`precise-valkey` run and again added no measurable latency.

### Why use Valkey if it isn't faster?

In both workloads, `precise-valkey` and `precise-memory` are within noise of
each other. Each request does a few small index lookups, and against a Valkey
on the same host those take well under a millisecond, while time-to-first-token
on these GPUs is hundreds of milliseconds. Two things would make the overhead look larger outside this
setup: faster GPUs shrink
time-to-first-token, and a Valkey on another host or in another availability
zone adds a network round trip to each lookup. We haven't measured either.

What Valkey changes is where the index lives: outside the router process.

- **Router restarts and upgrades.** An in-memory index starts empty when the
  router restarts, and can only rebuild from vLLM's limited event replay buffer
  and from new events. Until it does, routing is close to random. A Valkey index
  is still there. llm-d's precise routing guide names this gap: a router that
  starts after the model servers have warmed up misses the prefixes they cached
  before its replay window.
- **More than one router.** A new or replacement router reads the complete
  index from Valkey instead of building its own. This covers the index side of
  running several routers. llm-d still recommends a single router for precise
  routing, because its in-flight load accounting is per process.
- **One copy, visible.** The index is stored once instead of once per router,
  and you can inspect it directly, as the recipe notebook does.

This benchmark runs one router that never restarts, so it doesn't measure any
of these. A run that restarts the router partway
through would show the difference.

### How these numbers were produced

The T4 settings differ from the defaults, which are sized for 24 GB GPUs:

```bash
MODEL=Qwen/Qwen3-4B DTYPE=half MAX_MODEL_LEN=10240 \
SYSTEM_PROMPT_LEN=1024 QUESTION_LEN=128 OUTPUT_LEN=16 \
NUM_PREFIXES=128 PROMPTS_PER_PREFIX=4 \
WARMUP_REQUESTS=256 STAGE_REQUESTS=384 CONCURRENCY_LEVELS="8 16" \
PEAK_PREFILL_THROUGHPUT=299 \
sudo -E ./scripts/run-benchmark.sh
```

For the second workload, change `NUM_PREFIXES=32 PROMPTS_PER_PREFIX=8
WARMUP_REQUESTS=64 CONCURRENCY_LEVELS="4 8 16"`.

`PEAK_PREFILL_THROUGHPUT=299` is the value the script's calibration step
measured on this host (an 8,192-token prefill took 27.4 seconds).

### Caveats

- **Old GPUs.** The T4 is too old for FlashAttention (it needs compute
  capability 8.0; the T4 is 7.5), so vLLM falls back to a slower Triton
  attention kernel. Absolute latencies are far higher than on current GPUs.
  Compare strategies with each other, not with other published numbers. We
  used T4s because no newer GPU was available: on-demand capacity for
  `g6.12xlarge` (4x L4), and for every other 4-GPU G instance we tried, ran
  out in every zone of the US and Canadian regions we checked that day.
- **Small model and short prefixes.** Qwen3-4B in fp16 leaves each 16 GB GPU
  about 30k tokens of KV cache, so the shared prefixes are 1,024 tokens rather
  than the 4,096 the defaults use. Longer prefixes make each cache hit worth
  more, so we'd expect a larger gap on bigger GPUs, but we haven't measured it.
- **One run each.** Each row is a single run of 384 requests, without repeats
  or confidence intervals. Treat differences under about 10% as noise.
- **One router.** The run uses a single router replica, as llm-d's precise
  routing guide does. It doesn't measure what a Valkey index is for: sharing
  one index across router replicas and keeping it through a router restart.
- **Same workload, cold start.** Every strategy saw the same prompts in the
  same order (fixed seed), and started with empty prefix caches and an empty
  index. Warm-up requests are excluded from the tables.
- **"Prompt tokens from cache"** is vLLM's own count of cached prompt tokens,
  as reported per response and summed by inference-perf.
- inference-perf flagged a few requests where its count of output tokens
  differed from vLLM's. That affects output-token statistics only, not
  time-to-first-token.

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

- A Linux host with four NVIDIA GPUs. The defaults are sized for 24 GB GPUs
  such as an AWS `g6.12xlarge` (4x L4). 16 GB GPUs work with a smaller model
  and shorter prefixes; [the results above](#how-these-numbers-were-produced)
  list the settings we used on 4x T4.
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
