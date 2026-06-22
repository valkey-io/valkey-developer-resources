# vLLM Semantic Router + Valkey — Cookbook Sample

Runnable Go code for the [vLLM Semantic Router + Valkey cookbook series](../README.md).

This sample exercises the same `valkey-glide` commands the router's three Valkey backends issue — `FT.CREATE`, `FT.SEARCH` (KNN), `HSET`, `HSETNX`, `HINCRBY`, and `SCAN`/`DEL` cleanup — against a local Valkey instance with the Search module. It uses **deterministic stub embeddings** (character-trigram hashing) instead of a real model, so it runs anywhere without a GPU, model download, or the router's Rust candle bindings.

> The goal is to demonstrate the Valkey data-layer mechanics, not to reproduce the router's embedding quality. Real deployments use BERT/Qwen3/Gemma model embeddings.

## Prerequisites

1. **Go 1.24+**
2. **Docker or Podman** (for Valkey)
3. **Valkey with the Search module** — the `valkey/valkey-bundle` image includes it

## Setup

Start Valkey with the Search module:

```bash
# Docker
docker run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
# Podman
podman run -d --name valkey-search -p 6379:6379 valkey/valkey-bundle:latest
```

## Running

Each subcommand maps to one cookbook:

```bash
go run . cache         # cookbook 01 — semantic cache backend
go run . vectorstore   # cookbook 02 — RAG vector store backend
go run . memory        # cookbook 03 — agentic memory backend
```

Each demo creates its index, runs its operations, prints results, and cleans up
its index and keys on exit (including a defensive cleanup of stale resources at
startup, so re-runs after an interrupted run start fresh).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

Both are optional. See [`.env.example`](.env.example) for the placeholders; export them in your shell (e.g. `export VALKEY_PORT=6380`) to override the defaults.

## Files

| File | Purpose |
|------|---------|
| `main.go` | Entry point, client connection, subcommand dispatch |
| `cache.go` | Semantic cache demo (cookbook 01) |
| `vectorstore.go` | Vector store demo (cookbook 02) |
| `memory.go` | Agentic memory demo (cookbook 03) |
| `embedding.go` | Deterministic stub embeddings + float32 byte encoding |
| `keys.go` | TAG escaping and SCAN-based key cleanup |
| `.env.example` | Placeholder values for the optional connection env vars |

## Troubleshooting

- **`ERR unknown command 'FT.CREATE'`** — the Search module is not loaded. Use `valkey/valkey-bundle`, not plain `valkey/valkey`. Verify with `docker exec valkey-search valkey-cli MODULE LIST`.
- **`connection refused` / timeout** — confirm Valkey is running and `VALKEY_HOST`/`VALKEY_PORT` match. The client uses a 5s request timeout; raise it in `main.go` if you are on a high-latency network.
- **Cache or search returns nothing right after writing** — the Search module indexes asynchronously. The demos already sleep briefly before querying.
