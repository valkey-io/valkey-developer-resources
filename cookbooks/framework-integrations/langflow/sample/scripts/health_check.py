"""Health check script for Langflow and Valkey services.

Usage:
    export LANGFLOW_BASE_URL=http://127.0.0.1:7860
    python scripts/health_check.py
"""

import os
import socket
import sys

import requests


def check_langflow(base_url: str, api_key: str | None = None) -> bool:
    """Verify Langflow API is responding."""
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        resp = requests.get(f"{base_url}/health", headers=headers, timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def check_valkey(host: str = "localhost", port: int = 6379) -> bool:
    """Verify Valkey is responding to PING."""
    try:
        sock = socket.create_connection((host, port), timeout=2)
        try:
            sock.sendall(b"PING\r\n")
            response = sock.recv(64)
            return b"PONG" in response
        finally:
            sock.close()
    except (socket.error, OSError):
        return False


def main() -> None:
    base_url = os.environ.get("LANGFLOW_BASE_URL", "http://127.0.0.1:7860")
    api_key = os.environ.get("LANGFLOW_API_KEY")
    valkey_host = os.environ.get("VALKEY_HOST", "localhost")
    valkey_port = int(os.environ.get("VALKEY_PORT", "6379"))

    langflow_ok = check_langflow(base_url, api_key)
    valkey_ok = check_valkey(valkey_host, valkey_port)

    print(f"Langflow ({base_url}): {'✓ healthy' if langflow_ok else '✗ unreachable'}")
    print(f"Valkey ({valkey_host}:{valkey_port}): {'✓ healthy' if valkey_ok else '✗ unreachable'}")

    if not (langflow_ok and valkey_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
