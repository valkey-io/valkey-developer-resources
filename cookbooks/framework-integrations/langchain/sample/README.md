# LangChain + Valkey Sample

> Run a deterministic local demonstration of LangGraph checkpoints, exact caching, and semantic search backed by Valkey.

This directory is the runnable contract for the four cookbook pages. The default
path uses no model provider and no credentials. `main.py` creates a client from
`Settings.from_env()`, runs one checkpoint, cache, and store operation, prints
the results, and cleans up data belonging to that run.

## Prerequisites

- Python 3.10 or newer
- Docker with Compose
- A shell with the current directory set to the repository root

## Setup

Run setup from the repository root:

```bash
cd cookbooks/framework-integrations/langchain/sample
docker compose up -d
docker compose exec valkey valkey-cli ping
# PONG
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The Compose service uses the pinned image `valkey/valkey-bundle:9.1.1`. The
bundle supplies the JSON and Search features required by the store integration.

## Dependency provenance

The pinned `langgraph-checkpoint-aws` package is an AWS-specific dependency that
supplies the `ValkeySaver`, `ValkeyCache`, and `ValkeyStore` classes used by
this sample. It is published under the AWS package namespace, but the default
flow uses only its Valkey integrations and does not require AWS credentials or
services. The optional Bedrock examples below are separate provider addenda.

## Loopback security

The Compose port mapping is `127.0.0.1:${VALKEY_PORT:-6379}:6379`, so the
default service is reachable only from the local machine. Keep it that way for
this sample. Do not change the bind address to expose an unauthenticated Valkey
service. Shared or production deployments need an approved network boundary,
authentication, TLS, and a retention policy.

## Demo

Run the deterministic demo from this directory:

```bash
python main.py
```

Expected output has these three labeled sections:

```text
checkpoint: {'messages': ['Run demo: I forgot my password.']}
cache: {'hit': False, 'value': {'answer': 'Valkey is fast.'}}
semantic search: [...]
```

The exact representation of the semantic-search result depends on the installed package version. The demo cleans its `demo` run data before it exits, so a fresh invocation starts with an empty run namespace.

## Tests

Run the integration tests while the Compose service is healthy:

```bash
python -m pytest -q test_langchain.py
```

The tests cover checkpoint resume and TTLs, cache miss and hit behavior,
semantic search and namespace isolation, environment overrides, cleanup after
failure, idempotent cleanup, and preservation of unrelated keys. A missing
Valkey service fails the test job instead of producing a passing zero-test
result.

## Environment overrides

`Settings.from_env()` reads these exact variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `VALKEY_URL` | `valkey://127.0.0.1:6379` when unset | Full Valkey URL; takes precedence over host and port. |
| `VALKEY_HOST` | `127.0.0.1` | Host fallback when `VALKEY_URL` is unset. |
| `VALKEY_PORT` | `6379` | Port fallback when `VALKEY_URL` is unset. |
| `VALKEY_SOCKET_TIMEOUT` | `5.0` | Socket and connection timeout in seconds. |
| `CHECKPOINT_TTL_SECONDS` | `3600` | Checkpoint lifetime in seconds. |
| `CACHE_TTL_SECONDS` | `300` | Default exact-cache lifetime in seconds. |
| `STORE_TTL_MINUTES` | `60` | Default store lifetime in minutes. |
| `VALKEY_CACHE_PREFIX` | `langchain:cache:` | Prefix used by `ValkeyCache`. |
| `VALKEY_STORE_COLLECTION` | `langchain_store_idx` | Search collection used by `ValkeyStore`. |
| `VALKEY_STORE_NAMESPACE` | `langchain-cookbook` | Namespace prefix used by the sample store. |

For example, this changes only the local timeout and TTLs:

```bash
VALKEY_SOCKET_TIMEOUT=7.5 \
CHECKPOINT_TTL_SECONDS=120 \
CACHE_TTL_SECONDS=45 \
STORE_TTL_MINUTES=15 \
python main.py
```

To use the host and port fallback, leave `VALKEY_URL` unset:

```bash
VALKEY_HOST=127.0.0.1 VALKEY_PORT=6379 python main.py
```

`VALKEY_URL` takes precedence when it is set. Use a secure URL and approved connection controls for a remote service; the sample's default URL is loopback-only.

## Optional provider limitations

The pinned requirements intentionally do not install a hosted LLM or embedding
provider. The default demo uses `DeterministicEmbeddings` with four dimensions,
so it is credential-free and repeatable. A Bedrock addendum can be used only
after installing a compatible provider package, configuring AWS credentials and
permissions, and choosing a new store collection when the provider's embedding
dimensions differ. Provider calls also introduce network access and
data-handling considerations that are outside this sample.

## Teardown

Stop the service and remove its Compose resources from this directory:

```bash
docker compose down --volumes
```

[Back to LangChain + Valkey cookbooks](../README.md)
