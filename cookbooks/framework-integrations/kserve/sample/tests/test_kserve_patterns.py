"""Integration tests validating KServe's Valkey usage patterns."""

import hashlib
import struct
import threading
import time

import numpy as np
import pytest
import valkey


class TestConnectivity:
    """Basic connectivity and protocol compatibility."""

    def test_ping(self, valkey_client):
        assert valkey_client.ping() is True

    def test_server_version(self, valkey_client):
        """Valkey 9.1.0+ is used in the KServe samples."""
        info = valkey_client.info("server")
        version = info.get("valkey_version") or info.get("redis_version")
        assert version is not None
        parts = version.split(".")
        major, minor = int(parts[0]), int(parts[1])
        assert (major, minor) >= (9, 1), f"Expected 9.1+, got {version}"

    def test_redis_protocol_compatibility(self, valkey_client):
        """Valkey responds to standard Redis protocol commands (wire compat)."""
        # SET/GET (used by LMCache and Feast)
        valkey_client.set("proto:test", "hello")
        assert valkey_client.get("proto:test") == b"hello"
        valkey_client.delete("proto:test")

        # HSET/HGET (used by Feast)
        valkey_client.hset("proto:hash", mapping={"k1": "v1", "k2": "v2"})
        assert valkey_client.hget("proto:hash", "k1") == b"v1"
        valkey_client.delete("proto:hash")


