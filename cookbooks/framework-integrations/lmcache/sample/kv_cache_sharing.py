"""
02 - KV Cache Sharing: Share KV caches across vLLM instances via Valkey.

Launches two vLLM servers on separate GPUs, sends a prompt to Instance A
(which stores the KV cache in Valkey), then sends the same prompt to
Instance B (which loads from Valkey and skips prefill).

NOTE: UNTESTED — requires Linux + 2 NVIDIA GPUs + vLLM. Cannot run on
macOS or against remote LLM APIs. Based on LMCache official docs and examples.

Prerequisites:
    - 2 NVIDIA GPUs
    - Valkey running on localhost:6379
    - pip install -r requirements.txt

Usage:
    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
    python kv_cache_sharing.py

Note:
    This script starts two vLLM server subprocesses. Ensure ports 8000
    and 8001 are available.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

MODEL = "Qwen/Qwen3-8B"
PROMPT = (
    "You are a helpful AI assistant specializing in distributed systems. "
    "Explain the CAP theorem and its implications for modern databases."
)
CONFIG_FILE = Path(__file__).parent / "lmcache_sharing.yaml"

PAYLOAD = {
    "model": MODEL,
    "prompt": PROMPT,
    "max_tokens": 50,
    "temperature": 0,
}


def write_config() -> None:
    """Write the shared LMCache config file."""
    CONFIG_FILE.write_text(
        "chunk_size: 256\n"
        "local_cpu: true\n"
        "max_local_cpu_size: 5.0\n"
        'remote_url: "valkey://localhost:6379"\n'
        'remote_serde: "cachegen"\n'
    )


def start_instance(gpu_id: int, port: int) -> subprocess.Popen:
    """Start a vLLM server with LMCache on the given GPU and port."""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["LMCACHE_CONFIG_FILE"] = str(CONFIG_FILE)
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODEL,
        "--gpu-memory-utilization", "0.8",
        "--port", str(port),
        "--kv-transfer-config",
        '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}',
    ]
    return subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for_server(port: int, proc: subprocess.Popen, timeout: int = 300) -> bool:
    """Wait until the vLLM server is ready or the process exits."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False  # Process already exited
        try:
            resp = requests.get(f"http://localhost:{port}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(2)
    return False


def send_request(port: int) -> float:
    """Send a completion request and return elapsed time in ms."""
    t0 = time.perf_counter()
    resp = requests.post(
        f"http://localhost:{port}/v1/completions",
        json=PAYLOAD,
        timeout=120,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    return elapsed_ms


def main() -> None:
    """Run the cross-instance KV cache sharing demo."""
    write_config()

    print("Starting Instance A (GPU 0, port 8000)...")
    proc_a = None
    proc_b = None

    try:
        proc_a = start_instance(gpu_id=0, port=8000)

        print("Starting Instance B (GPU 1, port 8001)...")
        proc_b = start_instance(gpu_id=1, port=8001)
        print("Waiting for Instance A to be ready...")
        if not wait_for_server(8000, proc_a):
            print("ERROR: Instance A failed to start.")
            return

        print("Waiting for Instance B to be ready...")
        if not wait_for_server(8001, proc_b):
            print("ERROR: Instance B failed to start.")
            return

        # Send to Instance A — computes and stores KV cache
        print("\n--- Instance A (cold — compute + store to Valkey) ---")
        cold_ms = send_request(8000)
        print(f"  TTFT: {cold_ms:.0f}ms")

        time.sleep(2)

        # Send same prompt to Instance B — loads from Valkey
        print("\n--- Instance B (warm — load from Valkey) ---")
        warm_ms = send_request(8001)
        print(f"  TTFT: {warm_ms:.0f}ms")

        print(f"\nSpeedup: {cold_ms / warm_ms:.1f}x")
        print("Instance B loaded KV cache from Valkey without recomputing.")

    finally:
        print("\nShutting down servers...")
        for proc in (proc_a, proc_b):
            if proc is None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        CONFIG_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
