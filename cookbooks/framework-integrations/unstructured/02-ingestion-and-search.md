# Document Ingestion & Semantic Search

> Run a full document ingestion pipeline: partition a PDF, chunk, embed with
> a local model, upload to Valkey, and query with KNN vector search.

**Intermediate** · Python · ~25 min

**Who is this for:** Python developers who have completed
[01 Getting Started](01-getting-started.md) and want to build an end-to-end
document search pipeline using Valkey as the vector store.

## Prerequisites

- Completed [01 Getting Started](01-getting-started.md)
- Valkey running on `localhost:6379` (with Search module)
- Python 3.11+ with `unstructured-ingest[valkey]` installed
- ~500 MB disk for the local embedding model (downloaded automatically)

## Step 1: Prepare a Sample Document

Create a sample text file for ingestion. In production you would use PDFs,
DOCX, or HTML — Unstructured handles them all the same way.

```python
from pathlib import Path

# Create a sample document with multiple paragraphs
sample_dir = Path("sample_docs")
sample_dir.mkdir(exist_ok=True)

content = """
# Valkey Architecture Overview

Valkey is a high-performance, open-source key-value store forked from Redis
under the BSD license. It supports strings, hashes, lists, sets, sorted sets,
streams, and more.

## Vector Search

Valkey Search provides full-text and vector search capabilities. The HNSW
(Hierarchical Navigable Small World) algorithm enables approximate nearest
neighbor queries with sub-millisecond latency.

## Data Structures

Hashes in Valkey store field-value pairs, making them ideal for document
storage. Each field can hold text, numbers, or binary data like vector
embeddings.

## Clustering

Valkey supports horizontal scaling through cluster mode. Data is sharded
across multiple nodes using hash slots. Use hash tags in key prefixes to
ensure related keys land on the same shard.

## Persistence

Valkey offers RDB snapshots and AOF (Append Only File) for durability.
In-memory performance is preserved while data survives restarts.
"""

(sample_dir / "valkey_overview.txt").write_text(content)
print(f"Created sample document: {sample_dir / 'valkey_overview.txt'}")
```

## Step 2: Run the Ingestion Pipeline

The pipeline partitions the document into structural elements, chunks them
for embedding, generates vector embeddings, and uploads everything to Valkey.

```python
import asyncio
from pathlib import Path

from unstructured_ingest.data_types.file_data import FileData, SourceIdentifiers
from unstructured_ingest.processes.connectors.valkey import (
    CONNECTOR_TYPE,
    ValkeyAccessConfig,
    ValkeyConnectionConfig,
    ValkeyUploader,
    ValkeyUploaderConfig,
)


async def ingest_document(doc_path: Path):
    """Ingest a single document into Valkey."""

    # --- Partition: split document into structural elements ---
    from unstructured.partition.auto import partition

    elements = partition(filename=str(doc_path))
    print(f"Partitioned into {len(elements)} elements")

    # --- Chunk: combine small elements into semantic chunks ---
    from unstructured.chunking.title import chunk_by_title

    chunks = chunk_by_title(elements, max_characters=500, overlap=50)
    print(f"Chunked into {len(chunks)} chunks")

    # --- Embed: generate vector embeddings ---
    # Uses sentence-transformers locally (no API key needed)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dimensions

    # Build the element dicts that the Valkey uploader expects
    upload_data = []
    for i, chunk in enumerate(chunks):
        text = str(chunk)
        embedding = model.encode(text).tolist()
        upload_data.append({
            "element_id": f"doc_{doc_path.stem}_{i:04d}",
            "type": chunk.category,
            "text": text,
            "metadata": {
                "filename": doc_path.name,
                "page_number": getattr(chunk.metadata, "page_number", 0) or 0,
                "chunk_index": i,
            },
            "embeddings": embedding,
        })

    print(f"Generated {len(upload_data)} embeddings ({len(embedding)} dimensions)")

    # --- Upload: store in Valkey with vector index ---
    uploader = ValkeyUploader(
        connection_config=ValkeyConnectionConfig(
            host="localhost",
            port=6379,
            ssl=False,
            access_config=ValkeyAccessConfig(),
        ),
        upload_config=ValkeyUploaderConfig(
            batch_size=50,
            key_prefix="doc:unstructured:",
            index_name="documents_index",
            distance_metric="COSINE",
        ),
    )

    file_data = FileData(
        source_identifiers=SourceIdentifiers(
            fullpath=doc_path.name, filename=doc_path.name
        ),
        connector_type=CONNECTOR_TYPE,
        identifier=f"ingest-{doc_path.stem}",
    )

    await uploader.run_data_async(data=upload_data, file_data=file_data)
    print(f"✓ Uploaded {len(upload_data)} chunks to Valkey")


asyncio.run(ingest_document(Path("sample_docs/valkey_overview.txt")))
```

## Step 3: Query with KNN Vector Search

Now search the ingested documents using semantic similarity:

