# Production with Mem0 + Valkey

> Configure Mem0 for production Valkey deployments, then apply provider-specific settings when needed.

**Advanced** · Python · ~20 min

**Who is this for:** Engineers moving a local Mem0 integration into a managed or self-hosted Valkey deployment.

## Prerequisites

- Docker for local verification
- Python 3.10 or newer
- A Valkey deployment with the Search module
- A certificate and authentication policy for non-local connections

## Step 1: Provider-Neutral Valkey Configuration

Keep the application configuration independent of a specific cloud provider:

```python
import os

from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": os.environ["VALKEY_URL"],
            "collection_name": os.environ.get("MEM0_COLLECTION", "prod_memories"),
            "embedding_model_dims": int(os.environ.get("EMBEDDING_DIMENSIONS", "768")),
            "index_type": os.environ.get("MEM0_INDEX_TYPE", "hnsw"),
            "hnsw_m": int(os.environ.get("MEM0_HNSW_M", "16")),
            "hnsw_ef_construction": int(
                os.environ.get("MEM0_HNSW_EF_CONSTRUCTION", "200")
            ),
            "hnsw_ef_runtime": int(
                os.environ.get("MEM0_HNSW_EF_RUNTIME", "10")
            ),
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": os.environ.get("MEM0_LLM_MODEL", "llama3.2"),
            "ollama_base_url": os.environ.get(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ),
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": os.environ.get("MEM0_EMBEDDER_MODEL", "nomic-embed-text"),
            "embedding_dims": int(os.environ.get("EMBEDDING_DIMENSIONS", "768")),
            "ollama_base_url": os.environ.get(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ),
        },
    },
}

memory = Memory.from_config(config)
```

The selected embedder's output dimension must match `EMBEDDING_DIMENSIONS`.
Ollama is the default local provider; other providers can be substituted with
their documented Mem0 configuration without changing the Valkey configuration.
The credential-free sample remains local and uses `infer=False`.

This same configuration works with a self-hosted Valkey deployment or a
managed Valkey service. Set `VALKEY_URL` to the endpoint supplied by the
deployment, use an authenticated `valkeys://` URL for remote connections, and
follow that provider's documentation for networking, certificates, and access
control.

> **Security:** Do not put passwords, tokens, or private keys in cookbook files,
> shell history, or committed environment files. Enable TLS and authentication
> for every connection that leaves localhost. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Step 2: HNSW Parameter Tuning

| Parameter | Default | Effect | Recommendation |
| --- | --- | --- | --- |
| `hnsw_m` | 16 | More connections = higher recall, more memory | 16 for most cases, 32 for large stores |
| `hnsw_ef_construction` | 200 | Higher = better index quality, slower build | 200 default, increase for critical apps |
| `hnsw_ef_runtime` | 10 | Higher = better recall, higher latency | 10 for speed, 50+ for maximum recall |
| `index_type` | hnsw | HNSW is approximate, FLAT is exact | HNSW for larger stores, FLAT for small sets |

Benchmark representative data and queries before changing defaults.

## Step 3: Monitoring

```python
import valkey

client = valkey.from_url("valkeys://your-cluster:6379")

try:
    info = client.execute_command("FT.INFO", "prod_memories")
    print(info)

    mem_info = client.info("memory")
    print(f"Used: {mem_info['used_memory_human']}")

    results = client.execute_command(
        "FT.SEARCH", "prod_memories",
        "@user_id:{alice}",
        "LIMIT", "0", "0",
    )
    print(f"Alice has {results[0]} memories")
finally:
    client.close()
```

Use the Mem0 API for application operations and reserve direct Search commands
for operational inspection:

```python
memory.add(
    [{"role": "user", "content": "The support policy is documented."}],
    user_id="support-agent",
    infer=False,
)

results = memory.search(
    "Where is the support policy documented?",
    filters={"user_id": "support-agent"},
)
```

## Production Checklist

| Area | Recommendation |
| --- | --- |
| Deployment | Use a Search-capable Valkey service and keep the application provider-neutral |
| TLS | Use the `valkeys://` URL scheme for encrypted connections |
| Multi-AZ | Enable it for high availability |
| HNSW M | 16 default, increase after benchmarking |
| Embedding model | Match the index dimensions to the selected embedder |
| Memory limits | Use `maxmemory-policy` to handle a full deployment |
| Monitoring | Track `FT.INFO` for index size and memory usage |

The Mem0 Valkey connector and configuration are documented in
[valkey.py](https://github.com/mem0ai/mem0/blob/main/mem0/vector_stores/valkey.py)
and
[ValkeyConfig](https://github.com/mem0ai/mem0/blob/main/mem0/configs/vector_stores/valkey.py).

## Configuration Reference

| Environment variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_URL` | Yes | - | Authenticated Valkey URL, such as `valkeys://host:6379`. |
| `EMBEDDING_DIMENSIONS` | No | `768` | Output dimension of the selected embedder. |
| `MEM0_LLM_MODEL` | No | `llama3.2` | Ollama model used for Mem0 fact extraction. |
| `MEM0_EMBEDDER_MODEL` | No | `nomic-embed-text` | Ollama embedding model. Must match `EMBEDDING_DIMENSIONS`. |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama service endpoint. |
| `MEM0_COLLECTION` | No | `prod_memories` | Mem0 collection and Valkey index name. |
| `MEM0_INDEX_TYPE` | No | `hnsw` | `hnsw` or `flat`. |
| `MEM0_HNSW_M` | No | `16` | HNSW graph connectivity. |
| `MEM0_HNSW_EF_CONSTRUCTION` | No | `200` | HNSW construction width. |
| `MEM0_HNSW_EF_RUNTIME` | No | `10` | HNSW query width. |

---

[<- 02 - Multi-User Memory](02-multi-user-memory.md)
