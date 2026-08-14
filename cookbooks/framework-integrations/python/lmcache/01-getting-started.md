# Getting Started with LMCache + Valkey

> Load a real LMCache config, connect to Valkey, and store a KV cache chunk under LMCache's actual key format — no GPU required.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers who want to understand exactly what LMCache writes to Valkey before deploying the full vLLM + GPU pipeline.

[LMCache](https://github.com/LMCache/LMCache) is a KV cache management layer for LLM inference
engines (vLLM, SGLang). Instead of recomputing attention key/value tensors for every request,
LMCache stores them externally and reloads them when the same (or prefix-matching) prompt appears
again. Valkey serves as the remote (L2) storage backend for these cached tensors.

> **Scope note:** Driving LMCache through a real inference request requires vLLM on a Linux
> machine with an NVIDIA GPU. This cookbook does not run that pipeline. Instead, it uses LMCache's
> own config-loading and key-generation code (`lmcache==0.5.2`) against a real Valkey server, so
> you can see exactly what LMCache would write — verifiable on any laptop, no GPU needed.

## Prerequisites

- Docker or Podman installed
- Python 3.10 or newer (LMCache requires `>=3.10,<3.14`)
- No API keys, GPU, or paid services needed

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:8.1.1
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Dependencies

```bash
pip install lmcache==0.5.2 valkey-glide==2.5.0
```

`lmcache` pulls in `torch` (CPU build is sufficient — no CUDA needed for anything in this cookbook).

## Step 3: Write an LMCache Configuration

Create `lmcache_config.yaml`:

```yaml
chunk_size: 256
local_cpu: true
max_local_cpu_size: 5.0
remote_url: "valkey://localhost:6379"
remote_serde: "naive"
extra_config:
  valkey_num_workers: 4
```

This is the config LMCache reads from the `LMCACHE_CONFIG_FILE` environment variable when it starts. It configures:

- **chunk_size**: KV cache is split into 256-token chunks for storage
- **local_cpu / max_local_cpu_size**: an in-process CPU cache (L1) capped at 5 GB
- **remote_url**: Valkey as the L2 backend, addressed via the `valkey://` scheme
- **remote_serde**: serialization format for KV tensors (`naive` or `cachegen`)

## Step 4: Load the Config with LMCache's Real Loader

```python
from lmcache.v1.config import load_engine_config_with_overrides

config = load_engine_config_with_overrides(config_file_path="lmcache_config.yaml")
print(config.chunk_size)     # 256
print(config.remote_url)     # valkey://localhost:6379
print(config.extra_config)   # {'valkey_num_workers': 4}
```

`load_engine_config_with_overrides` is the same function LMCache calls internally to parse `LMCACHE_CONFIG_FILE` — this isn't a reimplementation, it's the real parser validating your config.

## Step 5: Build LMCache's Real Valkey Key

LMCache's Valkey connector keys every stored chunk with `lmcache.utils.CacheEngineKey`. Building one directly shows you exactly what lands in Valkey:

```python
import torch
from lmcache.utils import CacheEngineKey

key = CacheEngineKey(
    model_name="Qwen/Qwen3-8B",
    world_size=1,
    worker_id=0,
    chunk_hash=0x75bcd15,
    dtype=torch.float16,
)
print(key.to_string())
# Qwen/Qwen3-8B@1@0@75bcd15@half
```

The format is `{model_name}@{world_size}@{worker_id}@{chunk_hash_hex}@{dtype}`. In a real
deployment, `chunk_hash` comes from hashing a tokenized prefix chunk — this cookbook's sample code
(`common.py`) uses a simpler deterministic hash of the prompt text so it doesn't need a tokenizer
or model download, while still using the real `CacheEngineKey` class to build the key string.

## Step 6: Store and Retrieve a Chunk

```python
import asyncio
from glide import (
    AdvancedGlideClientConfiguration,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
)

async def main():
    client = await GlideClient.create(
        GlideClientConfiguration(
            addresses=[NodeAddress("localhost", 6379)],
            request_timeout=5000,
            advanced_config=AdvancedGlideClientConfiguration(connection_timeout=5000),
        )
    )
    try:
        key_str = key.to_string()
        await client.set(key_str, b"...simulated KV tensor bytes...")
        print(await client.exists([key_str]))  # 1 — cache hit
        print(await client.get(key_str))        # the bytes back
    finally:
        await client.close()

asyncio.run(main())
```

> GLIDE's default `request_timeout` is 250ms — fine for a local demo, but worth setting explicitly
> once you're pointing at a real network hop. `sample/common.py` sets both timeouts to 5000ms.

## Step 7: Verify with valkey-cli

```bash
docker exec valkey valkey-cli DBSIZE
# (integer) > 0
```

## How It Works

| Component | Role |
| ----------- | ------ |
| `LMCacheEngineConfig` | Parsed from YAML/env, tells LMCache which connector and settings to use |
| `CacheEngineKey` | Builds the Valkey key for a KV cache chunk from model name, worker id, chunk hash, and dtype |
| Valkey (L2) | Stores the serialized chunk bytes under that key; a network-attached backend that persists across requests and engine restarts |

## Configuration Reference

| Key | Default | Description |
| ----- | --------- | -------------- |
| `chunk_size` | 256 | Tokens per KV cache chunk |
| `local_cpu` | true | Enable CPU L1 cache |
| `max_local_cpu_size` | 5.0 | L1 capacity in GB |
| `remote_url` | — | `valkey://host:port` for the L2 backend |
| `remote_serde` | — | Serialization: `naive` (fast) or `cachegen` (compressed) |

## Teardown

```bash
docker rm -f valkey
```

---

[← README](./README.md) | [02 - KV Cache Sharing →](02-kv-cache-sharing.md)
