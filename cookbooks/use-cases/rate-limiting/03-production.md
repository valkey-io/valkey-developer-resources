# Production Patterns — Budgets, Degradation, and Observability

> Dollar-budget rate limiting, automatic model downgrades, Retry-After headers, circuit breakers, graceful degradation, and request queuing for production AI systems.

**Advanced** · Python · ~30 min

**Who is this for:** Platform engineers deploying AI rate limiting in production who need cost controls, reliability patterns (fail-open on infra issues), graceful degradation, and request queuing.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Completed [02 - Agent and Hierarchical Limiting](02-agent-hierarchical.md)
- Valkey running on localhost:6379
- Python 3.9+ with `valkey==6.1.1`

## Step 1: Dollar-Budget Limiter

Instead of counting tokens, limit by actual dollar spend. Use `INCRBYFLOAT` for sub-cent precision:

```python
import valkey
import time
from datetime import datetime

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True, socket_timeout=5.0)

# Model pricing (configurable — update as pricing changes)
MODEL_COSTS = {
    "model-large": {"input": 0.030, "output": 0.060},
    "model-medium": {"input": 0.005, "output": 0.015},
    "model-small": {"input": 0.001, "output": 0.002},
}


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate the dollar cost of an LLM call."""
    pricing = MODEL_COSTS.get(model, {"input": 0.01, "output": 0.02})
    return round(
        (input_tokens / 1000) * pricing["input"]
        + (output_tokens / 1000) * pricing["output"],
        6,
    )


def check_budget(
    identifier: str, estimated_cost: float, budget: float = 10.00, window: int = 3600
) -> dict:
    """Check if a request fits within the dollar budget for this window."""
    window_num = int(time.time() // window)
    key = f"budget:{identifier}:{window_num}"

    current = float(client.get(key) or 0)

    if current + estimated_cost <= budget:
        client.incrbyfloat(key, estimated_cost)
        client.expire(key, window)
        return {"allowed": True, "remaining": f"${budget - current - estimated_cost:.4f}"}
    else:
        return {"allowed": False, "remaining": f"${max(0, budget - current):.4f}"}
```

## Step 2: Model Downgrade on Budget Pressure

When a user nears their budget, automatically downgrade to cheaper models:

```python
def smart_model_select(identifier: str, preferred_model: str = "model-large") -> str:
    """Select model based on remaining budget percentage."""
    window_num = int(time.time() // 3600)
    current_spend = float(client.get(f"budget:{identifier}:{window_num}") or 0)
    budget = 10.00
    remaining_pct = (budget - current_spend) / budget

    if remaining_pct > 0.5:
        return preferred_model
    elif remaining_pct > 0.2:
        # Downgrade to medium model
        downgrade_map = {"model-large": "model-medium"}
        return downgrade_map.get(preferred_model, preferred_model)
    elif remaining_pct > 0.05:
        return "model-small"  # Emergency mode
    else:
        raise BudgetExhaustedError(f"Budget exhausted for {identifier}")


class BudgetExhaustedError(Exception):
    pass
```

## Step 3: Multi-Horizon Spend Tracking

Track spend across multiple time horizons using a pipeline for efficiency:

```python
def track_spend(identifier: str, cost: float, model: str):
    """Record spend in hourly, daily, and monthly buckets."""
    now = datetime.utcnow()
    pipe = client.pipeline()

    # Hourly bucket
    hour_key = f"spend:{identifier}:hour:{now:%Y%m%d%H}"
    pipe.incrbyfloat(hour_key, cost)
    pipe.expire(hour_key, 7200)

    # Daily bucket
    day_key = f"spend:{identifier}:day:{now:%Y%m%d}"
    pipe.incrbyfloat(day_key, cost)
    pipe.expire(day_key, 172800)

    # Monthly bucket
    month_key = f"spend:{identifier}:month:{now:%Y%m}"
    pipe.incrbyfloat(month_key, cost)
    pipe.expire(month_key, 2764800)

    pipe.execute()
```

## Step 4: Retry-After Headers

Always tell clients **when** to retry — don't just say "no":

```python
def build_rate_limit_headers(result: dict, window: int = 60) -> dict:
    """Build standard rate-limit response headers."""
    headers = {
        "X-RateLimit-Limit": str(result.get("limit", 0)),
        "X-RateLimit-Remaining": str(result.get("remaining", 0)),
        "X-RateLimit-Reset": str(int(time.time()) + window),
    }
    if not result.get("allowed"):
        # Tell the client exactly when to retry
        headers["Retry-After"] = str(window)
    return headers
```

Usage with any ASGI/WSGI framework:

