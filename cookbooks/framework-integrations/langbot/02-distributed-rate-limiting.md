# Distributed Rate Limiting with Valkey

**Intermediate** · Python · ~20 min

## What You'll Build

LangBot's default rate limiter (`fixwin`) keeps a fixed-window counter **in memory**. That works for a single process, but when you scale to multiple workers each one tracks its own window — so a global limit of 60 requests/minute becomes 60 *per worker*.

The `valkey_fixwin` algorithm moves that counter into Valkey so every worker increments the **same** key. In this cookbook you'll build the same atomic fixed-window limiter LangBot uses, then prove two workers share one counter.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md) (Valkey running, `valkey-glide` installed)
- Python 3.10+
- `valkey-glide>=2.4.1,<3.0.0`

## How Fixed-Window Limiting Works

A fixed window divides time into aligned buckets of `window-length` seconds. Every request in the same bucket increments one counter; when the counter exceeds `limitation`, further requests in that bucket are rejected. The counter is keyed by *who* is being limited and *which* window:

```text
langbot:ratelimit:fixwin:{launcher_type}:{launcher_id}:{window_start}
```

`window_start` is the bucket's start timestamp, computed by snapping `now` down to the window boundary:

```python
def window_start(now: int, window_size: int) -> int:
    # Snap the current epoch second down to the start of its window bucket.
    # e.g. now=1_700_000_123, window_size=60 -> 1_700_000_100
    return now - now % window_size
```

Because the key embeds `window_start`, each new window is a fresh key. Setting a TTL equal to the window length lets Valkey reap old counters automatically — no cleanup job needed.

## Step 1: The Atomic Counter (Lua)

The naive approach — `GET`, compare, `INCR`, `EXPIRE` as separate round-trips — has a race: two workers can both read `59`, both decide they're under the limit of `60`, and both increment to `61`. The window is breached.

Running the check-and-increment inside a single Lua script makes it atomic: Valkey executes the whole script without interleaving other commands, so concurrent workers can never both pass the boundary.

```python
# KEYS[1] = the window counter key
# ARGV[1] = limitation (max requests allowed in the window)
# ARGV[2] = window_size in seconds (TTL applied when the counter is first created)
#
# Returns -1 when the request is OVER the limit (deny); otherwise returns the
# post-increment counter value (>= 1, allow).
LUA_FIXWIN = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')  -- GET returns nil/false on a missing key; `or '0'` starts a new window at 0
if current >= tonumber(ARGV[1]) then
    return -1
end
current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return current
"""
```

> **Why `redis.call`?** Valkey keeps the `redis.*` scripting API for compatibility, so `redis.call` works on `valkey-bundle`. The `EXPIRE` is only set when `current == 1` (the first request of a new window) so a long-lived abuser can't keep pushing the TTL forward and pinning the counter open.

## Step 2: Wrap It in a Limiter

The limiter loads the script once, creates the `valkey-glide` client lazily, and invokes the script per request. `invoke_script` ships the script hash and only uploads the body if Valkey hasn't cached it yet.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

```python
import asyncio
import os
import time

from glide import GlideClient, GlideClientConfiguration, NodeAddress, Script

KEY_PREFIX = "langbot:ratelimit:fixwin"


class ValkeyFixedWindowLimiter:
    def __init__(self) -> None:
        self._client: GlideClient | None = None
        self._script = Script(LUA_FIXWIN)  # LUA_FIXWIN from Step 1

    async def _ensure_client(self) -> GlideClient:
        if self._client is None:
            config = GlideClientConfiguration(
                addresses=[
                    NodeAddress(
                        os.environ.get("VALKEY_HOST", "localhost"),
                        int(os.environ.get("VALKEY_PORT", "6379")),
                    )
                ],
                client_name="langbot_ratelimit_client",
                # 5s is a safe cookbook default that tolerates Docker-for-Mac /
                # WSL2 / remote-Valkey latency. LangBot's production chat path
                # uses ~500ms to fail fast rather than stall a user message on a
                # slow limiter check; tune toward that once you've measured your
                # link latency.
                request_timeout=5000,
            )
            self._client = await GlideClient.create(config)
        return self._client

    async def allow(self, launcher_type: str, launcher_id: str, window_size: int, limitation: int) -> bool:
        client = await self._ensure_client()
        now = int(time.time())
        bucket = now - now % window_size  # window_start
        key = f"{KEY_PREFIX}:{launcher_type}:{launcher_id}:{bucket}"
        result = int(await client.invoke_script(
            self._script,
            keys=[key],
            args=[str(limitation), str(window_size)],
        ))
        return result >= 1  # -1 means over the limit

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
```

