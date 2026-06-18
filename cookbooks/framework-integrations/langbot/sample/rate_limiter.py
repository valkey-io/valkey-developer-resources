"""LangBot + Valkey distributed fixed-window rate limiter — runnable demo.

Corresponds to cookbook: 02-distributed-rate-limiting.md

Demonstrates:
  1. A single client enforcing a fixed-window limit.
  2. Two independent "workers" (separate connections) sharing ONE counter.

Run against a local Valkey:
    docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
    python rate_limiter.py

Config via environment (defaults shown):
    VALKEY_HOST=localhost
    VALKEY_PORT=6379
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

try:
    from glide import GlideClient, GlideClientConfiguration, NodeAddress, Script
except ImportError:
    print("valkey-glide is not installed. Install it with:")
    print("    pip install 'valkey-glide>=2.4.1,<3.0.0'")
    sys.exit(1)


KEY_PREFIX = "langbot:ratelimit:fixwin"

# Atomic check-then-increment fixed-window script.
#   KEYS[1] = window counter key
#   ARGV[1] = limitation (max requests per window)
#   ARGV[2] = window size in seconds (TTL applied on first request of a window)
# Returns -1 when over the limit (deny); otherwise the post-increment count.
LUA_FIXWIN = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current >= tonumber(ARGV[1]) then
    return -1
end
current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return current
"""


class ValkeyFixedWindowLimiter:
    """Mirror of LangBot's valkey_fixwin algorithm (request path only)."""

    def __init__(self) -> None:
        self._client: GlideClient | None = None
        self._script = Script(LUA_FIXWIN)

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
                # 500ms matches LangBot's real-time chat path (fail fast). Raise
                # this for a higher-latency network link to Valkey.
                request_timeout=500,
            )
            self._client = await GlideClient.create(config)
        return self._client

    @staticmethod
    def _build_key(launcher_type: str, launcher_id: str, window_start: int) -> str:
        return f"{KEY_PREFIX}:{launcher_type}:{launcher_id}:{window_start}"

    async def allow(
        self, launcher_type: str, launcher_id: str, window_size: int, limitation: int
    ) -> bool:
        client = await self._ensure_client()
        now = int(time.time())
        window_start = now - now % window_size  # snap down to window boundary
        key = self._build_key(launcher_type, launcher_id, window_start)
        result = int(
            await client.invoke_script(
                self._script,
                keys=[key],
                args=[str(limitation), str(window_size)],
            )
        )
        return result >= 1  # -1 => over the limit

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


async def _cleanup(client: GlideClient, launcher_type: str, launcher_id: str) -> None:
    """Delete this demo's window keys so re-runs start clean (idempotent).

    Uses SCAN (never KEYS) for non-blocking cursor iteration. A bounded loop
    guards against an unexpectedly never-emptying cursor.
    """
    pattern = f"{KEY_PREFIX}:{launcher_type}:{launcher_id}:*"
    cursor: object = b"0"
    max_rounds = 1000  # safety cap; far more than any realistic key count here
    for _ in range(max_rounds):
        cursor, keys = await client.scan(cursor, match=pattern, count=500)
        if keys:
            await client.delete(keys)
        if cursor in (b"0", "0", 0):
            break


async def demo_single_client() -> None:
    print("\n=== Demo 1: single client fixed-window limit ===")
    window_size = 60  # 60-second window
    limitation = 5    # allow 5 requests per window
    launcher = ("person", "demo-user-1")

    limiter = ValkeyFixedWindowLimiter()
    try:
        client = await limiter._ensure_client()
        await _cleanup(client, *launcher)  # reset window for a deterministic run

        decisions = [await limiter.allow(*launcher, window_size, limitation) for _ in range(7)]
        allowed = sum(decisions)
        denied = len(decisions) - allowed
        print(f"  sent 7 requests -> allowed={allowed}, denied={denied}")
        assert allowed == limitation, f"expected {limitation} allowed, got {allowed}"
        assert denied == 2, f"expected 2 denied, got {denied}"

        await _cleanup(client, *launcher)
    finally:
        await limiter.close()


async def demo_shared_counter() -> None:
    print("\n=== Demo 2: two workers share one counter ===")
    window_size = 60
    limitation = 5
    launcher = ("group", "demo-shared-room")

    worker_a = ValkeyFixedWindowLimiter()
    worker_b = ValkeyFixedWindowLimiter()
    try:
        client = await worker_a._ensure_client()
        await _cleanup(client, *launcher)

        allowed = 0
        # Alternate workers; the shared Valkey counter caps the global total.
        for i in range(8):
            limiter = worker_a if i % 2 == 0 else worker_b
            if await limiter.allow(*launcher, window_size, limitation):
                allowed += 1
        print(f"  2 workers sent 8 requests -> allowed={allowed} (global cap={limitation})")
        # Per-worker in-memory limiting would allow up to 10 (5 each); the
        # shared counter allows exactly `limitation`.
        assert allowed == limitation, f"expected {limitation} allowed, got {allowed}"

        await _cleanup(client, *launcher)
    finally:
        await worker_a.close()
        await worker_b.close()


async def main() -> None:
    await demo_single_client()
    await demo_shared_counter()
    print("\nAll rate-limiter demos passed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"\nAssertion failed: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — friendly top-level message
        print(f"\nError: {exc}")
        print("Is Valkey running? Try: docker run -d -p 6379:6379 valkey/valkey-bundle:latest")
        sys.exit(1)
