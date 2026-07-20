# Agent and Hierarchical Rate Limiting

> Per-agent token buckets with Lua scripts for burst handling, tool-weighted costs, concurrent agent slots, and cascading multi-tier limits checked in a single Valkey pipeline.

**Intermediate** · Python · ~25 min

**Who is this for:** Platform engineers building multi-agent AI systems who need fine-grained rate control — per-agent burst allowances, tool-specific costs, concurrency limits, and organizational hierarchies.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running on localhost:6379
- Python 3.9+ with `valkey==6.1.1`

## Step 1: Per-Agent Token Bucket (Lua Script)

A token bucket is ideal for agents — they work in bursts (10 API calls in 2 seconds, then idle). The bucket allows bursts up to capacity while enforcing a steady-state refill rate:

```python
import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True, socket_timeout=5.0)

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, math.floor(tokens)}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    local wait = (requested - tokens) / refill_rate
    return {0, math.floor(tokens), math.ceil(wait * 1000)}
end
"""

# Register the script once, call by SHA thereafter
bucket_sha = client.script_load(TOKEN_BUCKET_SCRIPT)


def agent_check(agent_id: str, capacity: int = 50, refill_rate: float = 5.0, cost: int = 1) -> dict:
    """Check if an agent has enough tokens in its bucket."""
    now = time.time()
    result = client.evalsha(
        bucket_sha, 1,
        f"bucket:{agent_id}",
        str(capacity), str(refill_rate), str(cost), str(now),
    )
    allowed = result[0] == 1
    tokens_remaining = result[1]
    retry_after_ms = result[2] if len(result) > 2 else 0

    return {
        "allowed": allowed,
        "tokens_remaining": tokens_remaining,
        "retry_after_ms": retry_after_ms,
    }
```

> **Note on `redis.call`:** Valkey maintains `redis.call` as a compatibility alias in Lua scripts. It works identically to the Valkey-native `server.call`. Both are supported.

## Step 2: Tool-Weighted Costs

Different agent tools have different resource costs. A web search is cheap; code execution is expensive:

```python
TOOL_COSTS = {
    "web_search": 1,
    "read_page": 1,
    "llm_call": 3,         # LLM calls cost 3x
    "code_execute": 5,     # Code execution costs 5x
    "image_generate": 10,  # Image gen costs 10x
}


def agent_tool_check(agent_id: str, tool_name: str) -> dict:
    """Check rate limit with tool-specific cost multiplier."""
    cost = TOOL_COSTS.get(tool_name, 1)
    result = agent_check(agent_id, capacity=50, refill_rate=5.0, cost=cost)
    result["tool"] = tool_name
    result["cost"] = cost
    return result
```

## Step 3: Concurrent Agent Slots

Limit how many agents can run simultaneously per user. Uses a Sorted Set where scores are expiration timestamps:

```python
def acquire_agent_slot(
    user_id: str, agent_id: str, max_concurrent: int = 3, ttl: int = 300
) -> bool:
    """Acquire a concurrent execution slot for an agent.

    Uses a Sorted Set with expiration timestamps as scores.
    Expired entries are cleaned on each call.
    """
    key = f"concurrent:{user_id}"
    now = time.time()

    # Clean expired slots
    client.zremrangebyscore(key, "-inf", str(now))

    # Check current count
    current = client.zcard(key)
    if current >= max_concurrent:
        return False

    # Acquire slot (score = expiration time)
    client.zadd(key, {agent_id: now + ttl})
    client.expire(key, ttl)
    return True


def release_agent_slot(user_id: str, agent_id: str):
    """Release an agent slot when execution completes."""
    client.zrem(f"concurrent:{user_id}", agent_id)
```

## Step 4: Hierarchical Rate Limiting

Real organizations have cascading limits:

```text
Acme Corp (org):     1,000,000 tokens/hour
  +-- Engineering:      500,000 tokens/hour
  |   +-- alice:        100,000 tokens/hour
  |   |   +-- agent-1:   25,000 tokens/hour
  |   |   +-- agent-2:   25,000 tokens/hour
  |   +-- bob:          100,000 tokens/hour
  +-- Marketing:       200,000 tokens/hour
```

The key insight: use a **pipeline** to check all tiers in a single round-trip, then increment atomically only if all pass:

```python
from dataclasses import dataclass


@dataclass
class Tier:
    name: str           # "org", "team", "user", "agent"
    identifier: str     # "acme-corp", "engineering", "alice"
    max_requests: int
    max_tokens: int
    window_seconds: int


def hierarchical_check(tiers: list, tokens: int) -> dict:
    """Check all tiers in 2 round-trips regardless of tier count."""
    now = time.time()

    # Phase 1: Read all counters in one pipeline
    pipe = client.pipeline(transaction=False)
    for tier in tiers:
        window_num = int(now // tier.window_seconds)
        pipe.get(f"hier:{tier.name}:{tier.identifier}:req:{window_num}")
        pipe.get(f"hier:{tier.name}:{tier.identifier}:tok:{window_num}")
    results = pipe.execute()

    # Phase 2: Check each tier against its limits
    blocked_by = None
    for i, tier in enumerate(tiers):
        current_req = int(results[i * 2] or 0)
        current_tok = int(results[i * 2 + 1] or 0)
        if current_req + 1 > tier.max_requests or current_tok + tokens > tier.max_tokens:
            blocked_by = tier.name
            break

    # Phase 3: If allowed, increment all tiers atomically
    if not blocked_by:
        pipe = client.pipeline(transaction=True)
        for tier in tiers:
            window_num = int(now // tier.window_seconds)
            req_key = f"hier:{tier.name}:{tier.identifier}:req:{window_num}"
            tok_key = f"hier:{tier.name}:{tier.identifier}:tok:{window_num}"
            pipe.incr(req_key)
            pipe.expire(req_key, tier.window_seconds)
            pipe.incrby(tok_key, tokens)
            pipe.expire(tok_key, tier.window_seconds)
        pipe.execute()

    return {"allowed": blocked_by is None, "blocked_by": blocked_by}
```

## Step 5: Put It Together

```python
# Define the hierarchy for alice's agent-1
tiers = [
    Tier("org", "acme-corp", 10000, 1_000_000, 3600),
    Tier("team", "engineering", 5000, 500_000, 3600),
    Tier("user", "alice", 1000, 100_000, 3600),
    Tier("agent", "agent-research-1", 200, 25_000, 3600),
]

# Check hierarchical limits
result = hierarchical_check(tiers, tokens=500)
print(result)  # {"allowed": True, "blocked_by": None}
```

## How It Works

| Component | Role |
|-----------|------|
| Lua token bucket | Atomic burst control — refills over time, allows spikes |
| `EVALSHA` | Runs pre-loaded Lua server-side — single round-trip |
| Sorted Set slots | Tracks concurrent agents with automatic expiration |
| Pipeline reads | Fetches all tier counters in one round-trip |
| Transaction writes | Increments all tiers atomically on allow |

## Performance

| Tiers | Pipeline Commands | Round Trips | Latency |
|-------|-------------------|-------------|---------|
| 3 | 6 GET + 12 INCR/EXPIRE | 2 | ~0.3ms |
| 5 | 10 GET + 20 INCR/EXPIRE | 2 | ~0.5ms |
| 7 | 14 GET + 28 INCR/EXPIRE | 2 | ~0.7ms |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Patterns →](03-production.md)
