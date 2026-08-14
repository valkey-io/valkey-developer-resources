"""CI tests for the LMCache + Valkey cookbook sample.

Covers three layers, all CPU-only (no GPU, no vLLM):

1. Real LMCache config loading (``load_engine_config_with_overrides``)
   for standalone, cluster, TLS/serverless, and invalid configs.
2. Real LMCache key generation (``CacheEngineKey.to_string()`` via
   ``common.cache_key``) — determinism, format, cross-instance sharing.
3. Real Valkey round trips (store/hit/miss) using the same keys, against
   a real local Valkey server (started by CI or docker-compose).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from common import (
    cache_key,
    chunk_hash,
    create_client,
    load_lmcache_config,
    parse_host,
    parse_startup_nodes,
    resolve_connection,
)
from production_deployment import (
    generate_cluster_config,
    generate_mp_l2_adapter,
    generate_serverless_config,
    generate_standalone_config,
    validate_mp_config,
)

MODEL_NAME = "test-model"


def _write_temp_yaml(text: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        return f.name


class TestConfigLoading:
    """LMCache's real config loader must accept every config we generate."""

    def test_standalone_config_loads(self):
        path = _write_temp_yaml(generate_standalone_config("localhost:6379"))
        try:
            config = load_lmcache_config(path)
            assert config.remote_url == "valkey://localhost:6379"
            assert config.remote_serde == "naive"
            assert config.extra_config["valkey_num_workers"] == 8
        finally:
            Path(path).unlink(missing_ok=True)

    def test_cluster_config_loads(self):
        path = _write_temp_yaml(generate_cluster_config("10.0.0.1:7001"))
        try:
            config = load_lmcache_config(path)
            assert config.remote_url == "valkey://10.0.0.1:7001"
            assert config.extra_config["valkey_mode"] == "cluster"
            assert config.extra_config["valkey_num_workers"] == 32
        finally:
            Path(path).unlink(missing_ok=True)

    def test_serverless_config_loads_with_tls(self):
        path = _write_temp_yaml(
            generate_serverless_config("my-cache.serverless.us-east-1.cache.amazonaws.com:6379")
        )
        try:
            config = load_lmcache_config(path)
            assert config.extra_config["tls_enable"] is True
            assert config.extra_config["valkey_mode"] == "cluster"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_malformed_yaml_raises(self):
        """Genuinely unparseable YAML must raise, not silently degrade."""
        path = _write_temp_yaml("chunk_size: [1, 2\n")  # unclosed flow sequence
        try:
            with pytest.raises(Exception):
                load_lmcache_config(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_wrong_typed_value_degrades_with_warning(self):
        """A badly-typed value doesn't raise — LMCache logs a warning and
        falls back to None for that field. This is real LMCache behavior
        (see lmcache/v1/config_base.py), not a gap in this cookbook's config."""
        path = _write_temp_yaml("chunk_size: not_a_number\n")
        try:
            config = load_lmcache_config(path)
            assert config.chunk_size is None
        finally:
            Path(path).unlink(missing_ok=True)


class TestResolveConnection:
    """resolve_connection must honor explicit host/port over env vars.

    Regression test: production_deployment.py's --monitor once ignored its
    own --host argument and silently connected to VALKEY_HOST/VALKEY_PORT
    instead, because create_client() only read env vars. Any caller that
    passes an explicit host/port must have it win.
    """

    def test_explicit_args_win_over_env(self, monkeypatch):
        monkeypatch.setenv("VALKEY_HOST", "env-host")
        monkeypatch.setenv("VALKEY_PORT", "9999")
        assert resolve_connection("explicit-host", 1234) == ("explicit-host", 1234)

    def test_falls_back_to_env_when_not_given(self, monkeypatch):
        monkeypatch.setenv("VALKEY_HOST", "env-host")
        monkeypatch.setenv("VALKEY_PORT", "9999")
        assert resolve_connection() == ("env-host", 9999)

    def test_falls_back_to_defaults_when_neither_given(self, monkeypatch):
        monkeypatch.delenv("VALKEY_HOST", raising=False)
        monkeypatch.delenv("VALKEY_PORT", raising=False)
        assert resolve_connection() == ("localhost", 6379)


class TestHostParsing:
    """Host string validation (CWE-1284: improper validation of specified quantity in input)."""

    def test_parses_host_and_port(self):
        assert parse_host("10.0.0.1:7001") == ("10.0.0.1", "7001")

    def test_defaults_port_when_missing(self):
        assert parse_host("my-cluster.example.com") == ("my-cluster.example.com", "6379")

    def test_rejects_unsafe_characters(self):
        with pytest.raises(ValueError, match="Invalid host format"):
            parse_host('localhost"; extra_config: {evil: true}')

    def test_rejects_out_of_range_port(self):
        with pytest.raises(ValueError, match="Invalid port"):
            parse_host("localhost:99999")


class TestStartupNodes:
    """MP-mode startup_nodes: comma-separated host:port list (CWE-1284/CWE-88).

    This value is embedded, unescaped, into an example shell command printed
    to the user (`lmcache server --l2-adapter '<json>'`), so it needs its
    own validation distinct from parse_host's single-host grammar.
    """

    def test_accepts_single_node(self):
        assert parse_startup_nodes("127.0.0.1:6379") == "127.0.0.1:6379"

    def test_accepts_multiple_nodes(self):
        nodes = "10.0.0.1:7001,10.0.0.2:7002,10.0.0.3:7003"
        assert parse_startup_nodes(nodes) == nodes

    def test_rejects_hostname_without_port(self):
        """LMCache's real _parse_startup_nodes requires a port on every
        entry — unlike parse_host, there's no default-to-6379 fallback."""
        with pytest.raises(ValueError, match="Invalid startup_nodes"):
            parse_startup_nodes("my-cluster.endpoint")

    def test_rejects_shell_metacharacters(self):
        with pytest.raises(ValueError, match="Invalid startup_nodes"):
            parse_startup_nodes("localhost:6379'; rm -rf /; echo '")

    def test_rejects_out_of_range_port_in_list(self):
        with pytest.raises(ValueError, match="Invalid startup_nodes"):
            parse_startup_nodes("10.0.0.1:7001,10.0.0.2:99999")

    def test_rejects_empty_entry(self):
        with pytest.raises(ValueError, match="Invalid startup_nodes"):
            parse_startup_nodes("10.0.0.1:7001,,10.0.0.2:7002")


class TestMpAdapterConfig:
    """MP-mode config is a plain JSON dict — not validated via the engine
    config loader (that's YAML-only), but validated via LMCache's separate
    real ``ValkeyL2AdapterConfig.from_dict`` parser (see ``validate_mp_config``
    and ``TestMpConfigValidation`` below).
    """

    def test_generates_expected_fields(self):
        adapter = generate_mp_l2_adapter("127.0.0.1:6379")
        assert adapter == {
            "type": "valkey",
            "cluster_mode": False,
            "startup_nodes": "127.0.0.1:6379",
            "num_workers": 16,
        }

    def test_cluster_mode_flag(self):
        adapter = generate_mp_l2_adapter("10.0.0.1:7001,10.0.0.2:7002", cluster_mode=True)
        assert adapter["cluster_mode"] is True

    def test_rejects_unsafe_host(self):
        with pytest.raises(ValueError, match="Invalid startup_nodes"):
            generate_mp_l2_adapter("localhost:6379'; echo pwned; '")


class TestMpConfigValidation:
    """Every generated MP config must round-trip through LMCache's real
    ValkeyL2AdapterConfig.from_dict — the MP-mode equivalent of
    TestConfigLoading for the legacy YAML path.
    """

    def test_generated_standalone_adapter_validates(self):
        adapter = generate_mp_l2_adapter("127.0.0.1:6379")
        validate_mp_config(adapter)  # must not raise

    def test_generated_cluster_adapter_validates(self):
        adapter = generate_mp_l2_adapter("10.0.0.1:7001,10.0.0.2:7002", cluster_mode=True)
        validate_mp_config(adapter)  # must not raise

    def test_real_parser_rejects_missing_port(self):
        """Our own generator can't produce this (parse_startup_nodes already
        rejects it), but validate_mp_config must still reject any dict
        that reaches it with a portless startup_nodes entry, since it's
        LMCache's real parser doing the rejecting, not ours."""
        with pytest.raises(ValueError, match="host:port"):
            validate_mp_config({"type": "valkey", "startup_nodes": "my-cluster.endpoint"})


class TestProductionDeploymentCli:
    """The --mode mp --cluster-mode flag must actually reach the generator.

    Regression test: the cookbook docs show `--l2-adapter '{"cluster_mode":
    true, ...}'`, but the CLI originally had no way to set cluster_mode from
    the command line at all — the doc's example was unreproducible by any
    real invocation of this script. Exercises the actual CLI via subprocess,
    the same way a reader would run it.
    """

    def test_cluster_mode_flag_reaches_cli_output(self):
        result = subprocess.run(
            [sys.executable, "production_deployment.py", "--mode", "mp",
             "--host", "my-cluster.endpoint:6379", "--cluster-mode"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert '"cluster_mode": true' in result.stdout

    def test_host_defaults_to_env_vars_when_not_passed(self):
        env = {**os.environ, "VALKEY_HOST": "env-configured-host", "VALKEY_PORT": "9999"}
        result = subprocess.run(
            [sys.executable, "production_deployment.py", "--mode", "standalone"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert "env-configured-host:9999" in result.stdout


class TestCacheKey:
    """Real LMCache CacheEngineKey wire format, via common.cache_key."""

    def test_deterministic_for_same_prompt(self):
        key1 = cache_key(MODEL_NAME, "hello world")
        key2 = cache_key(MODEL_NAME, "hello world")
        assert key1 == key2

    def test_different_for_different_prompts(self):
        key1 = cache_key(MODEL_NAME, "hello world")
        key2 = cache_key(MODEL_NAME, "goodbye world")
        assert key1 != key2

    def test_key_format_matches_lmcache_wire_format(self):
        key = cache_key(MODEL_NAME, "hello world", worker_id=0, world_size=1)
        # Real LMCache format: {model_name}@{world_size}@{worker_id}@{chunk_hash_hex}@{dtype_str}
        parts = key.split("@")
        assert len(parts) == 5
        assert parts[0] == MODEL_NAME
        assert parts[1] == "1"
        assert parts[2] == "0"
        assert parts[4] == "half"  # torch.float16 -> "half" per lmcache.utils

    def test_different_worker_ids_produce_different_keys(self):
        key_a = cache_key(MODEL_NAME, "shared prompt", worker_id=0)
        key_b = cache_key(MODEL_NAME, "shared prompt", worker_id=1)
        assert key_a != key_b

    def test_chunk_hash_is_deterministic(self):
        assert chunk_hash("same text") == chunk_hash("same text")
        assert chunk_hash("same text") != chunk_hash("different text")


class TestValkeyRoundTrip:
    """Real Valkey store/hit/miss using LMCache's real key format.

    Each test wraps its own async body in ``asyncio.run`` rather than using
    pytest-asyncio, so the sample doesn't need an extra test dependency
    beyond what the rest of this repo's cookbooks already use.
    """

    def test_store_and_hit(self):
        async def _run():
            valkeyClient = await create_client()
            try:
                key = cache_key(MODEL_NAME, "round trip test prompt")
                payload = b"\x00\x01\x02" * 100
                await valkeyClient.set(key, payload)
                assert await valkeyClient.exists([key])
                retrieved = await valkeyClient.get(key)
                assert retrieved == payload
                await valkeyClient.delete([key])
            finally:
                await valkeyClient.close()

        asyncio.run(_run())

    def test_miss_for_unstored_key(self):
        async def _run():
            valkeyClient = await create_client()
            try:
                key = cache_key(MODEL_NAME, "never stored prompt")
                assert not await valkeyClient.exists([key])
                assert await valkeyClient.get(key) is None
            finally:
                await valkeyClient.close()

        asyncio.run(_run())

    def test_cross_client_sharing(self):
        """Two independent clients computing the same key share the same chunk."""

        async def _run():
            client_a = await create_client()
            try:
                client_b = await create_client()
                try:
                    key = cache_key(MODEL_NAME, "shared across instances")
                    payload = b"shared-kv-chunk"
                    await client_a.set(key, payload)

                    # client_b never talked to client_a directly, only to Valkey.
                    assert await client_b.exists([key])
                    assert await client_b.get(key) == payload

                    await client_a.delete([key])
                finally:
                    await client_b.close()
            finally:
                await client_a.close()

        asyncio.run(_run())
