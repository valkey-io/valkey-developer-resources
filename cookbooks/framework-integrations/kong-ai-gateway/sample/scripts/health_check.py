"""Health check: verify Valkey is ready for Kong AI Gateway's semantic plugins."""

import os
import sys

import valkey


def _has_module(modules: list, name: str) -> bool:
    """Check if a named module is loaded."""
    for mod in modules:
        mod_name = mod.get(b"name") or mod.get("name", b"")
        if isinstance(mod_name, bytes):
            mod_name = mod_name.decode()
        if mod_name.lower() == name.lower():
            return True
    return False


def main() -> None:
    host = os.environ.get("VALKEY_HOST", "localhost")
    port = int(os.environ.get("VALKEY_PORT", "6379"))
    client = valkey.Valkey(host=host, port=port)
    try:
        # 1. Ping
        pong = client.ping()
        print(f"1. PING: {'OK' if pong else 'FAILED'}")

        # 2. Server detection (Kong checks INFO server for server_name)
        info = client.info("server")
        server_name = info.get("server_name", "unknown")
        version = info.get("valkey_version") or info.get("redis_version", "unknown")
        print(f"2. Server: {server_name} v{version}")
        if server_name == "valkey":
            print("   Auto-detection: Kong will use Valkey-specific driver ✓")
        else:
            print("   Auto-detection: Kong will use Redis driver")

        # 3. Search module check (needed for FT.CREATE/FT.SEARCH)
        modules = client.module_list()
        search_found = _has_module(modules, "search")
        print(f"3. Search module: {'loaded ✓' if search_found else 'NOT FOUND'}")
        if not search_found:
            sys.exit(1)

        # 4. JSON module check (needed for JSON.SET)
        json_found = _has_module(modules, "json")
        print(f"4. JSON module: {'loaded ✓' if json_found else 'NOT FOUND'}")
        if not json_found:
            sys.exit(1)

        # 5. FT._LIST works
        indices = client.execute_command("FT._LIST")
        print(f"5. FT._LIST: {len(indices)} indices")

        print("\n✓ All checks passed — Valkey is ready for Kong AI Gateway")
    finally:
        client.close()


if __name__ == "__main__":
    main()
