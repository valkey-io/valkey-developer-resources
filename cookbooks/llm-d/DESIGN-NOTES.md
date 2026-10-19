# llm-d + Valkey cookbook — design notes (DRAFT / brainstorm)

> Scratch doc on `llm-d-cookbook-draft`. This is a fork taken before the real
> story/request landed — likely to change or be thrown away. Persisted so the
> research below doesn't have to be redone. **Nothing here is committed to a
> shape yet.** Scope is the **llm-d** item only; the Alibaba Tair KVCache item is
> explicitly out of scope.

## The core question (unresolved)

What does the cookbook actually *show*, and does a notebook make sense?

The worry: "getting llm-d to run with Valkey = point a Valkey URL at an
instance", which would be a config note, not a notebook. **Research below says
it's more than a URL** — there is a real, non-trivial Valkey data-structure
protocol in `llm-d-async`. So there is a genuine story to tell. The open
question is *how to show it* (see "A vs B vs C"), which the incoming
story/request should settle.

## Where the integration actually lives (verified in the clones)

Repos cloned locally:
- `/Users/matthowt/GITWorkspace/improving/llm-d` — the main k8s inference stack.
  Only **documents** the batch/async + Valkey story (`docs/architecture/batch/*`,
  `docs/operations/components/async-processor.md`). No Valkey code here.
- `/Users/matthowt/GITWorkspace/improving/llm-d-async` — the async/batch
  component. **This is where all the Valkey code is.**

So: **llm-d-async is the integration; llm-d is the surrounding context.**

### Client library
- `github.com/redis/go-redis/v9` (Go). RESP / Valkey-compatible.
- Tests use `github.com/alicebob/miniredis/v2` plus a real Redis/Valkey.

### The two integration points (your two bullets), confirmed

1. **Request queue — a sorted set + Lua.** `producer/redis_sortedset_producer.go`.
   - Requests live in a **ZSET** scored by `priority + monotonic-seq/2^21`
     (an `INCR` sequence gives FIFO *within* a priority band).
   - Enqueue is a **Lua script** (`submitRequestScript`): `INCR` seq →
     `EXPIREAT` → `SET` a per-request marker with `PX` TTL → `ZADD` the queue
     member → optional payload `SET`.
   - **Cluster-mode variant** (`enqueueRequestScript`) uses **hash-tagged keys**
     so each script stays within one Valkey Cluster slot — a good
     cluster-correctness teaching point.
2. **Quota / admission gate — also a sorted set.** `sortedset_quota_gate_test.go`,
   `redis_dispatch_gate_test.go`, `pool_gate_test.go`. Admission decisions are
   backed by a ZSET (sliding-window / deadline-view style), not a plain counter.

### Result delivery (a third, richer piece)
`producer/redis_result_delivery.go` — a Lua `receiveResultScript` implementing
**at-least-once** delivery over a **list + two hashes + a ZSET index**:
- `:result` list (FIFO, legacy `RPUSH`/`RPOP` direction preserved),
- `:result-claimed` / `:result-claim-owners` hashes,
- `:result-claims-idx` ZSET for claim expiry.
The script **requeues expired claims, skips acknowledged duplicates, and
atomically moves the oldest pending result into route-local claim state**.
Claim lease TTL + reclaim interval → survives worker death. This is the most
"notebook-worthy" single artifact: a real distributed-queue reclaim protocol.

### Other Valkey-backed details seen
- Cancellation markers (`SET` with `cancellationMarkerTTL = 7d`).
- Payload refs with `payloadTTLGrace = 10m`.
- Deadline views (`sortedset_deadline_views_test.go`).
- `claim_expiry_loss_test.go` — correctness under lost claims.

