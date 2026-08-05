# Getting Started with DSPy and Valkey

> Use Valkey as a distributed LLM response cache for DSPy, sharing cached completions across workers and eliminating redundant API calls.

**Beginner** · Python · ~15 min

**Who is this for:** Developers using DSPy who want to share cached LLM responses across multiple processes or pods, or who need caching on environments without writable filesystems (serverless, containers).

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Basic familiarity with DSPy (`dspy.Predict`, `dspy.configure`)

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey

DSPy's ValkeyCache uses only core Valkey commands (`SET`, `GET`, `EXISTS`, `DEL`) — no modules required:

```bash
docker run -d --name valkey-dspy \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey:9.1.0
```

Verify it's running:

```bash
docker exec valkey-dspy valkey-cli PING
# PONG
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Install DSPy with Valkey Support

```bash
pip install "dspy[valkey]"
```

This installs DSPy and [valkey-glide](https://github.com/valkey-io/valkey-glide), the official async Valkey client.

## Step 3: Configure ValkeyCache

Replace DSPy's default disk cache with the distributed Valkey backend:

```python
import dspy
from dspy.clients import ValkeyCache

# Point at your local Valkey instance
dspy.cache = ValkeyCache(host="localhost", port=6379)

# Configure your LLM (Ollama — free, local, no API key)
dspy.configure(lm=dspy.LM("ollama_chat/llama3.2", api_base="http://localhost:11434"))
```

That's it. Every LLM call DSPy makes is now cached in Valkey instead of `~/.dspy_cache`.

## Step 4: Verify Caching Works

```python
import time

predict = dspy.Predict("question -> answer")

# First call — cache miss, hits the LLM
start = time.perf_counter()
result1 = predict(question="What is Valkey?")
print(f"First call: {time.perf_counter() - start:.2f}s")

# Second call — cache hit, served from Valkey
start = time.perf_counter()
result2 = predict(question="What is Valkey?")
print(f"Second call: {time.perf_counter() - start:.4f}s")

print(f"Cache hit: {result2.cache_hit}")  # True
print(f"Same answer: {result1.answer == result2.answer}")  # True
```

The second call returns in under 5ms — a Valkey `GET` plus pickle deserialization.

## Step 5: Inspect the Cache

Use `valkey-cli` to see what DSPy stored:

```bash
docker exec valkey-dspy valkey-cli KEYS "dspy:cache:*"
# 1) "dspy:cache:a1b2c3d4e5f6..."
```

Each key is the SHA-256 hash of the serialized request parameters. The value is a pickled LLM response.

## How It Works

```text
┌─────────┐     ┌──────────────┐     ┌─────────┐     ┌─────┐
│  DSPy   │────▶│  ValkeyCache │────▶│  Valkey │     │ LLM │
│ Program │◀────│  (get/put)   │◀────│  Server │     │     │
└─────────┘     └──────────────┘     └─────────┘     └─────┘
                       │                                  ▲
                       │  cache miss                      │
                       └──────────────────────────────────┘
```

1. DSPy's `request_cache` decorator calls `cache.get(request)`
2. On hit: return cached response (no LLM call)
3. On miss: call LLM, then `cache.put(request, response)` stores in Valkey
4. On error: degrade gracefully — return None (miss), never crash

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |

ValkeyCache constructor parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `"localhost"` | Valkey server hostname |
| `port` | `6379` | Valkey server port |
| `ttl_seconds` | `None` | Cache entry TTL (None = no expiry) |
| `key_prefix` | `"dspy:cache:"` | Namespace prefix for all keys |
| `restrict_pickle` | `True` | Restrict deserialization to safe types |

## Cleanup

```bash
docker stop valkey-dspy && docker rm valkey-dspy
```

---

[Next: Production Deployment →](./02-production.md) · [← Back to README](./README.md)
