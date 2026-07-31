#!/usr/bin/env python3
"""Health check: verify Valkey is running with the valkey-search module loaded."""

from __future__ import annotations

import asyncio
import sys

from glide import GlideClient, GlideClientConfiguration, NodeAddress


def to_str(value) -> str:
    """Convert bytes or other types to str."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


async def main() -> None:
    config = GlideClientConfiguration(
        addresses=[NodeAddress("localhost", 6379)],
        client_name="dify_health_check",
        request_timeout=5000,
    )

    try:
        client = await GlideClient.create(config)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        # Basic connectivity
        pong = await client.ping()
        print(f"PING: {to_str(pong)}")

        # Check server info
        info = to_str(await client.info())
        for line in info.split("\n"):
            if "valkey_version" in line:
                print(f"Server version: {line.strip()}")
                break

        # Check search module
        result = await client.custom_command(["MODULE", "LIST"])
        module_names = []
        for module_info in result:
            if isinstance(module_info, dict):
                # Glide returns list of dicts: [{b'name': b'search', ...}, ...]
                name_val = module_info.get(b"name") or module_info.get("name")
                if name_val:
                    module_names.append(to_str(name_val))
            elif isinstance(module_info, (list, tuple)):
                items = [to_str(x) for x in module_info]
                for i, item in enumerate(items):
                    if item == "name" and i + 1 < len(items):
                        module_names.append(items[i + 1])

        if "search" in module_names:
            print("✅ valkey-search module loaded")
        else:
            print(f"❌ valkey-search module NOT loaded. Modules: {module_names}")
            sys.exit(1)

        print("\n✅ Health check passed — Valkey with search module is ready.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