### How they deploy the store (for the "run it" question)
`test/e2e/yaml/redis.yaml`: a single-replica Redis Deployment + Service
(NodePort 30480) in k8s, image via `${REDIS_IMAGE}`. i.e. the real stack is
**Helm/k8s**, store is a plain single node on 6379. Swapping in
`valkey/valkey-bundle` is trivial (it's RESP) — *this* is the "just a URL" part,
but it's only the deployment, not the logic.

## Question 1 — where under `cookbooks/`?

Existing buckets:
- `cookbooks/kv-caching/` — flat, top-level (LLM **serving-infra**; LMCache).
- `cookbooks/framework-integrations/<lang>/<name>/` — app frameworks
  (haystack, mem0, langchain4j, spring-ai, ...).
- `cookbooks/use-cases/<lang>/<name>/` — pattern demos (semantic-caching).

llm-d is LLM **serving infrastructure**, same neighborhood as kv-caching/LMCache
— not an app framework. **Lean: top-level `cookbooks/llm-d/`** (sibling of
`kv-caching/`). Alternative if we treat it as an integration:
`cookbooks/framework-integrations/<lang>/llm-d/` — but the code is Go, and that
bucket is split python/java with no go/, so a top-level dir avoids forcing a
language bucket. **DECISION: open — leaning top-level `cookbooks/llm-d/`.**

## Question 2 — what to call it?

- Dir `llm-d/`, title **"llm-d with Valkey"**, subtitle naming the roles:
  "Valkey as the job queue and admission store behind llm-d's async batch
  component." (pattern-second, matches kv-caching voice). **Leaning this.**
- Pattern-first alt: "Durable job queue & admission control with Valkey (llm-d)"
  — more descriptive, wordier.
- **DECISION: open — leaning dir `llm-d/`, title "llm-d with Valkey".**

## Question 3 — what's in the notebook? (depends on A/B/C)

**A — real llm-d-async stack, scaled down.** Helm/k8s (kind/minikube) + the
async component + a Valkey pod; drive batch jobs through it, point its store at
Valkey. Highest fidelity. Heavy; `.ci-structural-only`; not a 15-min laptop run.
Also it's **Go/k8s**, not a Python notebook's natural habitat.
*(User expects A will be what's requested "just because".)*

**B — the Valkey-side contract, standalone.** The notebook *is* the protocol:
re-create the sorted-set priority+seq enqueue, the quota ZSET, and the
claim/reclaim result script against a plain Valkey (`valkey/valkey-bundle` on
127.0.0.1:6379), and show them working (FIFO-within-priority, over-quota
rejection, reclaim-on-death). llm-d shown in prose/config as the consumer. Runs
anywhere, fast, genuinely illustrative of *why Valkey fits*. Fidelity caveat:
it's a faithful re-implementation, not llm-d itself driving it. **Language
tension:** the real code is Go+Lua; a Python notebook would port the Lua scripts
(the Lua is the portable part — same scripts run from any client).

**C — hybrid.** B runs live (the teachable core), plus a CI-skipped appendix
showing the real llm-d-async Helm values pointed at Valkey (A). Honest about
"here's the contract" + "here's how the real stack consumes it".

**Recommendation: C (B-spine + A-appendix).** Only path that clears the repo's
"runs end-to-end locally" bar while staying honest that real llm-d is k8s/Go.
But **defer to the incoming story/request** — if A is explicitly requested,
it's a Go/k8s cookbook (new territory for this repo; no `go` cookbook exists
yet) and the notebook premise itself is in question.

## Open issues to resolve when the real request lands
1. A vs B vs C — the whole shape hinges on this.
2. Language: Go (match the source) vs Python (match the notebook convention /
   the only existing cookbook tooling: uv, nbmake). The Lua scripts are the
   language-neutral bridge.
3. If A: this repo has **no Go cookbook pattern** and no k8s-in-CI story — that's
   net-new infra (CONTRIBUTING + CI would need a Go/k8s path, like the uv work).
4. Is the "integration" interesting enough as config alone? → No; the ZSET/Lua
   protocol is the substance. The URL is only the deployment.

## Key source files (llm-d-async) for whoever picks this up
- `producer/redis_sortedset_producer.go` — enqueue ZSET + Lua (std + cluster).
- `producer/redis_result_delivery.go` — at-least-once result claim/reclaim Lua.
- `producer/redis_conn.go` — client/connection setup.
- `test/integration/sortedset_quota_gate_test.go` — quota gate shape.
- `test/integration/redis_dispatch_gate_test.go`, `pool_gate_test.go` — gates.
- `test/integration/claim_expiry_loss_test.go` — reclaim correctness.
- `test/e2e/yaml/redis.yaml` — how the store is deployed in e2e (k8s, 6379).
- `docs/architecture/batch/*` (main `llm-d` repo) — the narrative context.

---

## UPDATE 2026-10-19 — clarification received (direction resolved)

Received a clarified request (Overview + Use Case + Acceptance Criteria). It
resolves the A/B/C fork **in favor of A** and against my earlier B/C lean.

### What the request says (the decisive language)
- "a **usage/integration guide rather than new Valkey code**"
- "Both of these work with Valkey **unchanged**"
- AC: "Guide **confirms both components work with Valkey unchanged (no Valkey
  code changes)**"