```python
import numpy as np
from glide import (
    FtSearchOptions,
    FtSearchLimit,
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ft,
)
from sentence_transformers import SentenceTransformer


async def semantic_search(query: str, top_k: int = 3):
    """Search ingested documents by semantic similarity."""

    # Embed the query with the same model used for ingestion
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vector = model.encode(query)
    query_bytes = np.array(query_vector, dtype=np.float32).tobytes()

    # Connect to Valkey
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    try:
        # KNN vector search
        # The query uses the @embedding field defined in the FT index
        knn_query = f"*=>[KNN {top_k} @embedding $query_vec AS score]"
        options = FtSearchOptions(
            limit=FtSearchLimit(offset=0, count=top_k),
            params=[{"key": "query_vec", "value": query_bytes}],
            return_fields=["text", "source_document", "score"],
        )

        results = await ft.search(client, "documents_index", knn_query, options)

        # Parse results: [total_count, {key: {field: value}, ...}]
        total = results[0] if results else 0
        docs = results[1] if len(results) > 1 else {}

        print(f"\nQuery: '{query}'")
        print(f"Found {total} results (showing top {top_k}):\n")

        for key, fields in docs.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            text = fields.get(b"text", b"").decode()
            score = fields.get(b"score", b"0").decode()
            print(f"  [{score}] {key_str}")
            print(f"    {text[:120]}...")
            print()

    finally:
        await client.close()


import asyncio

asyncio.run(semantic_search("How does Valkey handle vector similarity?"))
asyncio.run(semantic_search("What persistence options are available?"))
```

Expected output:

```text
Query: 'How does Valkey handle vector similarity?'
Found 3 results (showing top 3):

  [0.23] doc:unstructured:doc_valkey_overview_0001
    Valkey Search provides full-text and vector search capabilities. The HNSW
    (Hierarchical Navigable Small World) algorithm enables approximate...

  [0.45] doc:unstructured:doc_valkey_overview_0000
    Valkey is a high-performance, open-source key-value store forked from
    Redis under the BSD license...

  [0.67] doc:unstructured:doc_valkey_overview_0002
    Hashes in Valkey store field-value pairs, making them ideal for document
    storage...
```

## Step 4: Inspect the Stored Data

Verify what was stored in Valkey:

```python
async def inspect_stored_data():
    """Show what the connector stored in Valkey."""
    from glide import GlideClient, GlideClientConfiguration, NodeAddress, ft

    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    try:
        # Check index info
        info = await ft.info(client, "documents_index")
        print("Index info:")
        print(f"  Name: documents_index")
        print(f"  Num docs: {info.get('num_docs', 'unknown')}")

        # Inspect a single hash
        result = await client.hgetall("doc:unstructured:doc_valkey_overview_0000")
        if result:
            decoded = {k.decode(): v for k, v in result.items()}
            print(f"\nSample hash fields:")
            for field, value in decoded.items():
                if field == "embedding":
                    vec = np.frombuffer(value, dtype=np.float32)
                    print(f"  {field}: float32[{len(vec)}] = [{vec[0]:.4f}, {vec[1]:.4f}, ...]")
                elif field == "metadata_json":
                    print(f"  {field}: {value.decode()[:80]}...")
                else:
                    val_str = value.decode() if isinstance(value, bytes) else str(value)
                    print(f"  {field}: {val_str[:80]}")

    finally:
        await client.close()


asyncio.run(inspect_stored_data())
```

## Step 5: Incremental Re-Ingestion

The connector supports idempotent uploads. Re-ingesting the same document
overwrites existing chunks (keyed by `element_id`) and deletes orphaned
chunks from prior runs via the `record_id` tag:

```python
# Re-ingest the same document — no duplicates created
asyncio.run(ingest_document(Path("sample_docs/valkey_overview.txt")))
# ✓ Previous chunks for this file are deleted, new chunks stored
```

This is safe for production pipelines where documents are periodically
re-processed with updated content.

## How It Works

| Stage | What happens | Valkey involvement |
| ------- | -------------- | -------------------- |
| Partition | Document split into structural elements (titles, paragraphs) | None |
| Chunk | Elements combined into semantic chunks with overlap | None |
| Embed | Each chunk converted to a float32 vector | None |
| Upload (first run) | Batch HSET via pipeline, then FT.CREATE index | Index created after data |
| Upload (subsequent) | FT.SEARCH to delete old records, individual HSET | Incremental update |
| Query | KNN search against HNSW index | FT.SEARCH with vector param |

## Configuration Reference

### Embedding Models

| Model | Dimensions | Size | Notes |
| ------- | ----------- | ------ | ------- |
| `all-MiniLM-L6-v2` | 384 | 80 MB | Fast, good quality (default in sample) |
| `all-mpnet-base-v2` | 768 | 420 MB | Higher quality, slower |
| `nomic-embed-text` (Ollama) | 768 | 274 MB | Via Ollama API |

The connector is model-agnostic — it stores whatever embedding dimension
your pipeline produces. The HNSW index dimension is auto-detected from the
first batch.

### Distance Metrics

| Metric | Use case |
| -------- | ---------- |
| `COSINE` | Text similarity (default, normalized) |
| `L2` | Euclidean distance |
| `IP` | Inner product (for pre-normalized vectors) |

## Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| "No matching distribution" for `unstructured-ingest[valkey]` | Upstream not yet released | See note below |
| Slow first upload | HNSW index building | Expected — subsequent uploads use individual HSET |
| "Dimension mismatch" error | Changed embedding model between runs | Drop index: `FT.DROPINDEX documents_index` |
| Empty search results | Query vector dimension ≠ index dimension | Use same embedding model for query and ingestion |

> **Note:** The `unstructured-ingest[valkey]` extra depends on
> [Unstructured-IO/unstructured-ingest#747](https://github.com/Unstructured-IO/unstructured-ingest/pull/747)
> which has not yet been released. Until then, install from the PR branch
> or use the sample scripts which simulate the connector behavior.

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production →](03-production.md)
