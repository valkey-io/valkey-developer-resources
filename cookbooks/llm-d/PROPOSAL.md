# Proposal: llm-d + Valkey cookbook

**Status:** draft for direction · **Branch:** `llm-d-cookbook-draft` ·
**Target repo:** `valkey-io/valkey-developer-resources`

## What we want to build

A cookbook showing **Valkey as the store behind llm-d's async batch component
and its admission (quota) gate**. llm-d is a Kubernetes-native distributed
inference stack. Its async processor queues batch and latency-tolerant inference
jobs and admits them under quota. Both use a Redis-protocol store, and both run
against **Valkey unchanged**: no Valkey code changes, no llm-d code changes, only
a connection URL.

The cookbook is a usage and integration guide. It runs llm-d on Valkey and shows
the reader what Valkey is doing underneath.

## Why it's worth doing

- It extends the AI-infrastructure story the repo already tells with kv-caching
  (LMCache): another real LLM-serving component backed by Valkey.
- The integration is real, not a toy. llm-d uses a **sorted-set job queue**
  (priority and sequence ordering via Lua), a **sorted-set quota gate**, and an
  **at-least-once result-delivery** protocol with claim/reclaim. There is a real
  data model to show, not just a config knob.
- It is upstream-supported. llm-d's own Helm chart states it is "compatible with
  any Redis-protocol server including Valkey" and "all redis.* fields work
  unchanged when pointed at a Valkey endpoint."

## What the reader does and sees

1. `docker compose up` — Valkey + llm-d's async processor + a stub inference
   backend (`llm-d-inference-sim`, no GPU, no model download).
2. Submit a batch of inference jobs.
3. Watch Valkey hold the work: the `request-sortedset` queue fills in priority
   order and drains as jobs dispatch; results flow back through the result
   list. (Valkey as the job queue.)
4. Submit past the quota: some jobs are refused, visible as rejections and in
   the processor's `quota_exhausted` metric. (Valkey as the admission gate.)
5. A short section confirms nothing was modified, only the Valkey URL.

## What we've validated already

- The real llm-d async processor runs on Valkey via **docker compose, no
  Kubernetes**, and reaches steady state: it connects, spawns workers, and polls
  the queue. We verified this by running it, not by reading code.
- **Footprint is tiny: ~62 MiB** for the whole core stack, against 8 GiB for the
  kv-caching cookbook. No GPU, no model, no cluster.
- Running it surfaced a few documented setup wrinkles. For example, the processor
  needs a trivial kubeconfig stub to start off-cluster. These are solvable and
  will be handled in the cookbook's setup.
- One leg, the job *submitter*, is a small program built on llm-d's public
  producer library. It is written and compiles; finishing the end-to-end run
  needs a build environment with Go-module access.

## Open questions for management

1. **Format.** The acceptance criteria say "cookbook," which in this repo means a
   Jupyter notebook. This integration is Go + containers. Options:
   - **a.** Python notebook that drives the stack and observes Valkey (submitter
     runs as a prebuilt container; reader needs no Go). *Recommended.*
   - **b.** Go notebook (gophernotes) — most faithful, but new tooling for the
     repo and heavier reader setup.
   - **c.** A guide (README + compose + a script) with no notebook.
   Which do you want?
2. **Depth of "like production."** We can ship the lightweight compose stack
   (recommended, since it's small and runs anywhere) and optionally add a
   Kubernetes/Helm "production reference" appendix. Is the compose demo
   sufficient, or is a k8s path required?
3. **Submitter dependency.** The job submitter uses llm-d's public `producer`
   Go module (stable `v1.0.0` API). The alternative, the separate
   `llm-d-batch-gateway`, offers an OpenAI-style HTTP submit API but adds
   PostgreSQL and object storage and makes Valkey one of three stores, which
   dilutes the "Valkey is the store" message. We recommend the producer library.
   Agree?
4. **Scope confirmation.** We are building only the **llm-d** item. The separate
   **Alibaba Tair KVCache / GCM** integration, the one that would need new code,
   is explicitly out of scope here. Please confirm.

## Recommendation

Proceed with the **compose + Python-notebook** shape (1a, 2 compose-first,
3 producer library), scoped to llm-d only. It matches the acceptance criteria,
keeps Valkey central, runs on any laptop, and reuses the kv-caching cookbook
pattern. We finish the end-to-end run once the submitter builds, then author the
cookbook.