- Use case: "Batch and latency-tolerant inference jobs queued through llm-d,
  with Valkey holding the job queue and the admission quotas."

→ This **rules out B/C** (re-implementing the queue/quota/reclaim protocol in a
notebook is exactly the "new code" the request says not to write). The
deliverable is **A**: drive the *real* llm-d-async, point its store at Valkey,
and show llm-d's own queue + quota gate working **unchanged**. The star artifact
is the *evidence*, not our code.

### "Works with Valkey unchanged" — VERIFIED, and it's upstream's own claim
Config path is code-free: a single **`REDIS_URL`** (Helm injects it as a Secret
→ env; `pkg/redis/options.go` reads `REDIS_URL`; `producer/redis_conn.go` does
`redis.ParseURL`). standalone / cluster / sentinel all via the same URL.

Upstream **documents Valkey support in their own chart values**
(`charts/llm-d-async/values.yaml`, the `ap.redis` block ~lines 205–216):
- "Compatible with any Redis-protocol server including Valkey."
- "All redis.* fields work unchanged when pointed at a Valkey endpoint."
- example `url: "redis://redis-master.redis.svc.cluster.local:6379"`.
Transport is `ap.transport: redis-sortedset` with
`ap.transportConfig.urlSecret.url` (the `ap.redis.*` block is deprecated but
works). So the AC is satisfiable with upstream's words + a live run — no Valkey
or llm-d code changes.

### The one real decision left: FORMAT (notebook vs guide)
The request says "cookbook" but every AC is "demonstrates / shows / confirms" —
**none require a `.ipynb`.** And the thing being driven is Go + Helm/k8s, which
is a poor fit for a Python notebook. Options:
- **A1 — deploy-and-verify guide.** README + Helm values (`transport:
  redis-sortedset`, `urlSecret.url` → Valkey) + a verify script that watches the
  ZSET queue fill/drain and the quota gate reject over-limit, via `redis-cli`/
  `valkey-cli` against the Valkey pod while a batch job runs. Matches the Go/k8s
  reality and the "guide" language. **Leaning this.**
- **A2 — thin notebook wrapper** that shells out to `helm`/`kubectl` and inspects
  Valkey with a client. Satisfies "notebook" literally but the notebook adds
  little over a script; risks being notebook-theatre around shell commands.
- Repo-fit note: this repo has **no Go/k8s cookbook and no k8s-in-CI**. Either
  option is almost certainly **`.ci-structural-only`** (can't stand up GPU/k8s
  llm-d in CI); verification is "run it locally against kind + a Valkey pod",
  like kv-caching's "see it working" bar, not a CI e2e.

