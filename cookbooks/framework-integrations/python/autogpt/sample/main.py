#!/usr/bin/env python3
"""AutoGPT + Valkey — runnable cookbook sample.

Demonstrates the three Valkey patterns the AutoGPT platform depends on for its
cache and coordination layer, against the same three-shard cluster topology the
platform's single-container distribution forms at startup:

  1. Sharded pub/sub  — carries agent execution output to the browser.
  2. Distributed lock — single-flight guard around an execution step.
  3. Counter + TTL     — rate limiting and spend counters, via EXPIRE NX.

Third-party dependencies (see requirements.txt):
  - valkey-glide

Usage:
    docker compose up -d   # three-shard cluster on 127.0.0.1:17000-17002
    python main.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

try:
    from glide import (
        ClosingError,
        ConditionalChange,
        ConnectionError as GlideConnectionError,
        ExpireOptions,
        ExpirySet,
        ExpiryType,
        GlideClusterClient,
        GlideClusterClientConfiguration,
        NodeAddress,
        RequestError,
        ServerCredentials,
        TimeoutError as GlideTimeoutError,
    )
except ImportError:
    # Module-level import: this must be caught here, not in main()'s handler,
    # or the hint below is unreachable.
    print(
        "Missing dependency 'valkey-glide'. Install with:\n"
        "    pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1)

# Seed node of the cluster. Any shard works as a seed — GLIDE discovers the
# rest of the topology from it.
VALKEY_HOST = os.environ.get("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "17000"))
# The sample's compose stack runs without a password. AutoGPT's own
# distribution sets one; supply it here to point this sample at that cluster.
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD") or None

# GLIDE's default request timeout is 250 ms, which is tight enough to fail
# spuriously against anything but localhost. 5000 ms is a safe cookbook
# default; lower it once you have measured your own p99.
REQUEST_TIMEOUT_MS = 5000

# Lock lifetime. Must exceed the guarded step's worst-case duration, or the
# lock expires while the holder is still working. 10 s suits this demo; size
# it from your own step latency.
LOCK_TTL_MS = 10_000

# Rate-limit window in seconds — the period a counter accumulates over
# before expiring and starting again.
RATE_WINDOW_S = 60

# Ceiling on the sharded-pub/sub read loop, so a dropped message fails the
# sample instead of hanging. 50 × 100 ms = 5 s worst case.
MAX_POLL_ATTEMPTS = 50
POLL_INTERVAL_S = 0.1

# Braces mark the part of a key Valkey hashes to choose a slot, so every key
# and channel sharing this tag lands on the same shard. That is what lets the
# multi-key DELETE in cleanup() run as one command, and it is how AutoGPT
# keeps an execution's channel and keys co-located.
EXECUTION_TAG = "{autogpt-cookbook-demo}"
STREAM_CHANNEL = EXECUTION_TAG + ":output"
LOCK_KEY = EXECUTION_TAG + ":lock"
RATE_KEY = EXECUTION_TAG + ":ratelimit"


async def connect(
    sharded_channels: set[str] | None = None,
) -> GlideClusterClient:
    """Open a cluster client, optionally subscribed to sharded channels.

    GLIDE fixes subscriptions at construction time, so a subscriber is a
    separate client from the one that publishes.
    """
    subscriptions = None
    if sharded_channels:
        subscriptions = GlideClusterClientConfiguration.PubSubSubscriptions(
            channels_and_patterns={
                GlideClusterClientConfiguration.PubSubChannelModes.Sharded: (
                    sharded_channels
                )
            },
            callback=None,
            context=None,
        )
    config = GlideClusterClientConfiguration(
        addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
        request_timeout=REQUEST_TIMEOUT_MS,
        credentials=(
            ServerCredentials(password=VALKEY_PASSWORD) if VALKEY_PASSWORD else None
        ),
        pubsub_subscriptions=subscriptions,
    )
    # A cluster client refuses to connect to a standalone node, so reaching
    # this line already proves the cluster is formed — the same requirement
    # AutoGPT's backend imposes.
    return await GlideClusterClient.create(config)


async def read_one_message(subscriber: GlideClusterClient) -> str | None:
    """Poll for a single sharded message, bounded by MAX_POLL_ATTEMPTS."""
    for _ in range(MAX_POLL_ATTEMPTS):
        message = subscriber.try_get_pubsub_message()
        if message is not None:
            payload = message.message
            return payload.decode() if isinstance(payload, bytes) else str(payload)
        await asyncio.sleep(POLL_INTERVAL_S)
    return None


async def demo_sharded_pubsub(publisher: GlideClusterClient) -> None:
    """Pattern 1 — stream execution output over sharded pub/sub.

    Cluster mode routes SPUBLISH by the channel's slot, so publisher and
    subscriber reach the same shard without a cluster-wide broadcast. This is
    the path AutoGPT uses to push agent output to a browser.
    """
    subscriber = await connect(sharded_channels={STREAM_CHANNEL})
    try:
        payload = "execution step 1 complete"
        receivers = await publisher.publish(payload, STREAM_CHANNEL, sharded=True)
        assert receivers == 1, (
            f"expected exactly 1 subscriber on {STREAM_CHANNEL}, got {receivers}"
        )

        delivered = await read_one_message(subscriber)
        assert delivered == payload, (
            f"subscriber received {delivered!r}, expected {payload!r}"
        )
        print(f"  sharded pub/sub: delivered {delivered!r} to {receivers} subscriber")
    finally:
        await subscriber.close()


async def demo_distributed_lock(client: GlideClusterClient) -> None:
    """Pattern 2 — single-flight guard with SET NX PX.

    AutoGPT uses this shape so two workers picking up the same execution step
    cannot both run it.
    """
    holder = str(uuid.uuid4())
    acquired = await client.set(
        LOCK_KEY,
        holder,
        conditional_set=ConditionalChange.ONLY_IF_DOES_NOT_EXIST,
        expiry=ExpirySet(ExpiryType.MILLSEC, LOCK_TTL_MS),
    )
    assert acquired is not None, "first lock acquisition should have succeeded"

    # A second worker must be refused while the lock is held. SET NX returns
    # None instead of raising when the key already exists.
    contended = await client.set(
        LOCK_KEY,
        str(uuid.uuid4()),
        conditional_set=ConditionalChange.ONLY_IF_DOES_NOT_EXIST,
        expiry=ExpirySet(ExpiryType.MILLSEC, LOCK_TTL_MS),
    )
    assert contended is None, "second acquisition should have been refused"

    # Releasing with a bare DELETE is only safe because this sample is the
    # sole holder. In production, compare the stored token before deleting
    # (a short EVAL script) — otherwise a holder whose lock already expired
    # can delete the next holder's lock.
    released = await client.delete([LOCK_KEY])
    assert released == 1, f"expected to release 1 lock, deleted {released}"
    print(f"  distributed lock: acquired by {holder[:8]}, contender refused, released")


async def demo_rate_counter(client: GlideClusterClient) -> None:
    """Pattern 3 — fixed-window counter with EXPIRE NX.

    INCR then EXPIRE NX is how AutoGPT's rate limits and spend counters keep a
    window from being extended by later requests inside the same window.
    EXPIRE NX needs Valkey 7.0-equivalent semantics.
    """
    first = await client.incr(RATE_KEY)
    assert first == 1, f"counter should start at 1, got {first}"

    # HasNoExpiry is the NX flag: set the window only if the key has none.
    window_started = await client.expire(
        RATE_KEY, RATE_WINDOW_S, ExpireOptions.HasNoExpiry
    )
    assert window_started is True, "EXPIRE NX should have set the initial window"

    second = await client.incr(RATE_KEY)
    assert second == 2, f"counter should have reached 2, got {second}"

    # The point of NX: the window is not pushed out by the second request, so
    # a busy caller cannot keep its own window alive forever.
    window_extended = await client.expire(
        RATE_KEY, RATE_WINDOW_S, ExpireOptions.HasNoExpiry
    )
    assert window_extended is False, "EXPIRE NX must refuse to extend a live window"

    remaining = await client.ttl(RATE_KEY)
    assert 0 < remaining <= RATE_WINDOW_S, f"unexpected TTL {remaining}"
    print(
        f"  rate counter: {second} hits in window, "
        f"{remaining}s left, window not extended"
    )


async def reset_demo_keys(client: GlideClusterClient) -> None:
    """Clear leftovers so a rerun after a mid-failure starts clean.

    A no-op on the first run: DELETE on absent keys returns 0 rather than
    raising.
    """
    try:
        await client.delete([LOCK_KEY, RATE_KEY])
    except RequestError:
        # Narrow on purpose — a broad except would swallow auth and
        # connection failures that should stop the sample.
        pass


async def run() -> None:
    client = await connect()
    try:
        print(f"Connected to Valkey cluster via {VALKEY_HOST}:{VALKEY_PORT}")
        await reset_demo_keys(client)
        await demo_sharded_pubsub(client)
        await demo_distributed_lock(client)
        await demo_rate_counter(client)
        print("All three AutoGPT coordination patterns verified.")
    finally:
        await reset_demo_keys(client)
        await client.close()


def main() -> int:
    try:
        asyncio.run(run())
    except GlideTimeoutError as exc:
        # Reachable because REQUEST_TIMEOUT_MS is set: a slow or wedged shard
        # times out rather than blocking forever.
        print(
            f"Valkey request timed out after {REQUEST_TIMEOUT_MS} ms: {exc}\n"
            "The cluster may be overloaded, or a shard may be unreachable. "
            "Check `docker compose ps` and raise REQUEST_TIMEOUT_MS if your "
            "network latency is higher than this sample assumes.",
            file=sys.stderr,
        )
        return 1
    except (GlideConnectionError, ClosingError) as exc:
        print(
            f"Could not reach the Valkey cluster at {VALKEY_HOST}:{VALKEY_PORT}: "
            f"{exc}\n"
            "Start it with `docker compose up -d` and confirm the cluster is "
            "formed:\n"
            "    docker compose exec valkey-cluster valkey-cli -p 17000 "
            "cluster info",
            file=sys.stderr,
        )
        return 1
    except RequestError as exc:
        print(
            f"Valkey rejected a command: {exc}\n"
            "If this mentions authentication, set VALKEY_PASSWORD. If it "
            "mentions CROSSSLOT, the keys lost their shared hash tag.",
            file=sys.stderr,
        )
        return 1
    except AssertionError as exc:
        print(f"Sample assertion failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
