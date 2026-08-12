# Coordination Patterns for AutoGPT on Valkey

> Work through the three Valkey patterns AutoGPT's platform depends on — sharded pub/sub for agent output, a single-flight lock around an execution step, and a fixed-window counter for rate limits.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers who have AutoGPT's Valkey cluster running and want to understand what the platform actually asks of it — and what breaks when a deployment cannot deliver one of these three things.

AutoGPT's coordination layer is small in surface area and specific in what it needs. Three patterns account for nearly all of it, and each one imposes a requirement on the deployment you point the platform at. Get one wrong and the failure is not a clean error — it is agent output that never reaches the browser, or a step that runs twice.

Each pattern below is a runnable excerpt from [`sample/main.py`](sample/main.py). Run the whole thing at any point with `.venv/bin/python main.py`.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md): a healthy three-shard cluster and the `valkey-glide` client installed
- The client from Step 3 of that guide, or the `connect()` helper in [`sample/main.py`](sample/main.py)

## Step 1: Keep an execution's keys on one shard

Start here, because the other two patterns depend on it.

In cluster mode Valkey hashes each key to one of 16384 slots and assigns slots to shards. A command touching two keys in different slots is rejected with `CROSSSLOT` — the cluster will not do the cross-node work implicitly. Braces mark the part of a key that gets hashed, so keys sharing a brace-delimited tag land on the same shard:

```python
# Everything for one agent execution shares a tag, so it shares a slot.
EXECUTION_TAG = "{autogpt-cookbook-demo}"
STREAM_CHANNEL = EXECUTION_TAG + ":output"
LOCK_KEY = EXECUTION_TAG + ":lock"
RATE_KEY = EXECUTION_TAG + ":ratelimit"
```

That is what makes a multi-key `DELETE` across those keys a single legal command:

```python
await client.delete([LOCK_KEY, RATE_KEY])
```

Drop the shared tag and the same call fails. It is worth reproducing once, so you recognise the error later:

```python
# Deliberately untagged — these two hash to different slots.
await client.delete(["autogpt:lock", "autogpt:ratelimit"])
# glide.exceptions.RequestError: CROSSSLOT Keys in request don't hash to the same slot
```

AutoGPT co-locates an execution's keys and its output channel for exactly this reason. It is also why server-side scripts (`EVAL`) and `MULTI`/`EXEC` transactions in the platform stay within a single slot: neither one lets you escape the constraint.

## Step 2: Stream agent output with sharded pub/sub

When an agent produces output, the backend publishes it and a websocket process relays it to the browser. Ordinary pub/sub in a cluster broadcasts every message to every node, because any client on any node might be subscribed. Sharded pub/sub instead routes by the channel's slot: `SPUBLISH` reaches exactly the shard that owns the channel, and only subscribers on that shard.

The client fixes its subscriptions when it is constructed, so a subscriber is a separate client from the publisher:

```python
from glide import GlideClusterClientConfiguration

subscriptions = GlideClusterClientConfiguration.PubSubSubscriptions(
    channels_and_patterns={
        GlideClusterClientConfiguration.PubSubChannelModes.Sharded: {
            STREAM_CHANNEL
        }
    },
    callback=None,
    context=None,
)
config = GlideClusterClientConfiguration(
    addresses=[NodeAddress("127.0.0.1", 17000)],
    request_timeout=REQUEST_TIMEOUT_MS,
    pubsub_subscriptions=subscriptions,
)
subscriber = await GlideClusterClient.create(config)
```

Publishing takes the `sharded=True` flag, and returns the number of subscribers that received the message:

```python
receivers = await publisher.publish(
    "execution step 1 complete", STREAM_CHANNEL, sharded=True
)
assert receivers == 1, f"expected 1 subscriber, got {receivers}"
```

Check that return value rather than assuming delivery. A publish with no subscribers returns `0` and succeeds — pub/sub is fire-and-forget, and the message is gone. That is the mechanism behind the most common complaint about a misconfigured deployment: agent output silently never arrives, and nothing errors.

Reading is a bounded poll, not an open-ended wait:

```python
MAX_POLL_ATTEMPTS = 50   # 50 × 100 ms = 5 s worst case
POLL_INTERVAL_S = 0.1

for _ in range(MAX_POLL_ATTEMPTS):
    message = subscriber.try_get_pubsub_message()   # not a coroutine
    if message is not None:
        payload = message.message
        print(payload.decode() if isinstance(payload, bytes) else payload)
        break
    await asyncio.sleep(POLL_INTERVAL_S)
```

Note that `try_get_pubsub_message()` returns immediately with `None` when nothing is queued and is *not* awaited, while `get_pubsub_message()` is a coroutine that waits for the next message. The bounded form is what you want in a test or a sample: a dropped message fails in five seconds instead of hanging.

**What this requires of a deployment:** sharded pub/sub (`SPUBLISH`, `SSUBSCRIBE`, `SUNSUBSCRIBE`), which means Valkey 7.2-equivalent semantics or newer. It is not optional and there is no fallback path in the platform.

