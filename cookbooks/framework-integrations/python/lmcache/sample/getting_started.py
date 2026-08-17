"""01 - Getting Started: load a real LMCache config and inspect a Valkey chunk.

Demonstrates the Valkey integration boundary using LMCache's own code:

1. Loads ``lmcache_config.yaml`` through LMCache's real
   ``load_engine_config_with_overrides`` (the same function LMCache uses
   internally to parse ``LMCACHE_CONFIG_FILE``).
2. Builds the same Valkey key format LMCache's connector uses
   (``lmcache.utils.CacheEngineKey.to_string()``) for a "cold" prompt and
   stores a chunk-sized blob under it — standing in for the KV tensor bytes
   LMCache would store during real inference.
3. Re-checks the same prompt (a "warm" hit) and a different prompt
   (a "miss") to show what LMCache's connector sees on EXISTS/GET.

This does not run vLLM or touch a GPU — it exercises real LMCache config
and key-generation code against a real local Valkey. Running the full
inference pipeline (vLLM + LMCache + Valkey, with actual TTFT reduction)
additionally requires an NVIDIA GPU; see https://docs.lmcache.ai.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.2
    python getting_started.py
"""

from __future__ import annotations

import asyncio
import os

from common import cache_key, create_client, load_lmcache_config

MODEL_NAME = "Qwen/Qwen3-8B"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "lmcache_config.yaml")

COLD_PROMPT = (
    "Explain the architecture of transformer models in detail, covering "
    "attention mechanisms, positional encoding, and feed-forward layers."
)
MISS_PROMPT = "What is the capital of France?"

# Stand-in for KV tensor bytes LMCache would store for one 256-token chunk.
FAKE_CHUNK_BYTES = os.urandom(4096)


async def main() -> None:
    """Load a real LMCache config, then store/inspect a simulated chunk in Valkey."""
    config = load_lmcache_config(CONFIG_PATH)
    print(f"Loaded LMCache config from {CONFIG_PATH}:")
    print(f"  chunk_size:    {config.chunk_size}")
    print(f"  remote_url:    {config.remote_url}")
    print(f"  remote_serde:  {config.remote_serde}")
    print(f"  extra_config:  {config.extra_config}")

    valkeyClient = await create_client()
    try:
        cold_key = cache_key(MODEL_NAME, COLD_PROMPT)
        print(f"\nValkey key for the cold prompt:\n  {cold_key}")

        exists_before = await valkeyClient.exists([cold_key])
        print(f"EXISTS before store: {bool(exists_before)}")

        await valkeyClient.set(cold_key, FAKE_CHUNK_BYTES)
        print(f"Stored {len(FAKE_CHUNK_BYTES)} bytes under this key (simulated KV cache chunk).")

        # Warm — same prompt, same key, cache hit.
        warm_key = cache_key(MODEL_NAME, COLD_PROMPT)
        assert warm_key == cold_key, "identical prompts must hash to identical keys"
        hit_bytes = await valkeyClient.get(warm_key)
        print(f"\nWarm lookup (same prompt): EXISTS={bool(await valkeyClient.exists([warm_key]))}")
        print(f"  Retrieved {len(hit_bytes)} bytes, matches stored chunk: {hit_bytes == FAKE_CHUNK_BYTES}")

        # Miss — different prompt, different key.
        miss_key = cache_key(MODEL_NAME, MISS_PROMPT)
        print(f"\nDifferent prompt's key:\n  {miss_key}")
        print(f"EXISTS for the different prompt: {bool(await valkeyClient.exists([miss_key]))}")

        dbsize = await valkeyClient.dbsize()
        print(f"\nValkey DBSIZE: {dbsize}")

        await valkeyClient.delete([cold_key])
    finally:
        await valkeyClient.close()


if __name__ == "__main__":
    asyncio.run(main())
