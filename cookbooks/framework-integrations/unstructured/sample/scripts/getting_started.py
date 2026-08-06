#!/usr/bin/env python3
"""Getting Started: Verify Valkey connectivity and Search module availability.

Demonstrates the same connection pattern used by the unstructured-ingest
Valkey destination connector. Requires Valkey running on localhost:6379
with the Search module loaded (valkey/valkey-bundle).
"""

import asyncio
import os
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


async def main():
    """Connect to Valkey, verify ping, and check Search module."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)],
        request_timeout=10000,
    )

    print(f"Connecting to Valkey at {VALKEY_HOST}:{VALKEY_PORT}...")
    client = await GlideClient.create(config)

    try:
        # Step 1: Verify connectivity
        pong = await client.ping()
        print(f"✓ PING → {pong}")

        # Step 2: Check server info
        info = await client.info()
        info_str = info.decode() if isinstance(info, bytes) else str(info)

        # Step 3: Verify Search module is loaded
        if "search" in info_str.lower() or "ft" in info_str.lower():
            print("✓ Search module detected")
        else:
            # Try FT._LIST as a more reliable check
            try:
                from glide import ft
                result = await ft.list(client)
                print("✓ Search module loaded (FT._LIST succeeded)")
            except Exception:
                print("✗ Search module NOT detected — use valkey/valkey-bundle image")
                sys.exit(1)

        print("\n✓ Valkey is ready for document ingestion!")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
