"""Portkey AI Gateway + Valkey getting started — cache LLM responses with the SDK.

Corresponds to cookbook: 01-getting-started.md

Uses the official `portkey-ai` SDK pointed at a local gateway backed by Valkey.

Tests:
  1. Build a Portkey client targeting the gateway
  2. Verify the gateway is reachable and Valkey is the active backend
  3. (Optional) Make two identical cached chat completions and show MISS -> HIT.
     Runs only when an LLM provider key is set via PROVIDER_API_KEY.
"""

from __future__ import annotations

import os

try:
    from portkey_ai import Portkey
except ImportError:
    raise SystemExit(
        "Missing dependency: portkey-ai\n"
        "Install first: pip install -r requirements.txt"
    )

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8787") + "/v1"
VALKEY_HOST = os.environ.get("VALKEY_CUSTOM_HOST", "valkey://localhost:6379")
# Cached-completion demo provider. Use a cloud provider with PROVIDER_API_KEY,
# or run locally with no key via PROVIDER=ollama (default below uses ollama).
PROVIDER = os.environ.get("PROVIDER", "ollama")
PROVIDER_API_KEY = os.environ.get("PROVIDER_API_KEY")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("MODEL", "llama3.2:latest")


def verify_valkey_backend() -> None:
    """Confirm the SDK reaches the gateway and Valkey is the active backend.

    Uses the valkey-search provider through the same SDK: a successful index
    round-trip proves the gateway is connected to Valkey.
    """
    client = Portkey(
        api_key="dummy",  # gateway requires a provider header, not a real key here
        base_url=GATEWAY_URL,
        provider="valkey-search",
        custom_host=VALKEY_HOST,
    )
    client.post(
        "/indexes",
        name="gs-probe",
        schema={"content": {"type": "TEXT"}},
        options={"prefix": "gs-probe:"},
    )
    info = client.get(path="/indexes/gs-probe").json()
    assert info["object"] == "index", f"Unexpected index info: {info}"
    client.delete(path="/indexes/gs-probe")
    print("OK: SDK reached the gateway; Valkey is the active backend")


def demo_cached_completion() -> None:
    """Make two identical chat completions and show the cache speedup.

    The gateway caches the first response in Valkey (cache mode 'simple') and
    serves the second from Valkey — far faster.

    Requires the gateway to be built with `"cache": true` in conf.json. Runs
    against a local Ollama by default (no API key needed); set PROVIDER and
    PROVIDER_API_KEY to use a cloud provider instead.
    """
    import time

    if PROVIDER == "ollama":
        client = Portkey(
            api_key="dummy",
            base_url=GATEWAY_URL,
            provider="ollama",
            custom_host=OLLAMA_HOST,
            config={"cache": {"mode": "simple"}},
        )
    elif PROVIDER_API_KEY:
        client = Portkey(
            api_key="dummy",
            base_url=GATEWAY_URL,
            provider=PROVIDER,
            Authorization=f"Bearer {PROVIDER_API_KEY}",
            config={"cache": {"mode": "simple"}},
        )
    else:
        print("SKIP: set PROVIDER_API_KEY for a cloud provider, or run Ollama locally")
        return

    # A unique prompt per run so the first call is always a fresh MISS
    messages = [{"role": "user", "content": f"Reply with one word. Token {time.time()}"}]

    # First call — cache MISS, hits the LLM and stores the response in Valkey
    t0 = time.time()
    first = client.chat.completions.create(model=MODEL, messages=messages)
    miss_ms = (time.time() - t0) * 1000
    assert first.choices[0].message.content, "Empty completion on first call"
    print(f"OK: first call (MISS) {miss_ms:.0f}ms")

    # Second identical call — cache HIT, served from Valkey
    t0 = time.time()
    second = client.chat.completions.create(model=MODEL, messages=messages)
    hit_ms = (time.time() - t0) * 1000
    assert second.choices[0].message.content, "Empty completion on second call"
    assert hit_ms < miss_ms, f"Cache HIT ({hit_ms:.0f}ms) not faster than MISS ({miss_ms:.0f}ms)"
    print(f"OK: second call (HIT) {hit_ms:.0f}ms — served from Valkey")


def main() -> None:
    print("=== Cookbook 01: Getting Started ===\n")
    verify_valkey_backend()
    demo_cached_completion()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