## Step 3: Prove the Counter Is Shared

Spin up two independent clients to stand in for two workers, point them at the same `launcher_id`, and confirm the global limit holds across both. Each worker is its own connection, but they all `INCR` the same key.

```python
async def demo_shared_counter() -> None:
    window_size = 60   # 60-second window
    limitation = 5     # allow 5 requests per window, globally
    launcher = ("group", "shared-room-1")

    # Two "workers", each with its own connection.
    worker_a = ValkeyFixedWindowLimiter()
    worker_b = ValkeyFixedWindowLimiter()
    try:
        allowed = 0
        # Alternate workers; the shared Valkey counter caps the total at 5.
        for i in range(8):
            limiter = worker_a if i % 2 == 0 else worker_b
            if await limiter.allow(*launcher, window_size, limitation):
                allowed += 1
        # Without a shared counter each worker would allow up to 5 (10 total).
        # With Valkey, the two workers together allow exactly `limitation`.
        assert allowed == limitation, f"expected {limitation} allowed, got {allowed}"
        print(f"Shared counter held: {allowed} of 8 requests allowed across 2 workers")
    finally:
        await worker_a.close()
        await worker_b.close()


if __name__ == "__main__":
    asyncio.run(demo_shared_counter())
```

A per-worker in-memory limiter would have allowed up to 10 here (5 each). The shared Valkey counter caps the total at `limitation`, which is the whole point.

## Step 4: Choose a Failure Posture

Valkey is an external dependency. What should happen to a user's message if Valkey is briefly unreachable?

| `fail_strategy` | Behavior on Valkey error | When to use |
|-----------------|--------------------------|-------------|
| `open` (default) | Allow the request through | Limiter is a throttle, not an auth gate — don't drop real users for an infra blip |
| `closed` | Deny the request | Limiter is your abuse/cost guard and over-serving is worse than dropping |

LangBot defaults to **fail-open** and logs a throttled warning (at most once per 60 seconds) so a Valkey outage doesn't flood the log. Crucially, only infrastructure errors (connection/timeout) trigger the fail-open path — configuration bugs and programming errors still raise loudly so regressions are caught.

```python
# Conceptual: only infra errors fail open; bugs propagate.
try:
    result = await self._run_script(key, limitation, window_size)
    ...
except (GlideError, OSError) as err:   # infrastructure errors only
    # fail_strategy 'open' -> return True (allow); 'closed' -> return False (deny)
    return self._fail_strategy != "closed"
```

The `strategy` setting (`drop` vs `wait`) is separate: it decides what happens when a request is legitimately *over* the limit. `drop` rejects immediately; `wait` sleeps until the next window boundary and retries once.

## How It Works Under the Hood

| Operation | Valkey command | Notes |
|-----------|----------------|-------|
| Check-and-increment | `EVAL` (Lua: `GET` + `INCR` + `EXPIRE`) | Atomic; concurrent workers can't both cross the boundary |
| Window expiry | `EXPIRE` (on first request only) | TTL = window length; old counters self-reap |
| Per-window key | `langbot:ratelimit:fixwin:{type}:{id}:{window_start}` | New key each window; `key_prefix` namespaces deployments |

> **Cluster note**: This limiter uses a single key per check, so it is safe in Valkey Cluster — there are no multi-key operations that could scatter across slots. If you customize the script to touch multiple keys, give them a common hash tag.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Limit enforced per-worker, not globally | Confirm every worker uses the same `key_prefix` and `launcher_id`, and points at the same Valkey instance/`db` |
| All requests allowed even over the limit | Likely fail-open after a Valkey error — check logs for the throttled warning and verify connectivity |
| `request timed out` under load | Raise `request_timeout` for higher-latency links, or scale Valkey |
| Counter never resets | Ensure `window-length` is a positive integer; the TTL equals the window length |

[Next: 03 Vector Search →](03-vector-search.md)
