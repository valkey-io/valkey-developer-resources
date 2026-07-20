# Getting Started with Rate Limiting

> Build a fixed-window rate limiter, then extend it with token-aware and dual limiting to handle AI workloads where request size varies dramatically.

**Beginner** · Python · ~15 min

**Who is this for:** Backend engineers and AI application developers who need to throttle API requests and LLM token consumption using Valkey's atomic counters and pipelines.

## Prerequisites

- Docker or Podman installed
- Python 3.9+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:8.1.1
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify it's running:

```bash
docker exec valkey valkey-cli ping
# PONG
```

## Step 2: Install Dependencies

```bash
pip install valkey==6.1.1
```

That's it — no special libraries needed. The `valkey` package is the official Valkey Python client.

## Step 3: Your First Rate Limiter

A fixed-window counter using `INCR` + `EXPIRE` in a pipeline:

```python
import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True, socket_timeout=5.0)

def check_rate_limit(user_id: str, max_requests: int = 10, window: int = 60) -> dict:
    """Fixed-window rate limiter.

    Uses INCR to atomically count requests per window.
    The key includes the window number (timestamp ÷ window size),
    so it auto-rotates every window period.
    """
    window_num = int(time.time() // window)
    key = f"rl:{user_id}:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, window)
    results = pipe.execute()

    current = results[0]
    allowed = current <= max_requests

    return {
        "allowed": allowed,
        "current": current,
        "limit": max_requests,
        "remaining": max(0, max_requests - current),
    }
```

## Step 4: Test It

```python
# Send 12 requests — last 2 should be denied
for i in range(12):
    result = check_rate_limit("user-123", max_requests=10)
    status = "ALLOW" if result["allowed"] else "DENY"
    print(f"[{status}] Request {i+1}: {result['current']}/{result['limit']}")
```

Expected output:

```text
[ALLOW] Request 1: 1/10
[ALLOW] Request 2: 2/10
...
[ALLOW] Request 10: 10/10
[DENY] Request 11: 11/10
[DENY] Request 12: 12/10
```

## Step 5: Token-Aware Limiting

For AI workloads, request count alone is insufficient. A "summarize this 200-page PDF" request consumes far more resources than a "Hi" message. Limit by token consumption:

```python
def check_token_limit(
    identifier: str,
    input_tokens: int,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Rate limit by token consumption per window."""
    window_num = int(time.time() // window)
    key = f"tl:{identifier}:tok:{window_num}"

    # Atomic: get current count, then increment
    pipe = client.pipeline(transaction=True)
    pipe.get(key)
    pipe.incrby(key, input_tokens)
    pipe.expire(key, window)
    results = pipe.execute()

    current_before = int(results[0] or 0)
    allowed = current_before + input_tokens <= max_tokens

    if not allowed:
        client.decrby(key, input_tokens)  # Rollback

    return {
        "allowed": allowed,
        "tokens_used": current_before,
        "tokens_remaining": max(0, max_tokens - current_before),
        "max_tokens": max_tokens,
    }
```

## Step 6: Dual Limiting (Requests + Tokens)

Most production systems limit **both** — you don't want a user making 10,000 tiny requests either:

```python
def dual_limit_check(
    identifier: str,
    tokens: int,
    max_requests: int = 60,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Limit by both request count AND token count."""
    window_num = int(time.time() // window)
    req_key = f"dl:{identifier}:req:{window_num}"
    tok_key = f"dl:{identifier}:tok:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(req_key)
    pipe.expire(req_key, window)
    pipe.incrby(tok_key, tokens)
    pipe.expire(tok_key, window)
    results = pipe.execute()

    req_count = results[0]
    tok_count = results[2]

    req_ok = req_count <= max_requests
    tok_ok = tok_count <= max_tokens
    allowed = req_ok and tok_ok

    blocked_by = None
    if not req_ok:
        blocked_by = "requests"
    elif not tok_ok:
        blocked_by = "tokens"

    return {
        "allowed": allowed,
        "blocked_by": blocked_by,
        "requests": f"{req_count}/{max_requests}",
        "tokens": f"{tok_count}/{max_tokens}",
    }
```

## How It Works

| Component | Role |
|-----------|------|
| `INCR` | Atomically increments a counter — no race conditions |
| `EXPIRE` | Auto-deletes the key after the window ends |
| Pipeline | Batches commands into a single round-trip (~0.2ms) |
| Window numbering | `timestamp ÷ window_size` creates natural time buckets |
| Dual limiting | Checks both axes — prevents abuse via many small or few huge requests |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `max_requests` | — | `10` | Maximum requests per window |
| `max_tokens` | — | `100,000` | Maximum tokens per window |
| `window` | — | `60` | Window duration in seconds |
| `socket_timeout` | — | `5.0` | Prevents indefinite hangs on connection issues |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[02 - Agent and Hierarchical Limiting →](02-agent-hierarchical.md)
