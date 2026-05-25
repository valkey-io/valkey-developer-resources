"""
01 - Getting Started: Offload KV cache to Valkey.

Demonstrates LMCache with vLLM using Valkey as the L2 KV cache backend.
Runs two identical prompts and shows the TTFT improvement on the second
(cached) run.

NOTE: UNTESTED — requires Linux + NVIDIA GPU + vLLM. Cannot run on macOS
or against remote LLM APIs. Based on LMCache official docs and examples.

Prerequisites:
    - NVIDIA GPU with sufficient VRAM for Qwen3-8B (~16 GB)
    - Valkey running on localhost:6379
    - pip install -r requirements.txt

Usage:
    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
    python getting_started.py
"""

from __future__ import annotations

import os
import time

# Configure LMCache environment before importing vLLM
os.environ["LMCACHE_CHUNK_SIZE"] = "256"
os.environ["LMCACHE_LOCAL_CPU"] = "True"
os.environ["LMCACHE_MAX_LOCAL_CPU_SIZE"] = "5.0"
os.environ["LMCACHE_REMOTE_URL"] = "valkey://localhost:6379"
os.environ["LMCACHE_REMOTE_SERDE"] = "naive"

from lmcache.integration.vllm.utils import ENGINE_NAME  # noqa: E402
from lmcache.v1.cache_engine import LMCacheEngineBuilder  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402
from vllm.config import KVTransferConfig  # noqa: E402

MODEL = "Qwen/Qwen3-8B"
PROMPT = (
    "Explain the architecture of transformer models in detail, "
    "covering attention mechanisms, positional encoding, "
    "and feed-forward layers."
)


def main() -> None:
    """Run two inference passes and compare TTFT."""
    llm = LLM(
        model=MODEL,
        kv_transfer_config=KVTransferConfig(
            kv_connector="LMCacheConnectorV1",
            kv_role="kv_both",
        ),
        max_model_len=8000,
        gpu_memory_utilization=0.8,
    )

    sampling_params = SamplingParams(temperature=0, max_tokens=50)

    # First run — cold (computes KV cache, stores to Valkey)
    t0 = time.perf_counter()
    outputs = llm.generate([PROMPT], sampling_params)
    cold_ms = (time.perf_counter() - t0) * 1000
    print(f"Cold run:  {cold_ms:.0f}ms")
    print(f"  Output: {outputs[0].outputs[0].text!r}\n")

    # Second run — warm (loads KV cache from Valkey)
    t0 = time.perf_counter()
    outputs = llm.generate([PROMPT], sampling_params)
    warm_ms = (time.perf_counter() - t0) * 1000
    print(f"Warm run:  {warm_ms:.0f}ms")
    print(f"  Output: {outputs[0].outputs[0].text!r}\n")

    if warm_ms > 0:
        print(f"Speedup: {cold_ms / warm_ms:.1f}x")

    # Cleanup
    LMCacheEngineBuilder.destroy(ENGINE_NAME)


if __name__ == "__main__":
    main()
