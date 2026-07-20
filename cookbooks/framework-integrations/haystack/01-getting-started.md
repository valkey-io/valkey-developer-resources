# Getting Started with Haystack + Valkey

> Connect Haystack to Valkey, store documents with embeddings, and run a vector similarity search.

**Beginner** · Python · ~10 min

**Who is this for:** Python developers learning how to use Valkey Search through Haystack's document-store and retriever APIs.

Haystack represents content as `Document` objects. The `valkey-haystack`
integration stores those documents and their embeddings in Valkey Search, then
returns ranked Haystack documents from a vector query.

## Prerequisites

- Python 3.10 or newer
- Docker or Podman
- A shell in the repository root
- No API key or model download for the deterministic sample path

The commands below use the pinned `valkey/valkey-bundle:9.1.1` image. It
includes the Valkey Search module required by `ValkeyDocumentStore`.

## Step 1: Start Valkey

Start a local Valkey Bundle container:

```bash
docker run -d --name haystack-valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.1
```

With Podman, use the equivalent command:

```bash
podman run -d --name haystack-valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.1
```

> **Security:** This local example uses no authentication or TLS. For any non-localhost deployment, enable authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

Wait for the service, then verify that the Search module is loaded:

```bash
until docker exec haystack-valkey valkey-cli ping | grep -q PONG; do sleep 1; done
docker exec haystack-valkey valkey-cli MODULE LIST
```

> **Note:** The document store creates its Search index when the first
> documents are written. An empty database is expected before that write.

## Step 2: Install Dependencies

The sample pins the integration, Haystack, the official Valkey client, and
the test runner:

```bash
cd cookbooks/framework-integrations/haystack/sample
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

The `valkey-haystack` package provides `ValkeyDocumentStore` and
`ValkeyEmbeddingRetriever` as Haystack components.

## Step 3: Connect to ValkeyDocumentStore

The document store's embedding dimension must match every document and query
embedding written to or searched in the index:

```python
from main import build_store

document_store = build_store()
try:
    print(document_store.count_documents())
finally:
    document_store.close()
```

For a direct configuration, the integration accepts host and port tuples:

```python
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="my_documents",
    embedding_dim=4,
    distance_metric="cosine",
    metadata_fields={"category": str},
    request_timeout=5000,
)
try:
    print(document_store.count_documents())
finally:
    document_store.close()
```

## Step 4: Write Documents

Haystack documents can carry content, metadata, and an embedding. The sample
uses deterministic vectors so this operation is reproducible:

```python
from main import build_documents, build_store

document_store = build_store()
try:
    document_store.delete_all_documents()
    documents = build_documents()
    written = document_store.write_documents(documents)
    print(f"Indexed {written} documents")
finally:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
```

## Step 5: Embed Documents

For a local model-backed workflow, use Haystack's document embedder and write
the returned documents. This optional path downloads a model and is not
needed by the deterministic sample:

```python
from haystack import Document
from haystack.document_stores.types import DuplicatePolicy
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore
from main import build_documents
from haystack.components.embedders import SentenceTransformersDocumentEmbedder

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="haystack_model_documents",
    embedding_dim=768,
    distance_metric="cosine",
    metadata_fields={"category": str},
    request_timeout=5000,
)
documents = [
    Document(content=document.content, meta=document.meta)
    for document in build_documents()
]

try:
    doc_embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-mpnet-base-v2"
    )
    doc_embedder.warm_up()
    docs_with_embeddings = doc_embedder.run(documents)["documents"]
    document_store.write_documents(
        docs_with_embeddings, policy=DuplicatePolicy.OVERWRITE
    )
finally:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
```

The model's vector dimension must match `embedding_dim`; the
`all-mpnet-base-v2` model used above produces 768-dimensional vectors. This
optional block also requires the `sentence-transformers` package and a model
download. Use the fixed vectors in `sample/main.py` when a model download is
not suitable for local or CI runs.

## Step 6: Run a Similarity Search

Pass a query embedding to the Haystack retriever. The integration performs the
Valkey Search query and returns Haystack documents:

```python
from main import build_documents, build_retriever, build_store, query_embedding

document_store = build_store()
try:
    document_store.delete_all_documents()
    document_store.write_documents(build_documents())

    retriever = build_retriever(document_store)
    results = retriever.run(query_embedding("valkey search"))
    for document in results["documents"]:
        print(f"{document.id}: {document.content}")
finally:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
```

Metadata filters are passed to the integration rather than implemented as
client-side filtering:

```python
from main import build_documents, build_retriever, build_store, query_embedding

document_store = build_store()
try:
    document_store.delete_all_documents()
    document_store.write_documents(build_documents())
    results = build_retriever(document_store).run(
        query_embedding("retrieval"),
        filters={"field": "meta.category", "operator": "==", "value": "search"},
    )
    print([document.id for document in results["documents"]])
finally:
    try:
        document_store.delete_all_documents()
    finally:
        document_store.close()
```

## How It Works

| Component | Role |
| --- | --- |
| Haystack `Document` | Carries content, metadata, and an embedding through the pipeline. |
| `ValkeyDocumentStore` | Writes documents and manages the Valkey Search index. |
| `ValkeyEmbeddingRetriever` | Sends a query embedding and optional filters to the integration. |
| Valkey Search | Stores the vector index and returns nearest documents. |

## Configuration Reference

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `nodes_list` | Yes | - | Host and port tuples for the Valkey nodes. |
| `VALKEY_HOST` | No | `localhost` | Host used by the sample's `nodes_list`. |
| `VALKEY_PORT` | No | `6379` | Port used by the sample's `nodes_list`. |
| `VALKEY_REQUEST_TIMEOUT_MS` | No | `5000` | Request timeout passed to the Valkey client in milliseconds. |
| `index_name` | Yes | - | Search index name managed by the document store. |
| `embedding_dim` | Yes | - | Number of values in each stored and query embedding. |
| `distance_metric` | Yes | - | Vector distance metric, such as `cosine`. |
| `metadata_fields` | No | None | Metadata fields that should be indexed for filtering. |
| `request_timeout` | No | `5000 ms` in the sample | Maximum time allowed for a Valkey request. |
| `top_k` | No | `3` in the sample | Maximum number of documents returned by the retriever. |

## Teardown

Remove the local container after the examples finish:

```bash
docker rm -f haystack-valkey
```

The sample also removes its documents and Search index through
`delete_all_documents()` before closing the document store.
Valkey Search documents do not expire automatically through this integration,
so production applications should define a retention policy and schedule
cleanup for data that can grow without bound.

---

[02 - RAG Pipeline ->](02-rag-pipeline.md)
