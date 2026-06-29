"""Portkey AI Gateway + Valkey production patterns — SDK error handling + monitoring.

Corresponds to cookbook: 03-production.md

Uses the official `portkey-ai` SDK. Demonstrates the production concerns that can
be exercised locally: connection-string formats, the SDK's typed exceptions, and
monitoring via the index-info endpoint. ElastiCache/TLS deployment is config-only
and requires a live AWS cluster, so it is not exercised here.

Tests:
  1. Connection string formats accepted by the gateway (TLS, cluster, password)
  2. Typed exception handling (NotFoundError on 404, ConflictError on 409)
  3. Monitoring — index stats via FT.INFO
"""

from __future__ import annotations

import os

try:
    from portkey_ai import Portkey
    from portkey_ai.api_resources.exceptions import (
        APIStatusError,
        ConflictError,
        NotFoundError,
    )
except ImportError:
    raise SystemExit(
        "Missing dependency: portkey-ai\n"
        "Install first: pip install -r requirements.txt"
    )

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8787") + "/v1"
VALKEY_HOST = os.environ.get("VALKEY_CUSTOM_HOST", "valkey://localhost:6379")
INDEX_NAME = "prod-docs"


def make_client(custom_host: str = VALKEY_HOST) -> Portkey:
    return Portkey(
        api_key="dummy",
        base_url=GATEWAY_URL,
        provider="valkey-search",
        custom_host=custom_host,
    )


def test_connection_formats() -> None:
    """Verify production connection-string formats are accepted by the gateway.

    The custom-host validator accepts the format; a real connection only succeeds
    for reachable endpoints. So a 503 (raised as APIStatusError) still proves the
    format was ACCEPTED — only a 400 (BadRequestError) means rejection. Multi-seed
    cluster strings are only valid for the VALKEY_CONNECTION_STRING env var, not
    this header, so they are not tested here.
    """
    formats = [
        "valkey://localhost:6379",            # plaintext, connects
        "valkeys://localhost:6379",           # TLS scheme, accepted (503 locally)
        "redis://localhost:6379",             # redis scheme, connects
        "rediss://localhost:6379",            # redis TLS scheme, accepted (503 locally)
        "valkey://localhost:6379?cluster=true",  # cluster flag, accepted (503 locally)
        "valkey://:pass@localhost:6379",      # password auth, accepted
    ]
    for fmt in formats:
        client = make_client(fmt)
        try:
            client.post("/indexes", name="fmt-prod", schema={"x": {"type": "TEXT"}})
            client.delete(path="/indexes/fmt-prod")
            print(f"OK: format accepted (connected) -> {fmt}")
        except APIStatusError as e:
            # 503 = accepted but endpoint unreachable locally (expected for TLS/cluster)
            assert e.status_code != 400, f"Format rejected by validator: {fmt}"
            print(f"OK: format accepted ({e.status_code}) -> {fmt}")


def test_typed_exceptions() -> None:
    """Demonstrate the SDK's typed exceptions for gateway error responses."""
    client = make_client()

    # 404 -> NotFoundError
    try:
        client.post("/indexes/does-not-exist/search", vector=[0.1, 0.2, 0.3], top_k=1)
        raise AssertionError("Expected NotFoundError for missing index")
    except NotFoundError:
        print("OK: missing index raises NotFoundError (404)")

    # 409 -> ConflictError
    body = dict(
        name=INDEX_NAME,
        schema={"vector": {"type": "VECTOR", "algorithm": "HNSW", "dims": 3, "distance": "COSINE"}},
        options={"prefix": f"{INDEX_NAME}:"},
    )
    client.post("/indexes", **body)
    try:
        client.post("/indexes", **body)
        raise AssertionError("Expected ConflictError for duplicate index")
    except ConflictError:
        print("OK: duplicate index raises ConflictError (409)")


def test_monitoring() -> None:
    """Retrieve index stats via FT.INFO through the SDK."""
    client = make_client()
    info = client.get(path=f"/indexes/{INDEX_NAME}").json()
    assert "info" in info, "Expected index info in response"
    print("OK: retrieved index stats via FT.INFO (monitoring)")
    client.delete(path=f"/indexes/{INDEX_NAME}")


def main() -> None:
    print("=== Cookbook 03: Production Patterns ===\n")
    test_connection_formats()
    test_typed_exceptions()
    test_monitoring()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
