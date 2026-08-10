# Getting Started with MetaGPT + Valkey

> Map the proposed MetaGPT RAG configuration for Valkey, then run a standalone sample that exercises the same Valkey behavior today.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building or evaluating multi-agent LLM workflows who want a Valkey-backed RAG vector store, and who want to see the proposed MetaGPT integration's exact Valkey
behavior without waiting for it to merge.

## What is MetaGPT + Valkey?

[MetaGPT](https://github.com/FoundationAgents/MetaGPT) is a multi-agent framework that assigns roles (product manager, architect, engineer) to LLMs so they collaborate on complex tasks like a software
company. Its RAG module supports pluggable vector stores through a `ConfigBasedFactory` pattern — the same pattern used by FAISS, Chroma, and Elasticsearch.

> MetaGPT is a [FoundationAgents](https://github.com/FoundationAgents) open-source project. It was previously hosted at `geekan/MetaGPT`; that URL now redirects to the FoundationAgents organization.

Valkey plugs in as a **RAG vector store**: document embeddings are stored as JSON documents and indexed with HNSW or FLAT vector indexes, so MetaGPT agents can run KNN similarity search — optimized
for low latency — to ground their work in your own data.

The integration uses the **synchronous** `valkey-glide` client (the `glide_sync` module, shipped as the `valkey-glide-sync` package) to stay consistent with MetaGPT's other synchronous RAG backends.
There is no `await` or `asyncio` anywhere in the data path.

> **Upstream status:** The Valkey RAG backend is proposed in upstream pull request [FoundationAgents/MetaGPT#2063](https://github.com/FoundationAgents/MetaGPT/pull/2063), which is **open and
unreviewed** at the time of writing. It is not yet part of any published `metagpt` release. This cookbook and its sample code independently reproduce the verified Valkey behavior from that PR — the
same `FT.CREATE` schema, key prefix pattern, and atomic batch semantics — without importing MetaGPT. Steps 2 and 4 below describe the proposed MetaGPT configuration and API shape for reference against
the PR; the [`sample/`](sample/) directory is the runnable path in this cookbook today.

## Prerequisites

- Docker or Podman installed
- Python 3.10+ (required by this sample's pinned `llama-index-core` version; see [Step 2](#step-2-understand-the-samples-dependencies))
- An embedding model only if a future merged MetaGPT release supports this workflow (OpenAI, Azure, or a local model configured in MetaGPT). The standalone `sample/` code needs no API key — it uses a
deterministic local embedding function.

## Step 1: Start Valkey with the Search Module

The vector store requires the **valkey-search** module for indexing and similarity queries, plus the **valkey-json** module for storing documents as JSON. The `valkey-bundle` image includes both:

```bash
# Docker
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

```bash
# Or Podman
podman run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> To remove an existing container on re-run: `docker rm -f valkey` (or `podman rm -f valkey`)
>
> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/) and [03 - Production](03-production.md).

Verify it's running and the search module is loaded:

```bash
docker exec valkey valkey-cli PING
# PONG

docker exec valkey valkey-cli MODULE LIST
# Should include "search" and "json" in the output
```

## Step 2: Understand the Sample's Dependencies

The Valkey RAG backend proposed in [PR #2063](https://github.com/FoundationAgents/MetaGPT/pull/2063) is **not yet part of the published `metagpt` package on PyPI**, and per this repository's
contribution guidelines a sample must never require building unreleased software. So this cookbook's [`sample/`](sample/) does not install `metagpt` at all — it depends only on published packages that
let it reproduce the same Valkey behavior:

- `valkey-glide-sync` — the **synchronous** GLIDE client (module `glide_sync`); this is the client the vector store actually uses
- `llama-index-core` — provides the `TextNode` / `VectorStoreQuery` / `BaseNode` shapes that MetaGPT's RAG module already builds on. **This is why the sample requires Python 3.10+**: the current
`llama-index-core` release (`0.14.23`) raised its minimum Python version above the `<0.11.0` line the archived version of this cookbook used, which still supported Python 3.9.

> **Note**: The package is `valkey-glide-sync` but the import is `glide_sync` (the async package `valkey-glide` imports as `glide`). The synchronous client exposes the same API surface without
coroutines, so no call is `await`ed.

Once PR #2063 merges and MetaGPT publishes a release with the Valkey RAG extra, the canonical install for using it *through MetaGPT itself* would become `pip install "metagpt[rag]"`, which pulls in
`valkey-glide-sync` transitively. Until then, this cookbook's sample gives you the same Valkey behavior standalone — see [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py), which
reimplements the documented `ValkeyVectorStore` methods directly against `glide_sync`.

## Step 3: Verify the Connection

This snippet confirms the synchronous client can reach Valkey and that the search module is loaded. Note there is no `await` — `GlideClient.create()` returns a connected client directly.

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

## Step 4: How MetaGPT Would Be Configured to Use Valkey

This section maps the proposed configuration surface from [PR #2063](https://github.com/FoundationAgents/MetaGPT/pull/2063), for reference against the PR. **It describes MetaGPT's own config file,
not the standalone sample** — since MetaGPT isn't installed, this step is descriptive, not runnable. MetaGPT reads connection settings from `config/config2.yaml`; the proposed integration would add a
`valkey` section (shipped commented-out in the PR's `config2.example.yaml`):

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

For the exact runtime behavior these fields would drive — schema, batch writes, KNN query construction — see the standalone, independently runnable [`sample/`](sample/) below and
[02 - Vector Store for RAG](02-vector-store-rag.md), which exercise the same logic against real Valkey today.

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

This diagram shows the real upstream integration, where `ValkeyVectorStore` subclasses llama-index's `BasePydanticVectorStore` so it plugs into MetaGPT's `RAGIndexFactory` / `RAGRetrieverFactory`.
This cookbook's standalone [`sample/valkey_vector_store.py`](sample/valkey_vector_store.py) reproduces the same `glide_sync` → Valkey Server layers below it, without the MetaGPT/llama-index factory
layers above it (since MetaGPT is not installed).

| Component | Purpose | Valkey Features Used |
| --- | --- | --- |
| `ValkeyVectorStore` | Store embeddings + KNN search | `FT.CREATE`, `FT.SEARCH`, `JSON.SET` |
| `ValkeyIndexConfig` | Build a `VectorStoreIndex` over Valkey | `FT.CREATE` |
| `ValkeyRetrieverConfig` | Retrieve nodes by similarity | `FT.SEARCH` |

## Try It: The Runnable Sample

The [`sample/`](sample/) directory contains a fully standalone, runnable reimplementation of `ValkeyVectorStore`'s create/add/query/delete/drop mechanics against real Valkey — no MetaGPT install, no
API key, no network access required beyond Valkey itself. This is the only runnable path in this cookbook until PR #2063 is merged and published:

```bash
cd sample
pip install -r requirements.txt
python main.py
```

See [`sample/README.md`](sample/README.md) for details, environment variables, and testing instructions.

---

[← README](README.md) | [02 - Vector Store for RAG →](02-vector-store-rag.md)
