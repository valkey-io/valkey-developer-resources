"""Health check: verify Valkey connectivity and protocol compatibility for KServe patterns."""

import sys
import time

import valkey


def main() -> None:
    client = valkey.Valkey(host="localhost", port=6379)
    try:
        # 1. Ping
        pong = client.ping()
        print(f"1. PING: {'OK' if pong else 'FAILED'}")

        # 2. Server version
        info = client.info("server")
        version = info.get("valkey_version") or info.get("redis_version", "unknown")
        server_name = info.get("server_name", "unknown")
        print(f"2. Server: {server_name} v{version}")

        # 3. LMCache pattern: SET/GET binary blob
        test_key = "test@0@0@12345@half"
        test_value = b"\x00" * 1024  # 1KB binary blob
        client.set(test_key, test_value)
        retrieved = client.get(test_key)
        assert retrieved == test_value
        client.delete(test_key)
        print("3. Binary SET/GET: OK (LMCache pattern)")

        # 4. Feast pattern: HSET/HGET for feature vectors
        feature_key = "feast:my_project:user_features:user_123"
        client.hset(feature_key, mapping={"f1": "0.5", "f2": "1.2", "f3": "0.8"})
        features = client.hgetall(feature_key)
        assert len(features) == 3
        client.delete(feature_key)
        print("4. HSET/HGET: OK (Feast pattern)")

        # 5. Pipeline support (bulk feature reads)
        pipe = client.pipeline()
        for i in range(10):
            pipe.set(f"bulk:{i}", f"value-{i}")
        pipe.execute()
        pipe = client.pipeline()
        for i in range(10):
            pipe.get(f"bulk:{i}")
        results = pipe.execute()
        assert len(results) == 10
        # Cleanup
        client.delete(*[f"bulk:{i}" for i in range(10)])
        print("5. Pipeline: OK (batch reads)")

        # 6. SCAN pattern (cache inspection — production-safe)
        client.set("model@0@0@aaa@half", b"chunk1")
        client.set("model@0@1@bbb@half", b"chunk2")
        keys = list(client.scan_iter("model@*"))
        assert len(keys) == 2
        client.delete("model@0@0@aaa@half", "model@0@1@bbb@half")
        print("6. SCAN pattern: OK (cache inspection)")

        print("\n✓ All checks passed — Valkey is ready for KServe workloads")
    finally:
        client.close()


if __name__ == "__main__":
    main()