```python
# Pseudocode — adapt to your framework (FastAPI, Flask, etc.)
def handle_request(user_id, prompt):
    result = check_rate_limit(user_id, max_requests=60)
    headers = build_rate_limit_headers(result)

    if not result["allowed"]:
        return Response(
            status=429,
            headers=headers,
            body={"error": "rate_limit_exceeded", "retry_after_seconds": 60},
        )
    return process_request(prompt)
```

## Step 5: Circuit Breaker (Fail-Open)

If Valkey goes down, fail-open (allow requests) rather than blocking everything:

```python
class RateLimiterWithCircuitBreaker:
    """Wraps rate limiting with a circuit breaker.

    If Valkey is unreachable, allows requests through (fail-open)
    rather than blocking all traffic due to infra issues.
    """

    def __init__(self, failure_threshold: int = 3, recovery_seconds: int = 30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.circuit_open_until = 0.0
        self.recovery_seconds = recovery_seconds

    def check(self, user_id: str, tokens: int) -> dict:
        # Circuit is open — fail-open (allow)
        if time.time() < self.circuit_open_until:
            return {"allowed": True, "source": "circuit_breaker"}

        try:
            result = self._do_check(user_id, tokens)
            self.failure_count = 0  # Reset on success
            return result
        except Exception:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.circuit_open_until = time.time() + self.recovery_seconds
            return {"allowed": True, "source": "fallback"}

    def _do_check(self, user_id: str, tokens: int) -> dict:
        """Actual rate limit check against Valkey."""
        window_num = int(time.time() // 60)
        key = f"rl:{user_id}:{window_num}"
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, 60)
        results = pipe.execute()
        current = results[0]
        return {"allowed": current <= 60, "source": "valkey", "current": current}
```

## Step 6: Graceful Degradation

Don't hard-fail — degrade gracefully through model tiers, then cache, then queue:

```python
def smart_llm_call(prompt: str, user_id: str) -> dict:
    """Try progressively cheaper options before rejecting."""
    # Tier 1: Preferred model
    result = check_budget(user_id, estimated_cost=0.03)
    if result["allowed"]:
        return {"model": "model-large", "source": "live"}

    # Tier 2: Cheaper model
    result = check_budget(user_id, estimated_cost=0.005)
    if result["allowed"]:
        return {"model": "model-medium", "source": "live_downgraded"}

    # Tier 3: Queue for later processing
    enqueue_request(user_id, prompt)
    return {"model": None, "source": "queued"}
```

## Step 7: Request Queuing with Streams

Use Valkey Streams to queue requests that can't be served immediately:

```python
def enqueue_request(user_id: str, prompt: str, model: str = "model-large"):
    """Queue a request for deferred processing using Valkey Streams."""
    client.xadd(
        "llm:queue",
        {
            "user_id": user_id,
            "prompt": prompt,
            "model": model,
            "queued_at": str(time.time()),
        },
        maxlen=10000,  # Cap queue length to prevent unbounded growth
    )


def process_queue(batch_size: int = 10) -> list:
    """Process queued requests (run as a background worker)."""
    entries = client.xrange("llm:queue", count=batch_size)
    processed_ids = []
    for entry_id, fields in entries:
        # Process each request...
        processed_ids.append(entry_id)
    # Acknowledge processed entries
    if processed_ids:
        client.xdel("llm:queue", *processed_ids)
    return processed_ids
```

## How It Works

| Component | Role |
|-----------|------|
| `INCRBYFLOAT` | Atomic floating-point increment for sub-cent budget tracking |
| Budget windows | Time-bucketed keys auto-expire — no cleanup needed |
| Circuit breaker | Fail-open prevents Valkey outage from blocking all users |
| Graceful degradation | Cheaper models → cache → queue before hard rejection |
| Streams (`XADD`) | Durable request queue with capped length |
| Retry-After header | Tells clients exactly when to retry (RFC 7231) |

## Production Checklist

| Area | Recommendation |
|------|---------------|
| Headers | `Retry-After` on every 429 response |
| Failure mode | Fail-open — never block users due to infra issues |
| Degradation | Cheaper models before hard rejection |
| Queuing | Don't lose requests — queue with Streams |
| Observability | Log every allow/deny decision with reason |
| Config | Update limits without redeploying (store in Valkey hash) |
| Connections | Use connection pooling; set `socket_timeout=5.0` |
| Atomicity | Lua scripts for check-and-increment correctness |
| Budget tiers | Free ($1/hr), Pro ($10/hr), Enterprise ($100/hr) |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `budget` | — | `10.00` | Dollar budget per window |
| `window` | — | `3600` | Budget window in seconds |
| `failure_threshold` | — | `3` | Consecutive failures before circuit opens |
| `recovery_seconds` | — | `30` | How long circuit stays open |
| `maxlen` (stream) | — | `10000` | Maximum queued requests |
| `socket_timeout` | — | `5.0` | Client connection timeout |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[← 02 - Agent and Hierarchical Limiting](02-agent-hierarchical.md)
