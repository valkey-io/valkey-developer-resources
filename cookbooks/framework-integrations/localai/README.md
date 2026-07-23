# LocalAI + Valkey

> Persist LocalAI's vector store in Valkey Search so embeddings survive restarts and scale past an in-memory scan.

[LocalAI](https://github.com/mudler/LocalAI) is a free, open-source, self-hosted
OpenAI-compatible inference stack. Its **stores** subsystem (`/stores/*`) is a
pluggable vector store used by features such as face/voice biometric registries
and the router embedding cache. LocalAI is a community open-source project
maintained by [Ettore Di Giacinto (@mudler)](https://github.com/mudler) and
contributors.

This series covers the **`valkey-store` backend**, which implements the four
`Stores*` operations (Set / Get / Delete / Find) against the
[Valkey Search](https://valkey.io/) module (`FT.*` vector similarity). Unlike
the default in-memory `local-store`, it **persists vectors across restarts** and
supports **opt-in HNSW** indexing — with no change to the `/stores/*` API.

> **Status:** the `valkey-store` backend is added in
> [mudler/LocalAI#10770](https://github.com/mudler/LocalAI/pull/10770), which is
> open at the time of writing. Until it merges and ships in the backend gallery,
> you build the backend (or LocalAI) from the PR branch — every guide below
> annotates this and shows the eventual released path.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start Valkey + LocalAI, select the `valkey-store` backend, and run your first Set/Get over the `/stores/*` REST API. | Beginner, ~20 min, Python |
| 02 | <nobr>[Vector Search & Persistence](02-vector-search.md)</nobr> | KNN `Find`, cosine-similarity semantics, index back-fill, and proving persistence across a restart. | Intermediate, ~25 min, Python |
| 03 | <nobr>[Production Configuration](03-production.md)</nobr> | Per-store model config, auth, TLS, `FLAT` vs `HNSW` tuning, and operational guidance. | Advanced, ~25 min, Python |

## What you'll build

A Python client that drives LocalAI's `/stores/*` endpoints with
`"backend": "valkey-store"`, storing embedding vectors in Valkey and querying
them by nearest-neighbour similarity. The runnable version lives in
[`sample/`](sample/).

## How the pieces fit

| Component | Role |
|-----------|------|
| Your client | Sends embedding vectors + values to LocalAI over HTTP `/stores/*`. |
| LocalAI | OpenAI-compatible server; routes `/stores/*` to the selected store backend. |
| `valkey-store` backend | Go gRPC backend translating Set/Get/Delete/Find into Valkey `HSET`/`HGET`/`DEL`/`FT.SEARCH`. |
| Valkey Search | Stores each vector as a HASH and serves KNN queries via the `FT.*` module; persists via RDB/AOF. |