### Concrete shape (pending format pick), placement/name unchanged leanings
`cookbooks/llm-d/` ("llm-d with Valkey"), containing:
1. `README.md` — what llm-d-async is, the two integration points, the "unchanged"
   claim with the upstream values.yaml citation, prerequisites (kind/minikube or
   an existing cluster, helm), and the run/verify steps.
2. Helm values file pointing `ap.transport: redis-sortedset` at a Valkey pod.
3. A Valkey deploy manifest (swap `valkey/valkey-bundle` into their
   `test/e2e/yaml/redis.yaml` shape) OR reuse an existing Valkey.
4. A verify step: submit batch jobs → observe the `request-sortedset` ZSET and
   the quota gate in Valkey (`valkey-cli`), and the results list drain.
5. `.ci-structural-only` marker.

### Still to confirm with the requester
- **Format:** notebook vs guide (A1 vs A2). The ACs permit a guide; the repo
  convention leans notebook. **Needs a call** — flag the mismatch.
- **Published in `valkey-developer-resources`** (AC) — that's this repo
  (valkey-io/valkey-samples / "Valkey Developer Resources"). Confirm it's the
  same target and not a different repo by that literal name.
- GPU: does the batch inference path need a GPU, or can the async component +
  queue/quota be shown with a trivial/stub model so it runs on a laptop-class
  kind cluster? Determines whether "see it working" is even locally reproducible.

---

## UPDATE 2026-10-19 (b) — inference backend + "what the runner sees" (VERIFIED in source, NOT yet run)

### No Ollama / no real inference engine needed — and we don't want one
- llm-d-async is a **queue/dispatch layer**, not an engine. It forwards
  OpenAI-style requests to any HTTP `/v1/completions` endpoint.
- The e2e stack's backend is **`llm-d-inference-sim`**
  (`ghcr.io/llm-d/llm-d-inference-sim`, `--model test-model --fake-metrics`):
  a vLLM-API-compatible **simulator**, instant fake completions, GPU-free, no
  weights, no download. `cpu: 10m`, no mem limit.
- Adding Ollama would pull GBs, add nondeterministic latency, blow the 8 GB
  budget, and distract from the point. The cookbook is about **Valkey holding
  the queue + quota**, NOT about inference — the stub backend is correct *by
  design*. (Swapping the sim for Ollama/any real endpoint is a one-env-var
  optional footnote, off the critical path.)

### GPU question: ANSWERED — no GPU. The sim replaces the only GPU-hungry part.

