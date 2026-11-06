# GPU benchmark for the llm-d serving recipe

> Optional and GPU-only. The [recipe notebook](../llm-d-serving-with-valkey.ipynb)
> runs on CPU and is the main path; you don't need this benchmark to follow it.

The notebook shows how the stack works: Valkey holds the router's
prefix-cache index and the KV cache that LMCache shares between vLLM
replicas. On CPU, loading KV from Valkey costs about as much as a local hit,
so the timing differences between routing strategies are small. This
benchmark runs the same stack on four GPUs, where prefill is expensive, and
measures first-token time, throughput, and where the cached prompt tokens
came from.

It is the same wiring as the recipe's [`docker-compose.yml`](../docker-compose.yml),
scaled up: four vLLM replicas with `LMCacheMPConnector`, a standalone LMCache
server whose store is Valkey, and llm-d's router (Envoy and the Endpoint
Picker v1.0.0) with its index in Valkey database 1. No Kubernetes is
involved; the router reads its list of replicas from a file, following
llm-d's [no-Kubernetes deployment guide](https://github.com/llm-d/llm-d/tree/main/guides/no-kubernetes-deployment).

## Results

No results have been published for this stack yet. Each published result
will state the cloud, instance type, GPU, region and date it was measured
on; `summarize.py` prints that line above every table.

