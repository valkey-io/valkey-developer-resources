"""CI tests for the LMCache + Valkey cookbook.

All CPU-only (no GPU, no vLLM), against a real local Valkey server (started by
CI or ``docker compose up``). Mirrors what the notebooks do:

1. Real LMCache config loading (``load_engine_config_with_overrides``).
2. Real LMCache key generation (``CacheEngineKey`` via ``common.build_cache_key``).
3. A real KV-tensor round trip through LMCache's real ``ValkeyConnector``
   (store -> exists -> get, byte-identical), including cross-instance sharing.
4. The MP-mode adapter config through its real parser.
"""

from __future__ import annotations

import tempfile

import pytest
import torch

import common


def _write_yaml(text: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        return f.name


class TestConfigLoading:
    def test_standalone_config_loads(self):
        path = _write_yaml(
            'chunk_size: 256\n'
            'local_cpu: true\n'
            'remote_url: "valkey://localhost:6379"\n'
            'remote_serde: "naive"\n'
        )
        config = common.load_lmcache_config(path)
        assert config.remote_url == "valkey://localhost:6379"
        assert config.remote_serde == "naive"

    def test_cluster_config_loads(self):
        path = _write_yaml(
            'chunk_size: 256\n'
            'local_cpu: true\n'
            'remote_url: "valkey://localhost:6379"\n'
            'remote_serde: "cachegen"\n'
            'extra_config:\n'
            '  valkey_mode: "cluster"\n'
            '  valkey_num_workers: 32\n'
        )
        config = common.load_lmcache_config(path)
        assert config.extra_config["valkey_mode"] == "cluster"

    def test_malformed_config_rejected(self):
        # LMCache's loader parses YAML; malformed YAML raises.
        path = _write_yaml("chunk_size: [unclosed\n")
        with pytest.raises(Exception):
            common.load_lmcache_config(path)


class TestCacheKey:
    def test_key_format(self):
        key = common.build_cache_key(chunk_hash=0x75BCD15)
        assert key.to_string() == "facebook/opt-125m@1@0@75bcd15@bfloat16"

    def test_same_hash_same_key(self):
        # Cross-instance sharing depends on identical inputs -> identical key.
        a = common.build_cache_key(chunk_hash=0xABC)
        b = common.build_cache_key(chunk_hash=0xABC)
        assert a.to_string() == b.to_string()


class TestMPAdapterConfig:
    def test_mp_adapter_parses(self):
        from lmcache.v1.distributed.l2_adapters.valkey_l2_adapter import (
            ValkeyL2AdapterConfig,
        )

        cfg = ValkeyL2AdapterConfig.from_dict(
            {"type": "valkey", "startup_nodes": "localhost:6379", "cluster_mode": True}
        )
        assert cfg is not None


@pytest.mark.asyncio
async def test_real_valkey_round_trip():
    """Store a real KV tensor through LMCache's ValkeyConnector and read it back."""
    cpu, conn = await common.make_backend_and_connector()
    try:
        mem, original = common.make_kv_tensor(cpu, conn)
        key = common.build_cache_key(chunk_hash=0x1234)
        await conn.put(key, mem)
        assert await conn.exists(key) is True
        got = await conn.get(key)
        assert got is not None
        assert torch.equal(got.tensor.to(torch.float32), original.to(torch.float32))
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_cross_instance_sharing():
    """A chunk stored by one connector is a hit for an independent connector."""
    key = common.build_cache_key(chunk_hash=0xCAFE)

    cpu_a, worker_a = await common.make_backend_and_connector()
    try:
        mem_a, original = common.make_kv_tensor(cpu_a, worker_a)
        await worker_a.put(key, mem_a)
    finally:
        await worker_a.close()

    cpu_b, worker_b = await common.make_backend_and_connector()
    try:
        assert await worker_b.exists(key) is True
        got = await worker_b.get(key)
        assert got is not None
        assert torch.equal(got.tensor.to(torch.float32), original.to(torch.float32))
    finally:
        await worker_b.close()
