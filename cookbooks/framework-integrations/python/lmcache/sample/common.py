"""Shared helpers for the LMCache + Valkey cookbook sample.

Wraps two pieces of real LMCache code (verified against lmcache==0.5.2, the
version pinned in requirements.txt):

- ``lmcache.v1.config.load_engine_config_with_overrides`` — the same
  function LMCache itself calls to parse ``LMCACHE_CONFIG_FILE``.
- ``lmcache.utils.CacheEngineKey`` — the same class LMCache's Valkey
  connector uses to build the keys it reads/writes
  (see ``valkey_connector.py``'s calls to ``key.to_string()``).

This sample does not run vLLM or touch a GPU. It exercises the real
LMCache config-loading and key-generation code against a real local Valkey
server so you can see exactly what LMCache writes to Valkey without needing
GPU hardware. Running the full inference pipeline (vLLM + LMCache +
Valkey, end to end) additionally requires an NVIDIA GPU — see
https://docs.lmcache.ai for that walkthrough.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

# LMCache logs its entire internal config (100+ fields, most irrelevant to
# this cookbook) at INFO level on every config load. Quiet it to WARNING by
# default for readable sample output; override with LMCACHE_LOG_LEVEL=INFO
# to see the full dump. Must be set before the lmcache imports below, since
# lmcache.logging.init_logger reads this env var at module import time.
os.environ.setdefault("LMCACHE_LOG_LEVEL", "WARNING")

import torch
from glide import (
    AdvancedGlideClientConfiguration,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)
from lmcache.utils import CacheEngineKey
from lmcache.v1.config import load_engine_config_with_overrides

VALKEY_HOST_DEFAULT = "localhost"
VALKEY_PORT_DEFAULT = 6379
REQUEST_TIMEOUT_MS = 5000

# Matches LMCache's own dtype string used in cache keys (see
# TORCH_DTYPE_TO_STR_DTYPE in lmcache/utils.py); float16 -> "half".
DEMO_DTYPE = torch.float16


def connection_settings() -> tuple[str, int]:
    """Read Valkey connection overrides at call time."""
    return (
        os.environ.get("VALKEY_HOST", VALKEY_HOST_DEFAULT),
        int(os.environ.get("VALKEY_PORT", str(VALKEY_PORT_DEFAULT))),
    )


def resolve_connection(host: str | None = None, port: int | None = None) -> tuple[str, int]:
    """Resolve the (host, port) to connect to.

    An explicitly passed host/port always wins; anything left as ``None``
    falls back to the VALKEY_HOST/VALKEY_PORT env vars (or their defaults).
    """
    env_host, env_port = connection_settings()
    return (
        host if host is not None else env_host,
        port if port is not None else env_port,
    )


async def create_client(
    host: str | None = None,
    port: int | None = None,
    use_tls: bool = False,
) -> GlideClient:
    """Create a GLIDE client with bounded timeouts.

    Defaults to VALKEY_HOST/VALKEY_PORT env vars when host/port aren't given
    explicitly.
    """
    host, port = resolve_connection(host, port)
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host, port)],
        use_tls=use_tls,
        request_timeout=REQUEST_TIMEOUT_MS,
        advanced_config=AdvancedGlideClientConfiguration(
            connection_timeout=REQUEST_TIMEOUT_MS,
        ),
    )
    return await GlideClient.create(config)


def load_lmcache_config(config_path: str | Path) -> Any:
    """Load an LMCache engine config the same way LMCache itself does.

    Real entry point: ``lmcache.v1.config.load_engine_config_with_overrides``
    — the function ``LMCACHE_CONFIG_FILE`` parsing goes through internally.
    Raises whatever ``load_engine_config_with_overrides`` raises on an
    invalid config (this is real validation, not a stub).
    """
    return load_engine_config_with_overrides(config_file_path=str(config_path))


def chunk_hash(prompt: str) -> int:
    """Deterministic stand-in for LMCache's real prefix chunk hash.

    LMCache computes chunk hashes over *tokenized* prefixes (see
    ``lmcache/v1/token_database.py``'s ``_hash_tokens`` / ``_prefix_hash``),
    which requires a real tokenizer and model. This demo hashes the raw
    prompt text instead so it doesn't need a model download — the point
    here is the Valkey key *format* LMCache uses
    (``CacheEngineKey.to_string()``), not exact hash-algorithm parity with
    LMCache's token-level chunking.
    """
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def cache_key(
    model_name: str,
    prompt: str,
    worker_id: int = 0,
    world_size: int = 1,
) -> str:
    """Build the real Valkey wire-key LMCache's connector would use for this chunk.

    Uses LMCache's actual ``CacheEngineKey`` class, so the string this
    returns is byte-for-byte what ``ValkeyConnector`` would use as a Valkey
    key for a KV cache chunk with these parameters.
    """
    key = CacheEngineKey(
        model_name=model_name,
        world_size=world_size,
        worker_id=worker_id,
        chunk_hash=chunk_hash(prompt),
        dtype=DEMO_DTYPE,
    )
    return key.to_string()


_HOST_PATTERN = re.compile(r"^[\w.\-]+(:(\d{1,5}))?$")
_HOSTNAME_ONLY_PATTERN = re.compile(r"^[\w.\-]+$")


def _valid_port(port_str: str) -> bool:
    return port_str.isdigit() and 1 <= int(port_str) <= 65535


def parse_host(host: str) -> tuple[str, str]:
    """Parse a ``host:port`` string, defaulting port to 6379.

    Raises:
        ValueError: If host contains characters unsafe for YAML/JSON
            interpolation, or the port is outside the valid 1-65535 range.
    """
    match = _HOST_PATTERN.match(host)
    if not match:
        raise ValueError(f"Invalid host format: {host!r}")
    port = match.group(2)
    if port is not None and not _valid_port(port):
        raise ValueError(f"Invalid port in host {host!r}: must be 1-65535")
    if ":" in host:
        addr, port = host.rsplit(":", 1)
        return addr, port
    return host, "6379"


def parse_startup_nodes(nodes: str) -> str:
    """Validate an MP-mode ``startup_nodes`` string: one or more comma-separated
    ``host:port`` entries. Returns the input unchanged if valid.

    Every entry MUST include a port — LMCache's own parser
    (``_parse_startup_nodes`` in
    ``lmcache/v1/distributed/l2_adapters/valkey_l2_adapter.py``) rejects a
    bare hostname with no port: ``"startup_nodes entry must be 'host:port',
    got {chunk!r}"``. This validator matches that grammar exactly rather
    than the looser ``parse_host`` grammar used for the legacy YAML configs
    (which does default a missing port to 6379).

    This value gets embedded, unescaped, into an example shell command
    printed to the user (``lmcache server --l2-adapter '<json>'``) — unlike
    the legacy YAML configs, there's no separate templating step to catch an
    unsafe value, so it's validated strictly before use.

    Raises:
        ValueError: If any entry is missing a port, malformed, or a port is
            out of range.
    """
    entries = [entry.strip() for entry in nodes.split(",")]
    if not entries or any(not entry for entry in entries):
        raise ValueError(f"Invalid startup_nodes: {nodes!r}")
    for entry in entries:
        addr, sep, port = entry.rpartition(":")
        if not sep or not addr or not _HOSTNAME_ONLY_PATTERN.match(addr) or not _valid_port(port):
            raise ValueError(f"Invalid startup_nodes entry (must be 'host:port'): {entry!r}")
    return nodes
