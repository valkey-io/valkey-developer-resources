# Semantic Search with LangChain + Valkey

> Store documents with deterministic local embeddings and retrieve related values through `ValkeyStore`.

**Intermediate** · Python · ~20 min

**Who is this for:** This page is for developers who need namespace-scoped
similarity search in a local LangGraph or LangChain integration without sending
text to an embedding provider.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start from the sample directory.
- Python 3.10 or newer and the pinned requirements installed.
- Docker Compose with `valkey/valkey-bundle:9.1.1` running.

```bash
cd cookbooks/framework-integrations/langchain/sample
docker compose up -d
python -m pip install -r requirements.txt
```

## Step 1: Create the local embedding provider

The sample's `DeterministicEmbeddings` class maps known words to four-dimensional vectors. It is intentionally small and repeatable; it is not a general-purpose language model.

```python
from main import DeterministicEmbeddings

embeddings = DeterministicEmbeddings()
dimensions = embeddings.dimensions
```

## Step 2: Configure `ValkeyStore`

`create_store` uses this public constructor and calls `setup()` before the first write:

```python
from langgraph_checkpoint_aws import ValkeyStore
from main import Settings, create_valkey_client

settings = Settings.from_env()
client = create_valkey_client(settings)
store = ValkeyStore(
    client=client,
    index={
        "collection_name": settings.store_collection_name,
        "dims": dimensions,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "distance_metric": "COSINE",
    },
    ttl={"default_ttl": settings.store_ttl_minutes},
)
store.setup()
```

The collection name, embedding dimensions, indexed field, index type, distance
metric, and TTL match `main.py`. An existing collection must use the same
embedding dimensions and index schema; use a new `VALKEY_STORE_COLLECTION`
value when changing providers or dimensions.

## Step 3: Put and search documents

The following block continues from Step 1 and Step 2, so `settings`, `client`,
`embeddings`, and `store` are already initialized.

`ValkeyStore.put` and `ValkeyStore.search` use a tuple namespace, a string key, and a value containing the indexed `text` field:

```python
store.put(
    ("help-desk", "passwords"),
    "password-1",
    {
        "text": "How do I reset my password?",
        "answer": "Use the password reset page.",
    },
)

store.put(
    ("help-desk", "vpn"),
    "vpn-1",
    {
        "text": "How do I connect to the VPN?",
        "answer": "Download the VPN client from the IT portal.",
    },
)

results = store.search(
    ("help-desk",),
    query="I forgot my password.",
    limit=5,
)

for result in results:
    print(result.value)
```

The namespace prefix returns both documents, while a search rooted at
`("help-desk", "passwords")` sees only the password document. Use a separate
top-level namespace for each tenant or application boundary.

The production-shaped sample helper accepts the same values as separate arguments:

This block also reuses the `store` created in Step 2:

```python
from main import run_store_demo

results = run_store_demo(
    store,
    namespace=("help-desk", "passwords"),
    query="I forgot my password.",
    documents=[
        (
            "password-2",
            {
                "text": "How do I reset my password?",
                "answer": "Use the password reset page.",
            },
        )
    ],
)
```

## Step 4: Run and verify semantic search

Run the complete local flow and the integration tests:

```bash
python main.py
python -m pytest -q test_langchain.py
```

The demo prints a `semantic search:` result and then removes the run-specific store data. The tests also verify namespace isolation and the store TTL.

## HNSW tuning

`ValkeyStore` accepts the standard HNSW settings in its index configuration.
Tune them only after measuring the quality and resource tradeoff for the
application's own documents:

| Option | Effect |
| --- | --- |
| `hnsw_m` | Connections per graph node; higher values use more index memory. |
| `hnsw_ef_construction` | Search width while building the index. |
| `hnsw_ef_runtime` | Search width for each query. |

```python
# This continues the configured client and embeddings from Step 2.
store = ValkeyStore(
    client=client,
    index={
        "collection_name": "tuned_store",
        "dims": embeddings.dimensions,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "distance_metric": "COSINE",
        "hnsw_m": 24,
        "hnsw_ef_construction": 300,
        "hnsw_ef_runtime": 20,
    },
)
store.setup()
```

## Step 5: Apply search safety rules

Choose namespaces and collection names that isolate applications or tenants.
Review which document fields are indexed and retained, avoid placing secrets or
unnecessary personal data in searchable values, and protect the Valkey service
with an approved network boundary, authentication, and TLS when it is not a
loopback-only development service.

## How It Works

`ValkeyStore` embeds the `text` field on `put`, writes the document, and uses
the configured HNSW index to compare an embedded query during `search`.
`store.setup()` creates or validates the collection before writes.
`STORE_TTL_MINUTES` controls the default document lifetime, while
`VALKEY_STORE_NAMESPACE` supplies the sample's namespace prefix.

Under the hood, setup and search can use Valkey Search and JSON lifecycle
operations, and store cleanup can scan keys owned by the configured namespace.
Those are implementation notes; application code should call
`ValkeyStore.setup`, `ValkeyStore.put`, and `ValkeyStore.search`.

## Configuration Reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `VALKEY_URL` | `valkey://127.0.0.1:6379` when unset | Full Valkey URL; takes precedence over host and port. |
| `VALKEY_HOST` | `127.0.0.1` | Host fallback when `VALKEY_URL` is unset. |
| `VALKEY_PORT` | `6379` | Port fallback when `VALKEY_URL` is unset. |
| `VALKEY_SOCKET_TIMEOUT` | `5.0` | Socket and connection timeout in seconds. |
| `CHECKPOINT_TTL_SECONDS` | `3600` | Checkpoint lifetime in seconds. |
| `CACHE_TTL_SECONDS` | `300` | Default exact-cache lifetime in seconds. |
| `STORE_TTL_MINUTES` | `60` | Default store lifetime in minutes. |
| `VALKEY_CACHE_PREFIX` | `langchain:cache:` | Prefix used by `ValkeyCache`. |
| `VALKEY_STORE_COLLECTION` | `langchain_store_idx` | Search collection used by `ValkeyStore`. |
| `VALKEY_STORE_NAMESPACE` | `langchain-cookbook` | Namespace prefix used by the sample store. |

## Optional Bedrock addendum

The default path uses `DeterministicEmbeddings` and needs no provider credentials. An application can supply a provider implementation through the same `create_store` signature:

```python
from langchain_aws import BedrockEmbeddings
from main import create_store

provider_embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-west-2",
)
with create_store(
    settings,
    client=client,
    embeddings=provider_embeddings,
) as provider_store:
    provider_store.put(
        namespace,
        "provider-example",
        {"text": "Provider-backed embedding example."},
    )
```

This addendum requires an extra compatible provider package, AWS credentials
and permissions, and a collection whose schema matches the provider's
embedding dimensions. It is not part of the default requirements or commands.

## Teardown

Close clients used by direct snippets and remove the local Valkey service:

```python
client.close()
```

```bash
docker compose down --volumes
```

---

[Previous: 02 - LLM Response Caching](02-llm-caching.md) | [Back to LangChain + Valkey](README.md) | [Next: 04 - Full Local Composition](04-full-agent.md)