class TestLMCachePattern:
    """Validate LMCache's ValkeyConnector storage patterns."""

    def test_binary_blob_storage(self, valkey_client, clean_keys, rng):
        """LMCache stores KV cache chunks as binary blobs."""
        # Simulate a realistic chunk size (~2MB for a mid-size model layer)
        chunk = rng.random(256 * 1024, dtype=np.float32).astype(np.float16).tobytes()  # 512KB
        key = "model@0@0@abcdef1234567890@half"

        valkey_client.set(key, chunk)
        retrieved = valkey_client.get(key)
        assert retrieved == chunk
        assert len(retrieved) == 512 * 1024

    def test_key_naming_convention(self, valkey_client, clean_keys):
        """LMCache keys follow: model@worker@layer@hash@dtype."""
        model = "meta-llama/Llama-3.2-1B-Instruct"
        keys_written = []
        for worker in range(2):
            for layer in range(4):
                token_hash = hashlib.sha256(
                    f"tokens_w{worker}_l{layer}".encode()
                ).hexdigest()[:16]
                key = f"{model}@{worker}@{layer}@{token_hash}@half"
                valkey_client.set(key, b"\x00" * 64)
                keys_written.append(key)

        # Pattern scan for this model's chunks
        found = valkey_client.keys(f"{model}@*")
        assert len(found) == 8  # 2 workers × 4 layers

    def test_idempotent_writes(self, valkey_client, clean_keys, rng):
        """Multiple replicas writing same chunk produce same key (idempotent)."""
        chunk = rng.random(1024, dtype=np.float32).astype(np.float16).tobytes()
        # Same content hash → same key regardless of which pod writes it
        content_hash = hashlib.sha256(chunk).hexdigest()[:16]
        key = f"model@0@0@{content_hash}@half"

        # Two "replicas" write the same key
        valkey_client.set(key, chunk)
        valkey_client.set(key, chunk)  # Second write is idempotent

        assert valkey_client.get(key) == chunk

    def test_concurrent_replica_writes(self, valkey_client, clean_keys, rng):
        """Concurrent writes from multiple threads don't corrupt data."""
        results = {}
        errors = []

        def write_chunk(replica_id: int) -> None:
            c = valkey.Valkey(host="localhost", port=6379)
            try:
                for layer in range(4):
                    key = f"model@{replica_id}@{layer}@concurrent_test@half"
                    data = rng.random(512, dtype=np.float32).astype(np.float16).tobytes()
                    c.set(key, data)
                    results[f"{replica_id}:{layer}"] = len(data)
            except Exception as e:
                errors.append(str(e))
            finally:
                c.close()

        threads = [threading.Thread(target=write_chunk, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent writes: {errors}"
        assert len(results) == 16  # 4 replicas × 4 layers

    def test_cache_hit_retrieval(self, valkey_client, clean_keys, rng):
        """Simulate cache hit: store then retrieve the same chunk."""
        chunk = rng.random(2048, dtype=np.float32).astype(np.float16).tobytes()
        content_hash = hashlib.sha256(chunk).hexdigest()[:16]
        key = f"model@0@0@{content_hash}@half"

        # First request: store
        valkey_client.set(key, chunk)

        # Second request: cache hit
        cached = valkey_client.get(key)
        assert cached is not None
        assert cached == chunk

    def test_ttl_for_cache_eviction(self, valkey_client, clean_keys):
        """TTL can be used for automatic cache eviction."""
        key = "model@0@0@ttl_test@half"
        valkey_client.set(key, b"temp_chunk", ex=2)  # 2 second TTL

        assert valkey_client.get(key) is not None
        assert valkey_client.ttl(key) > 0
        assert valkey_client.ttl(key) <= 2


class TestPrefixCacheIndex:
    """Validate the EPP's shared prefix-cache block index patterns."""

    def test_block_to_pod_mapping(self, valkey_client, clean_keys):
        """Store and retrieve block_hash → pod_ip mappings."""
        mappings = {
            "idx:block_hash_aaa": "10.0.1.10",
            "idx:block_hash_bbb": "10.0.1.11",
            "idx:block_hash_ccc": "10.0.1.10",
        }
        for key, pod_ip in mappings.items():
            valkey_client.set(key, pod_ip)

        # Routing lookup
        result = valkey_client.get("idx:block_hash_aaa")
        assert result == b"10.0.1.10"

    def test_index_update_on_eviction(self, valkey_client, clean_keys):
        """When a pod evicts a block, its index entry is removed."""
        valkey_client.set("idx:evict_block", "10.0.1.10")
        assert valkey_client.exists("idx:evict_block") == 1

        # Pod evicts the block
        valkey_client.delete("idx:evict_block")
        assert valkey_client.exists("idx:evict_block") == 0

    def test_index_bulk_update(self, valkey_client, clean_keys):
        """Bulk index updates via pipeline (efficient for batch events)."""
        pipe = valkey_client.pipeline()
        for i in range(100):
            block_hash = hashlib.sha256(f"block_{i}".encode()).hexdigest()
            pod_ip = f"10.0.1.{10 + (i % 5)}"
            pipe.set(f"idx:{block_hash}", pod_ip)
        pipe.execute()

        # Verify count
        keys = valkey_client.keys("idx:*")
        assert len(keys) == 100

    def test_pod_failure_cleanup(self, valkey_client, clean_keys):
        """Simulate pod failure: remove all entries for a specific pod."""
        # Populate
        for i in range(20):
            pod_ip = f"10.0.1.{10 + (i % 3)}"
            valkey_client.set(f"idx:block_{i}", pod_ip)

        # Pod 10.0.1.12 fails — remove its entries
        cursor = 0
        removed = 0
        while True:
            cursor, keys = valkey_client.scan(cursor, match="idx:*", count=50)
            for key in keys:
                if valkey_client.get(key) == b"10.0.1.12":
                    valkey_client.delete(key)
                    removed += 1
            if cursor == 0:
                break

        assert removed > 0  # Some entries belonged to the failed pod
        # Remaining entries should not reference the failed pod
        for key in valkey_client.keys("idx:*"):
            assert valkey_client.get(key) != b"10.0.1.12"


class TestFeastPattern:
    """Validate Feast's online store access patterns against Valkey."""

    def test_feature_materialization(self, valkey_client, clean_keys, rng):
        """Feast materializes features as HASH entries."""
        entity_key = "feast:project:user_features:user_001"
        features = {
            "age": "25",
            "purchase_count": "42",
            "avg_session_mins": "15.3",
            "embedding": rng.random(8, dtype=np.float32).tobytes(),
        }
        valkey_client.hset(entity_key, mapping=features)

        result = valkey_client.hgetall(entity_key)
        assert result[b"age"] == b"25"
        assert result[b"purchase_count"] == b"42"
        assert len(result[b"embedding"]) == 32  # 8 × 4 bytes

    def test_batch_feature_retrieval(self, valkey_client, clean_keys):
        """Feast reads features for multiple entities via pipeline."""
        # Materialize
        for i in range(10):
            valkey_client.hset(f"feast:proj:features:entity_{i}", mapping={
                "f1": str(i * 1.1),
                "f2": str(i * 2.2),
            })

        # Batch read (how Feast reads at inference time)
        pipe = valkey_client.pipeline()
        for i in range(10):
            pipe.hgetall(f"feast:proj:features:entity_{i}")
        results = pipe.execute()

        assert len(results) == 10
        for r in results:
            assert b"f1" in r
            assert b"f2" in r

    def test_feature_update(self, valkey_client, clean_keys):
        """Re-materialization overwrites existing features."""
        key = "feast:proj:features:entity_update"
        valkey_client.hset(key, mapping={"f1": "1.0", "f2": "2.0"})
        assert valkey_client.hget(key, "f1") == b"1.0"

        # Re-materialize with new values
        valkey_client.hset(key, mapping={"f1": "9.9", "f2": "8.8"})
        assert valkey_client.hget(key, "f1") == b"9.9"

    def test_missing_entity_returns_empty(self, valkey_client, clean_keys):
        """Non-existent entity returns empty dict (not error)."""
        result = valkey_client.hgetall("feast:proj:features:nonexistent")
        assert result == {}
