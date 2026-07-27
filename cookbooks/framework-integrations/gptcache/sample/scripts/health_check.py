#!/usr/bin/env python3
"""Health check: verify Valkey connectivity and search module availability."""

import sys

import valkey


def main():
    client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

    # Basic connectivity
    response = client.ping()
    print(f"PING: {response}")

    # Backend detection via INFO SERVER
    info = client.info("server")
    server_name = info.get("server_name", "unknown")
    version = info.get("server_version", info.get("redis_version", "unknown"))
    print(f"Backend: {server_name} {version}")

    # Check search module availability
    try:
        result = client.execute_command("FT._LIST")
        print(f"FT._LIST: OK (indexes: {result})")
    except valkey.ResponseError as e:
        print(f"FT._LIST: FAILED - {e}")
        sys.exit(1)

    print("\nAll checks passed.")
    client.close()


if __name__ == "__main__":
    main()
