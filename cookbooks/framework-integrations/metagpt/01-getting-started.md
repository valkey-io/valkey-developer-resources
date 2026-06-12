# Getting Started with MetaGPT + Valkey

**Beginner** · Python · ~15 min

## What is MetaGPT + Valkey?

[MetaGPT](https://github.com/geekan/MetaGPT) is a multi-agent framework that assigns roles (product manager, architect, engineer) to LLMs so they collaborate on complex tasks like a software company. Its RAG module supports pluggable vector stores through a `ConfigBasedFactory` pattern — the same pattern used by FAISS, Chroma, and Elasticsearch.

Valkey plugs in as a **RAG vector store**: document embeddings are stored as JSON documents and indexed with HNSW or FLAT vector indexes, so MetaGPT agents can run sub-millisecond KNN similarity search to ground their work in your own data.

The integration uses the **synchronous** `valkey-glide` client (the `glide_sync` module, shipped as the `valkey-glide-sync` package) to stay consistent with MetaGPT's other synchronous RAG backends. There is no `await` or `asyncio` anywhere in the data path.

## Prerequisites

- Python 3.9–3.11 (MetaGPT requires `<3.12`)
- Docker or Podman (for running Valkey)
- An embedding model (OpenAI, Azure, or a local model configured in MetaGPT)

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries, plus the **valkey-json** module for storing documents as JSON. The `valkey-bundle` image includes both:

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
# Or Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" and "json" in the output
```

## Step 2: Install MetaGPT with Valkey RAG Support

The Valkey backend is currently in review and is **not yet part of the published `metagpt` package on PyPI**. Until the integration is merged and released, install MetaGPT from the feature branch:

```bash
# Install MetaGPT (with the RAG extra) from the Valkey feature branch
pip install "metagpt[rag] @ git+https://github.com/daric93/MetaGPT.git@feat/valkey-rag-vector-store"
```

> **Temporary install source**: this points at a personal fork branch (`daric93/MetaGPT@feat/valkey-rag-vector-store`) because the Valkey backend is not yet merged upstream. Branch refs can be force-pushed, so for a reproducible build pin to a specific commit instead: `git+https://github.com/daric93/MetaGPT.git@<commit-sha>`. Once the integration lands in `geekan/MetaGPT` and ships to PyPI, the canonical install becomes `pip install "metagpt[rag]"`.

The `rag` extra pulls in both Valkey GLIDE clients used by the backend:

- `valkey-glide-sync>=2.1.0,<3.0.0` — the **synchronous** client (module `glide_sync`); this is the one the vector store actually uses
- `valkey-glide>=2.1.0,<3.0.0` — the async client, pulled in for compatibility

It also brings in `llama-index-core` (the `0.10.x` line, which `ValkeyVectorStore` builds on via `BasePydanticVectorStore`) transitively, so you do not need to install it separately. The sample's `requirements.txt` pins it explicitly only so the standalone `sample/main.py` can import `TextNode` / `VectorStoreQuery` without MetaGPT present.

> **Note**: The package is `valkey-glide-sync` but the import is `glide_sync` (the async package `valkey-glide` imports as `glide`). The synchronous client exposes the same API surface without coroutines, so no call is `await`ed.

## Step 3: Verify the Connection

This snippet confirms the synchronous client can reach Valkey and that the search module is loaded. Note there is no `await` — `GlideClient.create()` returns a connected client directly.

> ⚠️ These examples connect without authentication for local development. Always enable authentication and TLS for production deployments.

```python
"""Quick connectivity check using the synchronous GLIDE client."""
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ft

config = GlideClientConfiguration(
    addresses=[NodeAddress(host="localhost", port=6379)],
    client_name="metagpt_rag_client",
    request_timeout=5000,  # 5s — GLIDE defaults to 250ms, too low for non-local hops
)

client = GlideClient.create(config)  # synchronous: no await
try:
    print(f"Valkey says: {client.ping()}")  # b"PONG"

    # Confirm the search module is loaded (required for the vector store)
    indexes = ft.list(client)
    print(f"Search module loaded! ({len(indexes)} indexes found)")
    print("Connected successfully!")
finally:
    client.close()
```

## Step 4: Configure MetaGPT to Use Valkey

MetaGPT reads connection settings from `config/config2.yaml`. Add a `valkey` section (it ships commented-out in `config2.example.yaml`):

```yaml
# config/config2.yaml
valkey:
  host: "localhost"
  port: 6379
  password: ""              # leave empty for local; set for auth-enabled servers
  use_tls: false            # set true for any non-local deployment
  request_timeout: 5000     # milliseconds — tune for network latency
  index_name: "metagpt_rag"
  prefix: "metagpt:rag:"
  vector_dimensions: 1536   # must match your embedding model's output dim
  distance_metric: "COSINE" # COSINE, L2, or IP
  vector_algorithm: "HNSW"  # HNSW (fast, approximate) or FLAT (exact)
```

The `vector_dimensions` value must match your embedding model. `1536` is the output dimension of OpenAI `text-embedding-3-small` / `text-embedding-ada-002`; change it if you use a different model.

## Step 5: Understand the Architecture

```text
┌───────────────────────────────────────────────────┐
│                MetaGPT RAG Engine                 │
├─────────────────────────┬─────────────────────────┤
│     RAGIndexFactory     │   RAGRetrieverFactory   │
│   (ValkeyIndexConfig)   │ (ValkeyRetrieverConfig) │
├─────────────────────────┴─────────────────────────┤
│                 ValkeyVectorStore                 │
│    (BasePydanticVectorStore from llama-index)     │
├───────────────────────────────────────────────────┤
│          glide_sync client (synchronous)          │
├───────────────────────────────────────────────────┤
│       Valkey Server + Search + JSON modules       │
└───────────────────────────────────────────────────┘
```

| Component | Purpose | Valkey Features Used |
|-----------|---------|----------------------|
| `ValkeyVectorStore` | Store embeddings + KNN search | `FT.CREATE`, `FT.SEARCH`, `JSON.SET` |
| `ValkeyIndexConfig` | Build a `VectorStoreIndex` over Valkey | `FT.CREATE` |
| `ValkeyRetrieverConfig` | Retrieve nodes by similarity | `FT.SEARCH` |

[Next: 02 Vector Store for RAG →](02-vector-store-rag.md)
