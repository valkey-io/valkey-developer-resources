"""Health check: verify Valkey connectivity, version, and search module."""

import re
import sys

import valkey


def main() -> None:
    client = valkey.Valkey(host="localhost", port=6379)
    try:
        # 1. Ping
        pong = client.ping()
        print(f"1. PING: {'OK' if pong else 'FAILED'}")

        # 2. Server version detection (matches Open WebUI's _check_core_version)
        info = client.info("server")
        version = info.get("valkey_version") or info.get("redis_version", "unknown")
        server_name = info.get("server_name", "unknown")
        print(f"2. Server: {server_name} v{version}")

        # Check minimum version (9.0.1)
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if match:
            ver_tuple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if ver_tuple >= (9, 0, 1):
                print(f"   Version check: PASS (>= 9.0.1)")
            else:
                print(f"   Version check: FAIL (need >= 9.0.1, got {version})")
                sys.exit(1)

        # 3. Search module check (matches Open WebUI's _check_search_module)
        modules = client.module_list()
        search_found = False
        search_version = None
        for mod in modules:
            name = mod.get(b"name") or mod.get("name", b"")
            if isinstance(name, bytes):
                name = name.decode()
            if name.lower() == "search":
                search_found = True
                ver_int = int(mod.get(b"ver") or mod.get("ver", 0))
                search_version = (ver_int // 10000, (ver_int % 10000) // 100, ver_int % 100)
                break

        if search_found:
            ver_str = f"{search_version[0]}.{search_version[1]}.{search_version[2]}"
            print(f"3. Search module: v{ver_str}")
            if search_version >= (1, 2, 0):
                print(f"   Module check: PASS (>= 1.2.0)")
            else:
                print(f"   Module check: FAIL (need >= 1.2.0, got {ver_str})")
                sys.exit(1)
        else:
            print("3. Search module: NOT FOUND")
            sys.exit(1)

        # 4. FT._LIST works
        indices = client.execute_command("FT._LIST")
        print(f"4. FT._LIST: {len(indices)} indices")

        print("\n✓ All checks passed — Valkey is ready for Open WebUI")
    finally:
        client.close()


if __name__ == "__main__":
    main()
