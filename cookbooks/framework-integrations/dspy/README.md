# DSPy + Valkey Distributed Cache Cookbook

> Use Valkey as a shared LLM response cache for [DSPy](https://dspy.ai/) (Stanford NLP), eliminating redundant API calls across workers and enabling caching in serverless environments.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Replace DSPy's local disk cache with a shared Valkey backend |
| [Production Deployment](./02-production.md) | Intermediate | TTL policies, TLS, authentication, cluster mode, and tenant isolation |

## Prerequisites

- **Valkey 8+** (core commands only — no modules required)
- **Docker** and **Docker Compose**
- **Python 3.10+**
- **DSPy 3.3+** with the `valkey` extra (`pip install "dspy[valkey]"`)

## How DSPy Uses Valkey

DSPy's `ValkeyCache` stores pickled LLM responses keyed by SHA-256 hash of the request parameters:

- **SET** — Store a new response after an LLM call (`dspy:cache:<sha256hex>` → pickled bytes)
- **GET** — Retrieve a cached response on repeat calls (cache hit)
- **EXISTS** — Check if a key is present (used by `__contains__`)
- **DEL** — Evict poisoned entries detected by restricted pickle deserialization

No Valkey modules are required. The cache uses only core string commands.

## Upstream Status

> **Note:** The ValkeyCache backend is introduced in
> PR [stanfordnlp/dspy#10150](https://github.com/stanfordnlp/dspy/pull/10150)
> (currently OPEN). This cookbook documents the integration. The sample tests
> validate the underlying Valkey patterns independently using `valkey-glide`.

## Quick Start

```python
import dspy
from dspy.clients import ValkeyCache

# Swap in the distributed cache
dspy.cache = ValkeyCache(host="localhost", port=6379)

# Use DSPy normally — caching is transparent
dspy.configure(lm=dspy.LM("ollama_chat/llama3.2", api_base="http://localhost:11434"))
predict = dspy.Predict("question -> answer")
result = predict(question="What is Valkey?")
```

## Running the Sample Tests

```bash
cd sample/
docker compose up -d
pip install -e .
pytest tests/ -v
docker compose down
```

---

[← Back to Valkey Samples](../../../README.md)