### Memory: Tier 2 "shows everything" fits 8 GB (ESTIMATE, not measured)
Prod-shaped stack = Valkey + async-processor + EPP + InferencePool + Envoy
(512Mi, the only sizable ask) + sim (10m cpu). Drop Jaeger/Prometheus/pubsub.
kind control plane ~2–3 GB + pods ~1–1.5 GB + images/headroom → ~4–6 GB,
inside 8 GB. **Must measure peak on a real bring-up before quoting a number**
(same bar as kv-caching's 8 GiB).

### What the runner SEES — three observable layers (key names/paths from source)
1. **Valkey directly (the star).** `valkey-cli` against the Valkey pod; watch
   keys change live as jobs flow:
   - `request-sortedset` — the **job queue** (ZSET). `ZCARD` / `ZRANGE ...
     WITHSCORES` shows jobs land (priority+seq order) then drain. ← AC #1/#3.
   - `result-list` + `:result-claimed` / `:result-claim-owners` /
     `:result-claims-idx` — result delivery / claim state.
   - `request-cancel:<id>`, `request-active:<id>`,
     `request-payload:<id>:<token>` — per-request markers w/ TTLs.
   - quota-gate ZSET — fills to the limit. ← AC #2.
   (`valkey-cli monitor` or `watch 'valkey-cli ZCARD request-sortedset'`.)
2. **Request/response — quota made visible.** Over-quota requests get **429**
   (`api/inference_error.go`; `ErrCategoryRateLimit`). Submit a burst past the
   quota → some 200 (results return), some 429. ← AC #2 made visible.
3. **Metrics — the "prod" proof.** async-processor exposes Prometheus counters:
   - `async_gate_decisions_total{reason="quota_exhausted"}` — counts quota
     rejections (help text: "redis-quota in blocking mode").
   - `async_dispatched_requests_total`, `async_inflight_requests`,
     `async_successful_requests_total`, `async_queue_*`.

### The concrete "show" (reader walkthrough)
1. Stand up trimmed kind stack; store → Valkey via `REDIS_URL`.
2. Open a Valkey watch window (empty to start).
3. Submit a batch of jobs to the gateway (OpenAI-style `/v1/completions`).
4. See `request-sortedset` fill (ZRANGE shows priority ordering). ← AC #1.
5. See it drain → sim returns instant completions → `result-list` flows.
6. Burst past quota → 429s + `async_gate_decisions_total{quota_exhausted}`
   climbs. ← AC #2.
7. Show "unchanged": cite upstream `values.yaml` ("…including Valkey… all
   redis.* fields work unchanged"); only `REDIS_URL` changed. ← AC #3.

### Honest caveats
- Confirmed key names, the 429 path, and the metric **from source**; have NOT
  run the stack. Exact batch-submit `curl` through Envoy/EPP and the precise
  queue→drain→429 sequence need a live bring-up; changes may be needed.
- Backend is a **stub** by design — README must say completions are simulated;
  this demonstrates queue+quota, not inference.

---

## UPDATE 2026-10-19 (c) — does a notebook work? YES (Python, as client/driver)

The submit side is **OpenAI-compatible HTTP**, which makes a notebook viable:
- async-processor forwards to `/v1/completions` (`requestPathURL`,
  `batchSize: 10`).
- batch-gateway exposes an **OpenAI-compatible Batch API**: `POST /v1/files`,
  `POST /v1/batches`, `GET /v1/batches/{id}` (status/progress),
  `GET /v1/batches`, `POST /v1/batches/{id}/cancel`.

So the notebook's action cells are **real client code**, not kubectl theatre:
- submit with the `openai` Python client (or httpx) at the gateway;
- inspect Valkey with `valkey-py` (`zcard`/`zrange ... withscores` on
  `request-sortedset`, the result-list keys, the quota ZSET);
- poll `GET /v1/batches/{id}`; read metrics via an HTTP GET.

**Language: Python** (matches the repo's uv/nbmake tooling). llm-d-async is Go,
but the notebook is a *client* — client side is just HTTP + Valkey, both with
clean Python libs. No Go kernel.

### Key difference from kv-caching (state honestly)
- kv-caching: the notebook code *is* the system under test (LMCache+vLLM
  in-process).
- llm-d: the notebook is a **client/driver + observer** of a system running in
  kind. Legitimate notebook style, but not "the notebook is the app."

### The format that fits = hybrid (same shape kv-caching already uses)
- **README + setup script / Helm values** stand up the stack (the
  kind+helm-install equivalent of kv-caching's `docker-compose.yml`). Cluster
  lifecycle does NOT go in notebook cells — slow, stateful, not nbmake-friendly.
- **Notebook** = the re-runnable interesting part: drive jobs, watch
  `request-sortedset` fill/drain, trip the quota → 429s +
  `async_gate_decisions_total{quota_exhausted}`. This is the CI-structural piece.

### Proposed notebook chapters
0. setup/prose + a cell asserting the stack is up & port-forward reachable.
1. job queue: valkey-py shows ZSET empty → submit batch → ZSET fills (priority/
   score order) → drains → results. (AC #1/#3)
2. quota gate: burst past quota → 200s + 429s; metric counter climbs. (AC #2)
3. "unchanged": markdown citing upstream values.yaml + the one-line REDIS_URL.
   (AC #3)

### Verdict
A Python Jupyter notebook **does** work and can mirror the kv-caching
"set up, then run code that makes things happen and shows it" feel — as a client
driving kind-hosted llm-d and observing Valkey. Infra bring-up stays in
README/support files. Still pending a live bring-up to confirm the exact submit
API call and sequence.

---

## UPDATE 2026-10-19 (d) — COURSE CORRECTION: no k8s / no kind / no Homebrew.
## docker compose runs the core (like kv-caching).

Investigated whether we actually need Kubernetes before installing kind/helm/
kubectl. We do **not**. The async-processor runs standalone in a container.

### Evidence (from source)
- `cmd/main.go` is flag/env driven (`pflag`); no in-cluster config required.
- Transport = a JSON `--transport-config` (or `--transport-config-file`) + the
  `REDIS_URL` env; the sorted-set config carries `igw_base_url`,
  `request_path_url`, `request_queue_name`, and `gate_type`/`gate_params` (the
  quota gate). `pkg/redis/options.go`.
- The forward target is a **plain HTTP base URL** (`igw_base_url` +
  `request_path_url: /v1/completions`) — point it straight at the sim. No
  InferencePool *resolution* needed; `InferencePool` in the code is only a
  **metric label string**.
- The code is explicitly built k8s-free:
  `pkg/plugins/handle.go` — "a trimmed, **Kubernetes-free** analog of EPP's
  Handle"; `pkg/plugins/typedname.go` — "intentionally free of Kubernetes/
  controller-runtime".
- Their own Makefile `run` target is off-cluster: `go run ./cmd/main.go`
  ("Run a controller from your host").

### Tooling / images
- Host tools needed: **just Docker** (have it, Colima 16 GB) + `valkey-cli`
  (have it). **No Homebrew, no kind, no helm, no kubectl.**
- kubectl/helm are pure API clients — trivially containerizable — but we don't
  need them at all for the compose route.
- Images verified multi-arch incl. **arm64** (Apple Silicon) via
  `docker manifest inspect`:
  - `ghcr.io/llm-d/llm-d-async` (real tag e.g. `:e2e-test`)
  - `ghcr.io/llm-d/llm-d-inference-sim` (real tag e.g. `:v0.0.0-test`)
  - `valkey/valkey-bundle`
  Pin real tags, not `:latest`, in the cookbook.

### The compose stack (kv-caching shape, no k8s)
```
valkey/valkey-bundle               # the store (queue + quota)
ghcr.io/llm-d/llm-d-inference-sim  # stub backend, serves /v1/completions
ghcr.io/llm-d/llm-d-async          # async-processor:
                                   #   REDIS_URL -> valkey
                                   #   transport-config: redis-sortedset,
                                   #     igw_base_url -> http://llm-sim:8000
                                   #     request_path_url: /v1/completions
                                   #     gate_type: redis-quota (for AC #2)
```
This is strictly better for a cookbook than kind: no new tooling, far less
memory, ships as a `docker-compose.yml` the reader already knows (and matches
the repo's one existing cookbook). EPP/Envoy were only prod *gateway* plumbing,
not part of the Valkey story.

### Supersedes earlier Tier-2/kind plan
The kind/Helm "Tier 2" above is now the *prod-reference* appendix at most. The
**primary** bring-up and the cookbook's run path = this compose stack. Memory
should be well under the kv-caching 8 GiB (no vLLM, no k8s control plane) —
MEASURE on bring-up.

### Next action (the actual "try it out")
Build a throwaway compose + transport-config JSON, `docker compose up`, then:
submit to the sim path, watch `request-sortedset` fill/drain in `valkey-cli`,
trip the quota → 429 + `async_gate_decisions_total{quota_exhausted}`. Fix
assumptions (exact transport-config JSON shape, how a job is submitted to the
processor vs. directly to the sim, whether the quota gate needs extra config)
as reality corrects them.

---

## UPDATE 2026-10-19 (e) — CORRECTION: submission is a Go producer library,
## NOT an HTTP/OpenAI endpoint on the async component.

Verified against source while prepping the bring-up. Overturns the earlier
"notebook submits via the OpenAI /v1/batches API" assumption.

- `producer.Producer` is a **Go interface**; `SubmitRequest(ctx, req)` is a Go
  method (`producer/producer.go`, `producer/redis_sortedset_producer.go`). The
  e2e tests submit by calling `producer.SubmitRequest(...)` **in-process from
  Go** (`test/e2e/e2e_test.go`), then `producer.GetResult(...)`.
- **No HTTP submit front-end exists in llm-d-async.** `cmd/main.go` builds the
  *consumer* (async-processor). The only producer `main.go` is a test fixture
  (`test/e2e/oldproducer/main.go`).
- The OpenAI-compatible Batch API (`/v1/files`, `/v1/batches`) belongs to a
  **separate repo — `llm-d-batch-gateway`** — not to llm-d-async. Do not
  conflate them.
- `igw_base_url` + `request_path_url` (`/v1/completions`) are where the
  processor **forwards dequeued work** to the backend (the sim), NOT where a
  client submits.

### Verified transport-config JSON shape (for the compose wiring)
`SortedSetConfig` (top level, `pkg/redis/options.go`): `url`, `mode`,
`result_queue_name` (default `result-list`), `poll_interval_ms` (1000),
`batch_size` (10), `claim_lease_ttl_seconds`, `queues[]`.
`SortedSetQueueConfig` (per queue, `pkg/redis/sortedset_impl.go`): `id`,
`queue_name`, `worker_pool_id`, `inference_objective`, `request_path_url`,
`igw_base_url`, embedded `pipeline.GateConfig` (the gate_type/params — incl.
the quota gate), `labels`. Quota gate: `pkg/redis/quota_gate.go` —
`QuotaMode` is `rate-limit` or `concurrency`; refusal →
`Refuse().WithReason(ReasonQuotaExhausted)` → the `quota_exhausted` metric.

### Image tags (public registry — real resolvable tags)
- `ghcr.io/llm-d/llm-d-async:main` (and `:latest`). `e2e-test` does NOT resolve.
- `ghcr.io/llm-d/llm-d-inference-sim:v0.3.0` (also `:latest`, `:v0.1.0`,
  `:v0.2.0`). `v0.0.0-test` does NOT resolve.
- `valkey/valkey-bundle` (arm64 OK). Pin released tags in the cookbook.

### Impact on the NOTEBOOK format decision
A pure-Python notebook **cannot submit through the real producer library**
without a Go helper. Options for the submission step:
1. **Tiny Go producer** (build `test/e2e/oldproducer` or a ~30-line program on
   the `producer` package) — faithful, uses the real enqueue path. Honest, but
   introduces Go into a Python-notebook repo.
2. **Direct Valkey writes replicating `submitRequestScript`** — language-free,
   but re-implements their Lua protocol, which cuts against the "no new code /
   works unchanged" framing. Weaker story.
3. **Pull in `llm-d-batch-gateway`** (separate repo) to get the OpenAI HTTP
   submit API — more moving parts; revisits scope.
→ Lean **(1)**: the demo ships a small Go producer container in the compose
stack (a 4th service) that submits jobs; the notebook/README then observes
Valkey + reads results. Revisit whether the cookbook is then "Go-flavored"
rather than a Python notebook. **Flag to user.**

### Bring-up plan (unchanged in spirit, corrected in detail)
Compose services: valkey-bundle + inference-sim + llm-d-async (consumer) +
a small Go producer (submitter). Then observe `request-sortedset` fill/drain
and the quota path in valkey-cli. MEASURE memory.

---

## UPDATE 2026-10-19 (f) — VALIDATION RUN: consumer path PROVEN off-cluster;
## producer blocked only by sandbox Go-proxy DNS.

Scratch harness at `/Users/matthowt/GITWorkspace/improving/llm-d-valkey-scratch/`
(compose + transport-config + a producer program/Dockerfile). Images pulled:
`valkey/valkey-bundle:latest`, `ghcr.io/llm-d/llm-d-async:main`,
`ghcr.io/llm-d/llm-d-inference-sim:v0.3.0` (all arm64).

### PROVEN
- The async-processor (consumer) runs in **docker compose, no k8s**, reaches
  steady state: "Spawning workers for pool {default, 4}", readiness true,
  metrics server serving, **3 client connections to Valkey**, polling
  `request-sortedset` (depth 0, waiting). Transport-config-file parsed, Valkey
  reached via `REDIS_URL`/`url`.
- **Measured footprint (the "how little memory" answer):**
  async-processor **10.3 MiB**, valkey **47 MiB**, sim **4.3 MiB** →
  whole core stack **~62 MiB**. Orders of magnitude under kv-caching's 8 GiB
  (no k8s control plane, no real vLLM). 8 GiB is vast overkill for this stack.

### Three config corrections banked (assumption → reality)
1. `worker_pool_id` must be **`"default"`** (the auto-created pool) or you must
   supply `--pool-config-file` defining the named pool. An arbitrary name →
   fatal "worker pool \"X\" not found in pool configuration".
2. `--metrics-endpoint-auth=false` is necessary **but not sufficient**.
3. **`startMetricsServer` calls `ctrl.GetConfigOrDie()` UNCONDITIONALLY**
   (`pkg/server/runner.go:122`→`:361`); no `metrics-port=0` guard. Off-cluster
   the process **will not boot** without a kubeconfig. **Fix that works:** mount
   a **dummy kubeconfig** (server `https://127.0.0.1:1`) and set `KUBECONFIG` to
   it. With auth off, no real k8s call is made; the process boots and serves
   metrics `{secure:false}`. **This is the key non-obvious finding for a
   compose-only cookbook** — flag it prominently in the README, or (better) ask
   upstream to gate the metrics server on `metrics-port>0`.

### BLOCKED (environment, not design)
- Building the Go producer needs `go-redis v9.22.0` from the module proxy.
  **This sandbox has no DNS to `proxy.golang.org`** (host AND container; only
  the image registry is reachable). `GOPROXY=off` can't help — the dep isn't in
  the local module cache and llm-d-async isn't vendored. So the
  **submit→queue→dispatch→result** end-to-end could not be completed *here*.
  Everything checkable offline WAS checked: producer code compiles against the
  API (types verified, `*RequestMessage` implements `api.Request`,
  `ResultMessage` fields match), transport-config shape matches upstream
  compat_test, all images run.
- **Next-env step:** on a machine with Go-proxy access, `docker build` the
  producer (in-container, no host Go), run `producer submit`, and confirm:
  `request-sortedset` fills (ZRANGE WITHSCORES shows priority+seq order), drains
  as the sim answers, `result-list` delivers, and a quota gate
  (`gate_type: redis-quota` in the queue config) yields 429s +
  `async_gate_decisions_total{quota_exhausted}`.

### Net assessment of Option 1
Architecture is **validated as far as this environment allows**: the real
`llm-d-async` consumer runs unchanged on Valkey via compose, tiny footprint, no
k8s. The producer is a known, small, verified-to-compile piece blocked only by a
sandbox network rule. Option 1 is sound; finish the producer leg where Go
modules resolve.

### Scratch files (throwaway — NOT the deliverable)
`llm-d-valkey-scratch/`: `docker-compose.yml`, `transport-config.json`
(`worker_pool_id: default`, igw→sim), `kubeconfig-dummy.yaml`,
`producer/{main.go,Dockerfile,go.mod}`. Keep as the bring-up reference; the
cookbook's real files get authored separately once the full loop is seen.