## Step 3: Guard a step with a single-flight lock

Two workers can pick up the same execution step. `SET` with "only if absent" plus an expiry is the standard guard: the first caller gets the key, the second is refused, and the expiry means a worker that dies holding the lock does not block the step forever.

```python
import uuid

from glide import ConditionalChange, ExpirySet, ExpiryType

# Must exceed the guarded step's worst-case duration, or the lock expires
# while the holder is still working. Size it from your own step latency.
LOCK_TTL_MS = 10_000

holder = str(uuid.uuid4())
acquired = await client.set(
    LOCK_KEY,
    holder,
    conditional_set=ConditionalChange.ONLY_IF_DOES_NOT_EXIST,
    expiry=ExpirySet(ExpiryType.MILLSEC, LOCK_TTL_MS),
)
assert acquired is not None, "first acquisition should succeed"
```

A refused acquisition returns `None` — it is not an exception:

```python
contended = await client.set(
    LOCK_KEY,
    str(uuid.uuid4()),
    conditional_set=ConditionalChange.ONLY_IF_DOES_NOT_EXIST,
    expiry=ExpirySet(ExpiryType.MILLSEC, LOCK_TTL_MS),
)
assert contended is None, "second acquisition should be refused"
```

Releasing is where hand-rolled locks usually go wrong. A bare `DELETE` is only safe when you know you still hold the lock:

```python
await client.delete([LOCK_KEY])   # safe here: this sample is the sole holder
```

If the holder's work overran its TTL, the lock has already expired and been taken by someone else — and this `DELETE` removes *their* lock. The correct release compares the stored token first, which needs to be atomic, so it belongs in a script:

```lua
-- Release only if we are still the holder.
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
```

Valkey 8 and newer also expose `server.call` as an alias for `redis.call`; the form above is the portable one and works on every version this series supports.

Two properties follow from the TTL and are worth stating plainly, because they bound what this pattern can promise: a lock whose TTL expires mid-work no longer excludes anyone, and this construction is single-shard, so it offers no guarantee across a failover that loses unreplicated writes. It is a good fit for "don't do this work twice, usually", which is what AutoGPT needs it for — not for correctness-critical mutual exclusion.

**What this requires of a deployment:** nothing beyond `SET` with `NX` and `PX`, available in every supported version.

## Step 4: Rate-limit with a counter and a fixed window

Rate limits and spend counters are an `INCR` plus an expiry. The subtlety is in the expiry: it must be set only when the key has none, or every request inside the window pushes the window out and a busy caller keeps its own allowance alive forever.

`EXPIRE` with the `NX` flag does exactly that. In `valkey-glide` the flag is `ExpireOptions.HasNoExpiry`:

```python
from glide import ExpireOptions

RATE_WINDOW_S = 60

first = await client.incr(RATE_KEY)
assert first == 1

# NX: set the window only if the key does not already have one.
window_started = await client.expire(
    RATE_KEY, RATE_WINDOW_S, ExpireOptions.HasNoExpiry
)
assert window_started is True
```

The second request increments the counter but must *not* move the deadline:

```python
second = await client.incr(RATE_KEY)
assert second == 2

window_extended = await client.expire(
    RATE_KEY, RATE_WINDOW_S, ExpireOptions.HasNoExpiry
)
assert window_extended is False, "EXPIRE NX must refuse to extend a live window"

remaining = await client.ttl(RATE_KEY)
assert 0 < remaining <= RATE_WINDOW_S
```

Assert on the `False` return, not just on the counter. A client library that quietly drops the `NX` flag — or a proxy that does not implement it — still leaves the counter looking correct while the window silently slides. That failure is invisible until a caller exceeds its limit and is never throttled.

Fixed windows have a known edge: a caller can spend its full allowance at the end of one window and again at the start of the next, briefly doubling the nominal rate. Sliding-window and token-bucket variants trade more state and more commands for a smoother bound. AutoGPT accepts the fixed-window behaviour.

**What this requires of a deployment:** `EXPIRE … NX`, also Valkey 7.2-equivalent semantics.

## Where the rest of the layer fits

The platform's remaining Valkey use follows from these three. Session metadata and cached lookups are plain string and hash operations. Pending-message buffers use Streams. Some multi-step updates run as scripts or transactions, always within one slot — the constraint from Step 1 again. Notably absent: the coordination layer uses **no Valkey modules** at all, so there is no search, JSON or time-series bundle to provision for it.

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `LOCK_TTL_MS` | ✓ | — | Lock lifetime. Must exceed the guarded step's worst-case duration. |
| `RATE_WINDOW_S` | ✓ | — | Fixed-window length for the counter. |
| `MAX_POLL_ATTEMPTS` | — | `50` | Bound on the pub/sub read loop, so a dropped message fails instead of hanging. |
| `POLL_INTERVAL_S` | — | `0.1` | Sleep between polls. Lower it for latency, raise it to cut idle round trips. |
| `sharded` | — | `False` | Pass `True` to publish with `SPUBLISH`. The default broadcasts cluster-wide. |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production →](03-production.md)
