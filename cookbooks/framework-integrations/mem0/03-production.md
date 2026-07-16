# Production Configuration for Mem0 + Valkey

> Configure Mem0 for authenticated, encrypted Valkey deployments without coupling the application to one cloud provider.

**Advanced** · Python · ~20 min

**Who is this for:** Engineers moving a local Mem0 integration into a managed or self-hosted Valkey deployment.

## Prerequisites

- Docker or Podman for local verification
- Python 3.9 or newer
- A Valkey deployment with the Search module
- A certificate and authentication policy for non-local connections

## Step 1: Configure the Connection

Keep connection details outside source code:

```python
import os

from mem0 import Memory

memory = Memory.from_config(
    {
        "vector_store": {
            "provider": "valkey",
            "config": {
                "valkey_url": os.environ["VALKEY_URL"],
                "collection_name": os.environ.get("MEM0_COLLECTION", "production_memories"),
                "embedding_model_dims": int(os.environ["EMBEDDING_DIMENSIONS"]),
                "index_type": os.environ.get("MEM0_INDEX_TYPE", "hnsw"),
                "hnsw_m": int(os.environ.get("MEM0_HNSW_M", "16")),
                "hnsw_ef_construction": int(
                    os.environ.get("MEM0_HNSW_EF_CONSTRUCTION", "200")
                ),
                "hnsw_ef_runtime": int(
                    os.environ.get("MEM0_HNSW_EF_RUNTIME", "10")
                ),
            },
        }
    }
)
```

Use a `valkeys://` URL or the equivalent TLS settings supported by the Valkey Python client when TLS is required by the deployment.

> **Security:** Do not put passwords, tokens, or private keys in cookbook files,
> shell history, or committed environment files. Enable TLS and authentication
> for every connection that leaves localhost. See the [Valkey security
> documentation](https://valkey.io/topics/security/).

## Step 2: Choose Index Settings

Mem0 supports HNSW and FLAT indexes through its Valkey provider:

| Setting | Default | Effect |
| --- | --- | --- |
| `index_type` | `hnsw` | Selects approximate HNSW search or exact FLAT search. |
| `hnsw_m` | `16` | Controls graph connections per layer. |
| `hnsw_ef_construction` | `200` | Controls construction-time search width. |
| `hnsw_ef_runtime` | `10` | Controls query-time search width. |
| `embedding_model_dims` | Required | Must match the configured embedding model output. |

Benchmark representative data and queries before changing defaults. A larger graph or search width changes resource use and query behavior; it is not a universal performance improvement.

## Step 3: Use a Provider-Neutral Deployment

The application only needs a Valkey URL and a Search-capable deployment. The
same Mem0 configuration shape can be used with self-hosted Valkey or a managed
Valkey service. Provider-specific networking, certificates, secret storage,
backups, and failover settings belong in the deployment documentation for that
service.

For LLM-backed fact extraction, choose a supported Mem0 provider separately
from the Valkey configuration. OpenAI, Ollama, and other providers are
optional alternatives; the default sample remains local and uses `infer=False`.

## Step 4: Plan Lifecycle Operations

Use Mem0's API for application operations:

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

Define a retention policy for each scope. Use Mem0 deletion methods for
application-level removal and keep collection/index cleanup as an
administrative operation. Verify backup, restore, and index-rebuild procedures
against the actual Valkey deployment before relying on them.

Set `infer=True` only after configuring a supported LLM provider and its
credentials. The local sample keeps `infer=False` so it remains deterministic
and credential-free.

## Configuration Reference

| Environment variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VALKEY_URL` | Yes | - | Authenticated Valkey URL, such as `valkeys://host:6379`. |
| `MEM0_COLLECTION` | No | `production_memories` | Mem0 collection and Valkey index name. |
| `EMBEDDING_DIMENSIONS` | Yes | - | Output dimension of the selected embedder. |
| `MEM0_INDEX_TYPE` | No | `hnsw` | `hnsw` or `flat`. |
| `MEM0_HNSW_M` | No | `16` | HNSW graph connectivity. |
| `MEM0_HNSW_EF_CONSTRUCTION` | No | `200` | HNSW construction width. |
| `MEM0_HNSW_EF_RUNTIME` | No | `10` | HNSW query width. |

## Teardown

Before deleting a collection, confirm retention and backup requirements. For local sample resources:

```bash
docker compose -f cookbooks/framework-integrations/mem0/sample/docker-compose.yml down
```

---

[<- 02 - Multi-User Memory](02-multi-user-memory.md)