A note on what to expect. An earlier version of this benchmark
([#107](https://github.com/valkey-io/valkey-developer-resources/pull/107))
had no shared KV cache, and there precise routing's first-token times were
well below random routing's. Here, a request that random routing sends to
the wrong replica can still load the prefix from Valkey instead of
recomputing it, so the gap between random and precise routing may be
smaller. The `random-no-lmcache` baseline shows the combined effect
of routing and the shared cache. The benchmark reports whatever it measures.

## What it compares

`scripts/run-benchmark.sh` runs the same workload for each configuration,
three times each (`RUNS`):

| Configuration | Router | KV sharing |
| --- | --- | --- |
| `random-no-lmcache` | At random | None. Replicas run without `--kv-transfer-config`, so a miss in a replica's GPU prefix cache is a full prefill. |
| `random` | At random | LMCache and Valkey |
| `approximate` | llm-d's default prefix-aware scorers, which estimate cache contents from the requests they've routed. No KV events, no index. | LMCache and Valkey |
| `precise-memory` | Precise prefix-cache routing from vLLM's KV events, index in the router's memory | LMCache and Valkey |
| `precise-valkey` | The same, index in Valkey database 1 | LMCache and Valkey |

All five use the same Envoy and router path; only the router config (and,
for the baseline, the replicas' KV connector) changes. The router configs
are in [`epp/`](epp/); `random` and `random-no-lmcache` share
`epp/random.yaml`.

Before every run the script stops the router and the replicas, restarts the
LMCache server (empty L1), flushes Valkey database 0 (the KV store) and
resets Valkey's error counters, then recreates the replicas, so each run
starts with empty GPU prefix caches and an empty KV store. It also flushes
database 1, the router's index, while the router is stopped, so
`precise-valkey` starts each run with an empty index, as `precise-memory`
does. Set `FLUSH_ROUTER_INDEX=0` to keep it. The index's key count at the
start of each run is recorded in `valkey-before.json`.

## What you need

- A Linux host with four NVIDIA GPUs, 24 GB or more each. The defaults are
  sized for 48 GB GPUs such as the L40S; see [Workload](#workload) for
  smaller ones.
- Host RAM for Valkey's `maxmemory` plus the replicas and the LMCache
  server: 344 GiB with the defaults (see [Sizing Valkey](#sizing-valkey)).
  The script refuses to start on a host with less.
- Docker with the Compose plugin, the NVIDIA Container Toolkit, and
  `python3` on the host.
- About 150 GB of free disk for images, model weights and logs.
- Outbound internet access to pull images, Python packages and the model.
  The default model, `Qwen/Qwen3-8B`, is ungated, so no Hugging Face token
  is needed.

To get such a host on AWS, see the optional [`terraform/aws/`](terraform/aws/).
Any other host that meets the list above works the same way.

## Run it

```bash
cd cookbooks/llm-d-serving/benchmark
cp .env.example .env
./scripts/run-benchmark.sh
```

Edit `.env` first to set `BENCH_CLOUD`, `BENCH_INSTANCE_TYPE` and
`BENCH_REGION` (they go into `metadata.json` and above every results table)
or to change the model or workload. If your user is not in the `docker`
group, run the script with `sudo`; settings in `.env` still apply.

The first run builds the vLLM image (the pinned `vllm/vllm-openai:v0.30.0`
plus lmcache 0.5.5 and `valkey-glide-sync` 2.5.2, see
[`vllm/Dockerfile`](vllm/Dockerfile)), downloads about 16 GB of weights, and
waits a few minutes for the replicas to start. Each run then recreates the
replicas and sends 2,688 requests. With five configurations, three runs
each and the default workload, plan for several hours.

Stop everything afterwards with `docker compose down`.

## Results layout

```text
results/<run-id>/
  metadata.json             where, when and with what the run was measured
  summary.md, summary.json  the results tables, and the numbers behind them
  vllm-0.log, lmcache-server.log   startup logs (KV cache size, transfer mode)
  <configuration>/run-<n>/
    warmup/                 inference-perf report for the warm-up stage
    c8/, c16/, c32/         inference-perf report for each concurrency level,
                            plus counters-before.json and counters-after.json
    valkey-before.json      Valkey memory and key counts when the run started
    valkey.json, valkey.txt Valkey INFO memory, keyspace and errorstats after the run
    epp.log, lmcache-server.log, vllm-<n>.log
```

`metadata.json` records the date (UTC), `BENCH_CLOUD`, `BENCH_INSTANCE_TYPE`
and `BENCH_REGION`, the GPU model, count, memory and driver from
`nvidia-smi`, host RAM, the image each container ran (from `docker
inspect`), the lmcache, `valkey-glide-sync` and vLLM versions inside the
containers, the package changes the image build made, the model, the
workload and stack settings, and the git commit of this repository.

`summary.md` has one row per configuration and concurrency level:

- TTFT p50, p90 and p99, and requests per second, from inference-perf.
- Prompt tokens from the GPU prefix cache and from Valkey, as shares of all
  prompt tokens. These come from vLLM's counters on every replica, read
  just before and just after each stage: `vllm:prefix_cache_hits_total`
  (local hits), `vllm:external_prefix_cache_hits_total` (tokens LMCache
  supplied, which it reads from Valkey) and `vllm:prompt_tokens_total`. The
  recipe notebook tells local hits from Valkey hits with the same two
  counters.
- Failed requests, summed over the runs.

Each cell is the median of the runs, with the spread (minimum to maximum) in
brackets. A second table lists Valkey's `used_memory`, `used_memory_peak`,
key counts per database and OOM rejections for every run. Rerun
`python3 scripts/summarize.py results/<run-id>` at any time to print the
tables again.

## How it's wired

```text
loadgen (inference-perf)
   |
   v
envoy :8081  --ext_proc-->  EPP (router)  --index, db 1-->  valkey
   |                          ^                               ^
   |                          | KV events (ZMQ :5556, :5559)  | KV chunks, db 0
   v                          |                               |
vllm-0 .. vllm-3  ------------+-------- LMCacheMPConnector --> lmcache-server
```

| File | Purpose |
| --- | --- |
| `compose.yaml` | All services on one bridge network with fixed addresses |
| `vllm/Dockerfile`, `vllm/install-lmcache.sh` | The vLLM image with lmcache 0.5.5 and `valkey-glide-sync` 2.5.2 |
| `vllm/serve-vllm.sh` | vLLM flags: block size 64, prefix caching, KV events, render endpoints, the LMCache connector (or none) |
| `epp/*.yaml` | Router config for each strategy, plus `endpoints.yaml` for file discovery |
| `envoy/envoy.yaml` | Envoy config, copied from llm-d's no-Kubernetes guide |
| `loadgen/shared-prefix.yaml` | inference-perf workload template |
| `scripts/run-benchmark.sh` | Runs everything, one configuration and run at a time |
| `scripts/benchctl.py` | Calibration, router readiness, counter snapshots, Valkey stats, the host RAM check |
| `scripts/render.py`, `scripts/summarize.py`, `scripts/metadata.py` | Config templating, the results tables, and `metadata.json` |

Block and chunk sizes line up the way the CPU stack's do. vLLM's
`--block-size 64` equals the router's `blockSizeTokens`, because the router
recomputes vLLM's block hashes from the prompt tokens. LMCache stores KV in
256-token chunks, four vLLM blocks each, and the connector checks at
startup that the chunk size is a whole number of blocks. The default
4,096-token system prompts are exactly 16 chunks.

On GPUs, LMCache's `auto` transfer mode resolves to `lmcache_driven`: the
LMCache server maps each replica's KV cache through CUDA IPC handles and
copies chunks with its own kernels. That is why the LMCache server runs from
the same image, gets all four GPUs, and shares the host IPC namespace
(`ipc: host`) with the replicas. If CUDA IPC between the containers fails,
set `LMCACHE_MP_TRANSFER_MODE=engine_driven` in `.env`: the replicas then
send KV to the server themselves, and the server's default (`auto`) accepts
both modes.

### LMCache policy

The CPU stack runs the LMCache server with `skip_l1`, which drops each
chunk from the server's L1 memory once it is in Valkey, so every load comes
from Valkey. This benchmark doesn't, for a reason measured on the first GPU
runs. In lmcache 0.5.5, each lookup asks for the whole prompt, including the
part vLLM already holds in its GPU prefix cache, and the server copies every
chunk it finds into L1 before the request is scheduled. Under `skip_l1` that
copy always came from Valkey: about 576 MiB, taking 230-370 ms, on every
request, even when vLLM then used almost none of it. Median first-token time
at concurrency 8 was about 500 ms for precise routing, against 123 ms
without LMCache. LMCache fixed this after 0.5.6
([LMCache/LMCache#5383](https://github.com/LMCache/LMCache/pull/5383)).

So L1 is a cache here: chunks stay in host memory (`LRU` eviction) and are
also stored to Valkey, which is the shared tier behind it. L1 defaults to
64 GB (`LMCACHE_L1_SIZE_GB`), about half of the default workload's KV, so
many lookups still have to load from Valkey. The summary reports, for each
run, how many chunks lookups found in L1 and how many they loaded from
Valkey. To measure the CPU stack's policy instead, set
`LMCACHE_L2_STORE_POLICY=skip_l1` and `LMCACHE_EVICTION_POLICY=noop`.

### Workload

192 shared system prompts of 4,096 tokens, four users per prompt, a
256-token question and 64 output tokens: the "many prefixes competing for
cache" workload from #107. The shared prefixes add up to 786,432 tokens,
more than four 48 GB replicas can keep in GPU memory, so every strategy has
to evict. Each run sends 384 warm-up requests at the first concurrency
level, then 768 requests at each of 8, 16 and 32 concurrent users. The seed
is fixed, so every configuration and run sees the same prompts.

Each stage is a separate inference-perf run, so the counters can be read
between stages. The caches are not flushed between stages of one run.

If you change the model or GPU, check the `GPU KV cache size` line in
`results/<run-id>/vllm-0.log` and adjust `NUM_PREFIXES` or
`SYSTEM_PROMPT_LEN` so the shared prefixes still don't fit in the replicas'
combined GPU cache. Keep `SYSTEM_PROMPT_LEN` a multiple of 256.

### Calibration

The precise strategies estimate each replica's prefill time from
`peakPrefillThroughput`, which depends on the model and GPU. The script
measures it once, before the first run: it sends random-token prompts of
`MAX_NUM_BATCHED_TOKENS` tokens straight to `vllm-0` (with LMCache on) and
divides by the median first-token time, the method llm-d's
[calibration recipe](https://github.com/llm-d/llm-d/tree/main/guides/recipes/router/calibration)
uses. Set `PEAK_PREFILL_THROUGHPUT` in `.env` to reuse a value you measured
earlier.

The router configs keep llm-d's GPU defaults for everything else. The CPU
stack's overrides (`addEstimatedOutputTokens`, `peakPrefillThroughput:
1000`, `maxTTFTPenaltyMs: 1500`) are tuned for small CPU replicas and are
not used here.

## Sizing Valkey

Valkey holds every KV chunk LMCache stores during a run, so its `maxmemory`
and the host's RAM have to be planned for the workload.

- KV per token for Qwen3-8B: 36 layers × 8 KV heads × 128 head dim × 2 (K
  and V) × 2 bytes = 147,456 bytes, or 144 KiB.
- LMCache stores whole 256-token chunks, so one chunk is 36 MiB. Valkey's
  allocator rounds an allocation of that size up to 40 MiB, which is what
  `used_memory` counts.
- Shared prefixes: 192 × 4,096 tokens = 786,432 tokens = 3,072 chunks.
- Questions: each of the 768 distinct prompts (192 × 4) adds one more full
  chunk, tokens 4,096 to 4,351: 768 chunks. The rest of a prompt and its
  output tokens don't fill another chunk and are not stored.
- Total: 3,840 chunks × 40 MiB = 150 GiB per run (135 GiB of KV data).

The default `VALKEY_MAXMEMORY` is `192gb`. The extra 42 GiB covers prompts
that tokenize a few tokens short of 4,352: their output tokens complete the
17th chunk, and since outputs are sampled, that chunk differs per request.
In the worst case that adds one chunk per request, up to 105 GiB, so check
`used_memory` in `valkey.json` after your first run. Valkey runs with
`noeviction`: when it is full it rejects new writes instead of evicting, and
the summary flags any run with OOM rejections. An LRU policy would evict
across all databases, the router's index in database 1 included.

For other workloads the same arithmetic applies: (prefix chunks + one
chunk per distinct prompt for the question) × the rounded chunk size of
your model, with some margin. Lower `NUM_PREFIXES` and `VALKEY_MAXMEMORY`
together to fit a smaller host.

Host RAM, as `run-benchmark.sh` checks it before starting anything:

| Item | Default |
| --- | --- |
| Valkey `maxmemory` (`VALKEY_MAXMEMORY`) | 192 GiB |
| LMCache L1 (`LMCACHE_L1_SIZE_GB`) | 64 GiB |
| LMCache server process (`LMCACHE_SERVER_HOST_RAM_GIB`) | 8 GiB |
| Four vLLM replicas (`REPLICA_HOST_RAM_GIB` each) | 4 × 16 GiB |
| OS, Docker, router, load generator (`SYSTEM_HOST_RAM_GIB`) | 16 GiB |
| Total | 344 GiB |

The last three are allowances, not measurements; adjust them in `.env` once
you have measured your host.

## Versions

| Component | Version |
| --- | --- |
| vLLM | `docker.io/vllm/vllm-openai:v0.30.0`, pinned by digest in `vllm/Dockerfile` |
| LMCache | 0.5.5, installed by `vllm/Dockerfile` |
| Valkey GLIDE (sync) | 2.5.2, used by LMCache's Valkey adapter |
| Valkey | `docker.io/valkey/valkey-bundle:9.1.2` (same as the recipe and CI) |
| llm-d router (EPP) | `ghcr.io/llm-d/llm-d-router-endpoint-picker:v1.0.0`, pinned by digest |
| Envoy | `docker.io/envoyproxy/envoy:distroless-v1.33.2`, pinned by digest |
| inference-perf | `quay.io/inference-perf/inference-perf:v0.7.0`, pinned by digest (amd64 only) |

## Limits

- One router replica. llm-d's precise routing guide also runs one, because
  its in-flight load accounting is local to each process. The benchmark
  doesn't measure what a Valkey index adds for several routers or across a
  router restart.
- LMCache doesn't report what it stores back to the router
  (`LMCacheMPConnector` emits no KV events), so the precise strategies route
  on what is in each replica's GPU cache, not on what is in Valkey.
- Valkey runs as a single node without authentication, on a private Docker
  network, with persistence off.
- Each stage runs as its own inference-perf process, so the warm-up and the
  first measured stage start at the same point in the prompt order. Results
  aren't directly comparable with #107's, which ran all stages in one
  process and had no shared KV cache.

## AWS host (optional, AWS-specific)

[`terraform/aws/`](terraform/aws/) creates one GPU instance on AWS
(`g6e.12xlarge` by default: 4x L40S 48 GB, 384 GiB RAM), reachable only
through SSM Session Manager, and writes `BENCH_CLOUD`, `BENCH_INSTANCE_TYPE`
and `BENCH_REGION` for the benchmark from instance metadata. It is one way
to get a host; nothing else in this directory depends on AWS.
