# Proposal: llm-d + Valkey cookbook

**Status:** draft for direction · **Branch:** `llm-d-cookbook-draft` ·
**Target repo:** `valkey-io/valkey-developer-resources`

## What we want to build

A cookbook showing Valkey as the store behind llm-d's async batch component
and its admission (quota) gate. llm-d is a Kubernetes-native distributed
inference stack. Its async processor queues batch and latency-tolerant inference
jobs and admits them under quota. Both use a Redis-protocol store, and both run
against **Valkey unchanged**: no Valkey code changes, no llm-d code changes, only
a connection URL.

The cookbook is a usage and integration guide. It runs llm-d on Valkey and shows
the reader what Valkey is doing underneath.

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

## Open questions

1. **Format.** The acceptance criteria say "cookbook," which in this repo means a
   Jupyter notebook. This integration is Go + containers. Options:
   - **a.** Python notebook that drives the stack and observes Valkey. The
     submitter is a small program on llm-d's public `producer` Go module;
     llm-d does not publish a submitter image, so we would build and maintain
     that container ourselves (or ship its source for the reader to build). The
     reader needs no Go either way.
   - **b.** Go notebook (gophernotes) — most faithful, but new tooling for the
     repo and heavier reader setup.
   - **c.** A guide (README + compose + a script) with no notebook.
   Which do you want?
2. **Depth of "like production."** We can ship the lightweight compose stack
   (small, runs anywhere) and optionally add a Kubernetes/Helm "production
   reference" appendix. Is the compose demo sufficient, or is a k8s path
   required?
3. **Submitter dependency.** The job submitter uses llm-d's public `producer`
   Go module (stable `v1.0.0` API). The alternative, the separate
   `llm-d-batch-gateway`, offers an OpenAI-style HTTP submit API but adds
   PostgreSQL and object storage and makes Valkey one of three stores, which
   dilutes the "Valkey is the store" message. Which do you prefer?
