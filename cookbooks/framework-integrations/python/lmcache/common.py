"""Shared helpers for the LMCache + Valkey cookbook notebooks.

Everything here drives **real LMCache code** (verified against ``lmcache==0.5.2``)
against a **real Valkey** server, on CPU — no GPU and no vLLM required:

- ``lmcache.v1.config.load_engine_config_with_overrides`` — the same function
  LMCache calls to parse ``LMCACHE_CONFIG_FILE``.
- ``lmcache.utils.CacheEngineKey`` — the class LMCache's Valkey connector uses
  to build the keys it reads/writes.
- ``lmcache.v1.storage_backend.connector.valkey_connector.ValkeyConnector`` —
  LMCache's **real** Valkey connector. The ``valkey://`` scheme is dispatched to
  it by ``valkey_adapter.py`` (``ValkeyConnectorAdapter``). We drive its
  ``put``/``exists``/``get`` directly with a real KV-cache tensor so you can
  watch a genuine store-and-load cycle through Valkey.

The one thing this does **not** do is run a full vLLM inference server: that
path drives the same ``ValkeyConnector`` from vLLM's GPU KV buffers. See
``03`` for how to wire it up on a Linux host.
"""

from __future__ import annotations

import asyncio
import os

# LMCache logs its entire internal config at INFO on every load, plus a couple
# of benign CPU/standalone notices at WARNING (no accelerator custom ops; no
# distributed controller). Set its log level to ERROR before importing lmcache
# so notebook output stays readable. Raise to INFO to see LMCache's own logs.
os.environ.setdefault("LMCACHE_LOG_LEVEL", "ERROR")

import logging
import torch
from lmcache.utils import CacheEngineKey
from lmcache.v1.config import LMCacheEngineConfig, load_engine_config_with_overrides
from lmcache.v1.memory_management import MemoryFormat
from lmcache.v1.metadata import LMCacheMetadata
from lmcache.v1.storage_backend.connector.valkey_connector import ValkeyConnector
from lmcache.v1.storage_backend.local_cpu_backend import LocalCPUBackend

# LMCache emits a couple of benign runtime notices on CPU (a "device cpu ...
# fallback ops" note and a "Controller message sender is not initialized"
# note — the controller is only used in distributed deployments). Neither
# affects the demo; quiet them so notebook output stays readable.
logging.getLogger("lmcache").setLevel(logging.ERROR)

VALKEY_HOST_DEFAULT = "localhost"
VALKEY_PORT_DEFAULT = 6379

# A small but real KV-cache geometry so the demo runs in seconds on CPU:
# (num_layers, 2, chunk_size_tokens, num_kv_heads, head_dim).
DEMO_MODEL_NAME = "facebook/opt-125m"
DEMO_KV_DTYPE = torch.bfloat16
DEMO_CHUNK_SIZE = 16
DEMO_KV_SHAPE = (2, 2, DEMO_CHUNK_SIZE, 4, 64)


def connection_settings() -> tuple[str, int]:
    """Resolve the (host, port) to connect to from env, with defaults."""
    return (
        os.environ.get("VALKEY_HOST", VALKEY_HOST_DEFAULT),
        int(os.environ.get("VALKEY_PORT", str(VALKEY_PORT_DEFAULT))),
    )


def load_lmcache_config(config_path: str) -> LMCacheEngineConfig:
    """Load an LMCache engine config exactly the way LMCache itself does.

    Real entry point: ``load_engine_config_with_overrides`` — the function that
    ``LMCACHE_CONFIG_FILE`` parsing goes through internally. Raises whatever it
    raises on an invalid config (this is real validation, not a stub).
    """
    return load_engine_config_with_overrides(config_file_path=config_path)


def build_cache_key(
    chunk_hash: int, model_name: str = DEMO_MODEL_NAME
) -> CacheEngineKey:
    """Build the real LMCache key object for a KV chunk.

    Uses LMCache's actual ``CacheEngineKey``. Pass the returned object to the
    connector's ``put``/``get``/``exists``; call ``.to_string()`` to see the
    exact Valkey wire-key (``{model}@{world}@{worker}@{hash}@{dtype}``).
    """
    return CacheEngineKey(
        model_name=model_name,
        world_size=1,
        worker_id=0,
        chunk_hash=chunk_hash,
        dtype=DEMO_KV_DTYPE,
    )


async def make_backend_and_connector(
    host: str | None = None,
    port: int | None = None,
    model_name: str = DEMO_MODEL_NAME,
) -> tuple[LocalCPUBackend, ValkeyConnector]:
    """Construct a real LMCache CPU backend + real ValkeyConnector on CPU.

    This is the exact connector vLLM drives in production; here we build it
    standalone so it can be exercised without a GPU. Requires the
    ``valkey-glide-sync`` package (the connector's sync client). Call from an
    async context (or a notebook cell with top-level ``await``) so the connector
    binds to the running event loop.
    """
    env_host, env_port = connection_settings()
    host = host if host is not None else env_host
    port = port if port is not None else env_port
    loop = asyncio.get_running_loop()

    config = LMCacheEngineConfig.from_defaults()
    config.local_cpu = True
    metadata = LMCacheMetadata(
        model_name=model_name,
        world_size=1,
        local_world_size=1,
        worker_id=0,
        local_worker_id=0,
        kv_dtype=DEMO_KV_DTYPE,
        kv_shape=DEMO_KV_SHAPE,
        chunk_size=DEMO_CHUNK_SIZE,
    )
    cpu_backend = LocalCPUBackend(config=config, metadata=metadata)
    connector = ValkeyConnector(
        host=host,
        port=port,
        loop=loop,
        local_cpu_backend=cpu_backend,
        num_workers=2,
    )
    return cpu_backend, connector


def make_kv_tensor(cpu_backend: LocalCPUBackend, connector: ValkeyConnector):
    """Allocate a real MemoryObj sized to the connector's fixed chunk shape and
    fill it with deterministic data. Returns (memory_obj, original_copy).

    The connector uses single-key, fixed-size storage: a stored value must match
    ``connector.meta_shapes[0]`` or a GET is treated as a miss. Allocating with
    that exact shape is what a real KV-cache chunk would use.
    """
    shape = connector.meta_shapes[0]
    mem = cpu_backend.allocate(shape, DEMO_KV_DTYPE, MemoryFormat.KV_2LTD)
    if mem is None:
        raise RuntimeError("LocalCPUBackend.allocate returned None")
    # Deterministic content so readback comparison is meaningful.
    filler = torch.arange(mem.tensor.numel(), dtype=torch.float32).reshape(
        tuple(mem.tensor.shape)
    )
    mem.tensor.copy_(filler.to(DEMO_KV_DTYPE))
    return mem, mem.tensor.clone()
