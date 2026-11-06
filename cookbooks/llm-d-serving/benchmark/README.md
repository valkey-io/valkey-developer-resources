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

We ran this benchmark on an AWS `g6e.12xlarge` (4x NVIDIA L40S, 48 GB each)
in `ap-northeast-1`, provisioned with the Terraform in
[`terraform/aws/`](terraform/aws/), on 2026-10-29, with the default model
(Qwen3-8B) and 4,096-token shared prompts. Each vLLM replica had 165,248
tokens of KV cache, about 661k across the four. Read the caveats below
before quoting these numbers.

### Many prefixes competing for cache

192 shared system prompts of 4,096 tokens each, four users per prompt, a
256-token question and 64 output tokens. The shared prefixes add up to about
786k tokens, 1.2 times what the four replicas can cache between them, so
every strategy has to evict. 384 warm-up requests, then 768 requests at each
concurrency level.

| Strategy | Concurrency | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Prompt tokens from cache | Requests/s |
| --- | --- | --- | --- | --- | --- | --- |
| random | 8 | 409 | 716 | 1,086 | 14% | 3.22 |
| approximate | 8 | 367 | 422 | 449 | 47% | 3.90 |
| precise-memory | 8 | 132 | 434 | 456 | 65% | 4.03 |
| precise-valkey | 8 | 133 | 435 | 463 | 65% | 4.02 |
| random | 16 | 418 | 782 | 1,532 | 16% | 4.99 |
| approximate | 16 | 395 | 435 | 767 | 46% | 6.30 |
| precise-memory | 16 | 149 | 450 | 553 | 65% | 6.78 |
| precise-valkey | 16 | 147 | 447 | 524 | 64% | 6.80 |
| random | 32 | 466 | 1,420 | 2,755 | 14% | 6.64 |
| approximate | 32 | 405 | 452 | 1,636 | 48% | 9.40 |
| precise-memory | 32 | 241 | 497 | 1,398 | 65% | 10.59 |
| precise-valkey | 32 | 224 | 466 | 1,375 | 64% | 10.58 |

What this shows:

- Precise prefix-cache routing reused 64-65% of prompt tokens from cache,
  against 46-48% for the approximate scorer and 14-16% for random routing.
- At concurrency 8 and 16 it cut median time-to-first-token by 62-64%
  compared with the approximate scorer, and by 64-68% compared with random.
  At concurrency 32 the cut was 41-45% against approximate.
- At concurrency 32, precise routing served 1.6 times the requests per second
  of random routing, and 13% more than the approximate scorer.
- For the prefix-aware strategies, the p90 is close to a full 4,352-token
  prefill (about 380 ms at the calibrated rate): the slowest tenth of their
  requests are cache misses.
- Keeping the index in Valkey instead of the router's memory made no
  measurable difference: the two precise rows are within noise of each other.
  After the `precise-valkey` run, Valkey held 20,976 index keys written from
  vLLM's KV-cache events; after the other strategies it held none.

### Every prefix fits in cache

40 shared system prompts of 4,096 tokens, eight users per prompt, same
question and output lengths. The shared prefixes total about 164k tokens, a
quarter of the replicas' combined cache. 96 warm-up requests, then 768
requests at each concurrency level.

| Strategy | Concurrency | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Prompt tokens from cache | Requests/s |
| --- | --- | --- | --- | --- | --- | --- |
| random | 8 | 108 | 404 | 537 | 78% | 4.29 |
| approximate | 8 | 94 | 114 | 140 | 97% | 4.72 |
| random | 16 | 114 | 412 | 498 | 82% | 7.62 |
| approximate | 16 | 100 | 132 | 228 | 99% | 8.24 |
| random | 32 | 126 | 417 | 744 | 82% | 12.53 |
| approximate | 32 | 106 | 128 | 188 | 99% | 15.77 |

