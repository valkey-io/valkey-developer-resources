## The Problem  

```python
Agent "research-bot" has a plan:
  1. Search the web (1 API call)
  2. Read 15 pages (15 API calls)
  3. Summarize each page (15 LLM calls × 2000 tokens each)
  4. Write final report (1 LLM call × 8000 tokens)

Total: 32 calls, ~38,000 tokens - in 30 seconds.
```

## Step 1: Per-Agent Token Bucket

Token bucket is ideal for agents - it allows bursts (agents work in bursts) while enforcing a steady-state rate:

```python
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
    return {1, tokens}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    local wait = (requested - tokens) / refill_rate
    return {0, tokens, math.ceil(wait * 1000)}
end
"""
```

## Step 2: Tool-Specific Costs

Different tools have different costs. A web search is cheap; code execution is expensive:

```python
TOOL_COSTS = {
    "web_search": 1,
    "read_page": 1,
    "llm_call": 3,       # LLM calls cost 3x
    "code_execute": 5,   # Code execution costs 5x
    "image_generate": 10, # Image gen costs 10x
}

def agent_tool_check(agent_id: str, tool_name: str) -> dict:
    cost = TOOL_COSTS.get(tool_name, 1)
    result = agent_check(agent_id, capacity=50, refill_rate=5.0, cost=cost)
    result["tool"] = tool_name
    result["cost"] = cost
    return result
```

## Step 3: Concurrent Agent Limit

Limit how many agents can run simultaneously per user using a Sorted Set with TTL:

```python
def acquire_agent_slot(user_id: str, agent_id: str, max_concurrent: int = 3, ttl: int = 300) -> bool:
    key = f"concurrent:{user_id}"
    now = time.time()
    client.zremrangebyscore(key, "-inf", now)  # Clean expired
    current = client.zcard(key)
    if current >= max_concurrent:
        return False
    client.zadd(key, {agent_id: now + ttl})
    client.expire(key, ttl)
    return True
```

## Step 4: Agent Budget Tracking

```python
def track_agent_spend(agent_id: str, tokens: int, model: str = "gpt-4"):
    cost_per_1k = {"gpt-4": 0.03, "gpt-4o": 0.005}
    cost = (tokens / 1000) * cost_per_1k.get(model, 0.01)
    pipe = client.pipeline()
    pipe.incrbyfloat(f"agent:spend:{agent_id}:total", cost)
    pipe.incrbyfloat(f"agent:spend:{agent_id}:today", cost)
    pipe.expire(f"agent:spend:{agent_id}:today", 86400)
    pipe.execute()
```

**Key Patterns:** Call rate limit (Hash token bucket), tool-weighted costs (Lua script), concurrent agents (Sorted Set + TTL), budget tracking (INCRBYFLOAT).