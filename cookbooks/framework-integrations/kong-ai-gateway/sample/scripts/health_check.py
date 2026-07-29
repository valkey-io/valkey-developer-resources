"""Health check: verify Valkey is ready for Kong AI Gateway's semantic plugins."""

import sys

import valkey


def main() -> None:
    client = valkey.Valkey(host="localhost", port=6379)
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
        search_found = False
        for mod in modules:
            name = mod.get(b"name") or mod.get("name", b"")
            if isinstance(name, bytes):
                name = name.decode()
            if name.lower() == "search":
                search_found = True
                break
        print(f"3. Search module: {'loaded ✓' if search_found else 'NOT FOUND'}")
        if not search_found:
            sys.exit(1)

        # 4. JSON module check (needed for JSON.SET)
        json_found = False
        for mod in modules:
            name = mod.get(b"name") or mod.get("name", b"")
            if isinstance(name, bytes):
                name = name.decode()
            if name.lower() == "json":
                json_found = True
                break
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
