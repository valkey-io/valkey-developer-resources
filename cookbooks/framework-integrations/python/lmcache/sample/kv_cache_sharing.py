"""02 - KV Cache Sharing: two simulated instances sharing chunks via Valkey.

In real LMCache, two separate vLLM+LMCache processes computing the same
prompt produce the same Valkey key (``CacheEngineKey.to_string()`` is a
pure function of model name, world size, worker id, chunk hash, and
dtype) — so whichever instance computes the chunk first, every other
instance reads it back instead of recomputing it.

This script simulates that with two independent GLIDE clients ("instance
A" and "instance B") talking to the same Valkey server. It does not run
vLLM or touch a GPU — see ``getting_started.py`` and the cookbook docs for
the scope of what this demonstrates versus a real inference pipeline.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:8.1.1
    python kv_cache_sharing.py
"""

from __future__ import annotations

import asyncio
import os

from common import cache_key, create_client

MODEL_NAME = "Qwen/Qwen3-8B"
SHARED_PROMPT = (
    "You are a helpful AI assistant specializing in distributed systems. "
    "Explain the CAP theorem and its implications for modern databases."
)
FAKE_CHUNK_BYTES = os.urandom(4096)


async def main() -> None:
    """Instance A stores a chunk; Instance B reads it without recomputing."""
    # Two independent connections, standing in for two separate vLLM +
    # LMCache processes that happen to share the same Valkey backend.
    # Each client is opened in its own try/finally so a failure creating
    # instance_b can't leak an already-open instance_a connection.
    instance_a = await create_client()
    try:
        instance_b = await create_client()
        try:
            key_a = cache_key(MODEL_NAME, SHARED_PROMPT, worker_id=0)
            print(f"Instance A's key for the shared prompt:\n  {key_a}")

            print("\n--- Instance A (cold — compute + store) ---")
            await instance_a.set(key_a, FAKE_CHUNK_BYTES)
            print(f"  Stored {len(FAKE_CHUNK_BYTES)} bytes.")

            # Instance B computes the SAME key independently — it never
            # talked to Instance A, only to the shared Valkey.
            key_b = cache_key(MODEL_NAME, SHARED_PROMPT, worker_id=0)
            assert key_b == key_a, (
                "same model/prompt/worker must hash to the same key across instances"
            )

            print("\n--- Instance B (warm — load from Valkey) ---")
            exists = await instance_b.exists([key_b])
            print(f"  EXISTS on Instance B's connection: {bool(exists)}")
            loaded = await instance_b.get(key_b)
            print(f"  Retrieved {len(loaded)} bytes, matches what A stored: {loaded == FAKE_CHUNK_BYTES}")
            print("  Instance B never recomputed the chunk — it read what Instance A wrote.")

            await instance_a.delete([key_a])
        finally:
            await instance_b.close()
    finally:
        await instance_a.close()


if __name__ == "__main__":
    asyncio.run(main())