With this little cache pressure, random routing already hits the cache for
most tokens, and the approximate scorer nearly always does: 97-99% of prompt
tokens, with a p90 of about 130 ms against random's 410 ms. Precise routing
has little left to win here. We leave its rows out because this run predates
the replica restart described under [Caveats](#caveats), and its precise
results were affected by replay churn.

### Also run on older GPUs (4x T4)

Before the L40S run we ran a smaller version on an AWS `g4dn.12xlarge` (4x
NVIDIA T4, 16 GB each) in `ca-central-1`, on 2026-10-28, when no newer GPU
had capacity. The T4 can't use FlashAttention, so vLLM falls back to a slower
attention kernel and prefill is about 38 times slower than on the L40S. It
needed a smaller model (Qwen3-4B in fp16) and 1,024-token prefixes.

With more prefixes than the replicas could cache (128 x 1,024 tokens against
about 120k tokens of combined cache), at concurrency 16:

| Strategy | TTFT p50 ms | Prompt tokens from cache | Requests/s |
| --- | --- | --- | --- |
| random | 1,461 | 11% | 2.82 |
| approximate | 940 | 38% | 5.14 |
| precise-memory | 897 | 57% | 6.25 |
| precise-valkey | 847 | 58% | 6.37 |

The ordering matches the L40S: precise routing reuses the most, the two
index backends tie, and random trails. When every prefix fit (32 x 1,024
tokens), approximate and precise routing tied at 94% of prompt tokens from
cache. These runs predate the replica restart, and we didn't check them for
replay churn. The full T4 tables and settings are in this file's history.

### Why use Valkey if it isn't faster?

In every run, `precise-valkey` and `precise-memory` are within noise of each
other. Each request does a few small index lookups.
Against a Valkey on the same host those take well under a millisecond, while
time-to-first-token is around a hundred milliseconds or more even on the
L40S. A Valkey on another
host or in another availability zone would add a network round trip to each
lookup; we haven't measured that.

What Valkey changes is where the index lives: outside the router process.

- **Router restarts and upgrades.** An in-memory index starts empty when the
  router restarts, and can only rebuild from vLLM's limited event replay buffer
  and from new events. Until it does, routing is close to random. A Valkey index
  is still there. llm-d's precise routing guide names this gap: a router that
  starts after the model servers have warmed up misses the prefixes they cached
  before its replay window.
- **More than one router.** A new or replacement router reads the complete
  index from Valkey instead of building its own. That handles the index part of running several routers. llm-d still recommends a single router for precise
  routing, because its in-flight load accounting is per process.
- **One copy, visible.** The index is stored once instead of once per router,
  and you can inspect it directly, as the recipe notebook does.

This benchmark runs one router per strategy against freshly restarted
replicas, so it doesn't measure any of these. One caveat from our runs: with llm-d-router v1.0.0, a router
that joined busy replicas mid-stream degraded precise routing with either
backend (see [Caveats](#caveats)), so a Valkey index didn't protect against
that case.

### How these numbers were produced

The L40S runs use the defaults for the model and prompt shape, with a larger
workload sized to the L40S's cache:

```bash
NUM_PREFIXES=192 PROMPTS_PER_PREFIX=4 \
WARMUP_REQUESTS=384 STAGE_REQUESTS=768 CONCURRENCY_LEVELS="8 16 32" \
sudo -E ./scripts/run-benchmark.sh
```

For the second workload, change `NUM_PREFIXES=40 PROMPTS_PER_PREFIX=8
WARMUP_REQUESTS=96`. The calibration step measured
`peakPrefillThroughput` at 11,471 tokens/s (an 8,192-token prefill took 0.71
seconds). The `random` rows in the first table come from an earlier run of the
same workload without replica restarts; random routing doesn't use KV-cache
events, so the restart doesn't affect it.

For the T4 runs:

```bash
MODEL=Qwen/Qwen3-4B DTYPE=half MAX_MODEL_LEN=10240 \
SYSTEM_PROMPT_LEN=1024 QUESTION_LEN=128 OUTPUT_LEN=16 \
NUM_PREFIXES=128 PROMPTS_PER_PREFIX=4 \
WARMUP_REQUESTS=256 STAGE_REQUESTS=384 CONCURRENCY_LEVELS="8 16" \
PEAK_PREFILL_THROUGHPUT=299 \
sudo -E ./scripts/run-benchmark.sh
```

### Caveats

- **Replay churn without replica restarts.** Our first L40S runs kept the
  vLLM replicas up across strategies and only restarted the router. Each new
  router joined the replicas' KV-event streams mid-stream and asked for a full
  replay, which vLLM's replay buffer could no longer serve. The incomplete
  replays kept resetting index entries. On the first workload, precise
  routing's share of prompt tokens from cache swung between 24% and 63% from
  run to run, tracking the number of replays rather than the index backend. `run-benchmark.sh` now restarts the
  replicas before each strategy (`RESTART_REPLICAS=1`), and the precise rows
  in the first table come from that run, with no mid-stream joins or
  incomplete replays in the router logs. A production router that restarts
  against busy replicas could see the same churn.
- **One GPU type each, and not the one the defaults target.** The defaults are
  sized for 24 GB GPUs such as the L4. We used L40S and T4 because no L4 had
  capacity: when we tried, AWS had no on-demand capacity for `g6.12xlarge`
  (4x L4) in `us-east-1`, `us-east-2`, `us-west-2`, `ca-central-1`,
  `eu-central-1` or `ap-northeast-1`, apart from one zone that filled again
  within a minute.
- **One run each.** Each row is a single run of 768 requests (384 on the T4),
  without repeats or confidence intervals. Treat differences under about 10%
  as noise.
- **One router.** Each run uses a single router replica, as llm-d's precise
  routing guide does. It doesn't measure what a Valkey index is for: sharing
  one index across router replicas and keeping it through a router restart.
- **Same workload, cold start.** Every strategy saw the same prompts in the
  same order (fixed seed), and started with empty prefix caches and an empty
  index. Warm-up requests are excluded from the tables.
- **"Prompt tokens from cache"** is vLLM's own count of cached prompt tokens,
  as reported per response and summed by inference-perf.
- Three measured requests failed across the L40S runs; the one we inspected
  was an HTTP 503 from the router path. inference-perf also flagged a few requests where its count
  of output tokens differed from vLLM's; that affects output-token statistics
  only, not time-to-first-token.

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
