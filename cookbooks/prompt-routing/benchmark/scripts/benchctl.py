#!/usr/bin/env python3
"""Helpers that run-benchmark.sh calls from inside the bench network.

  calibrate           measure peak prefill throughput on one vLLM replica
  reset-prefix-cache  drop every replica's prefix cache (needs VLLM_SERVER_DEV_MODE=1)
  wait-router         block until a completion succeeds through Envoy and the EPP

Standard library only, so it runs in any image with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import urllib.error
import urllib.request


def post(url: str, body: dict | None = None, timeout: float = 30.0):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Surface the server's explanation (vLLM puts it in the body).
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"POST {url} returned HTTP {exc.code}: {detail}") from None


def time_to_first_token(endpoint: str, model: str, n_tokens: int) -> float:
    # Random token IDs, so the prefix cache misses and we time a full prefill.
    # IDs stay well inside Qwen3's vocabulary and away from special tokens.
    prompt = [random.randint(1000, 100_000) for _ in range(n_tokens)]
    body = {"model": model, "prompt": prompt, "max_tokens": 1, "temperature": 0, "stream": True}
    start = time.perf_counter()
    with post(f"{endpoint}/v1/completions", body, timeout=300) as resp:
        for raw in resp:
            if raw.startswith(b"data:") and raw.strip() != b"data: [DONE]":
                elapsed = time.perf_counter() - start
                for _ in resp:  # drain the stream
                    pass
                return elapsed
    raise RuntimeError("stream ended without a token")


def calibrate(args: argparse.Namespace) -> None:
    """peakPrefillThroughput = chunk / median(TTFT), the method llm-d's
    guides/recipes/router/calibration uses. chunk should equal vLLM's
    --max-num-batched-tokens."""
    for _ in range(args.warmup):
        time_to_first_token(args.endpoint, args.model, args.chunk)
    samples = [time_to_first_token(args.endpoint, args.model, args.chunk) for _ in range(args.measure)]
    median = statistics.median(samples)
    print(
        f"calibrate: chunk={args.chunk} median_ttft={median:.4f}s "
        f"min={min(samples):.4f}s max={max(samples):.4f}s",
        file=sys.stderr,
    )
    print(round(args.chunk / median))


def reset_prefix_cache(args: argparse.Namespace) -> None:
    for endpoint in args.endpoints:
        with post(f"{endpoint}/reset_prefix_cache") as resp:
            if resp.status != 200:
                sys.exit(f"reset-prefix-cache: {endpoint} returned HTTP {resp.status}")
        print(f"reset-prefix-cache: {endpoint} ok", file=sys.stderr)


def wait_router(args: argparse.Namespace) -> None:
    body = {"model": args.model, "prompt": "ping", "max_tokens": 1}
    deadline = time.monotonic() + args.timeout
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            with post(f"{args.url}/v1/completions", body, timeout=30) as resp:
                if resp.status == 200:
                    print("wait-router: router is serving", file=sys.stderr)
                    return
                last_error = f"HTTP {resp.status}"
        except (urllib.error.URLError, OSError, RuntimeError) as exc:
            last_error = str(exc)
        time.sleep(3)
    sys.exit(f"wait-router: router not serving after {args.timeout}s (last error: {last_error})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("calibrate")
    p.add_argument("--endpoint", required=True, help="one vLLM replica, e.g. http://172.30.0.11:8000")
    p.add_argument("--model", required=True)
    p.add_argument("--chunk", type=int, default=8192)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--measure", type=int, default=20)
    p.set_defaults(func=calibrate)

    p = sub.add_parser("reset-prefix-cache")
    p.add_argument("endpoints", nargs="+")
    p.set_defaults(func=reset_prefix_cache)

    p = sub.add_parser("wait-router")
    p.add_argument("--url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(func=wait_router)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
