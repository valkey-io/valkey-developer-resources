# Document Ingestion & Search

**Intermediate** · Python · ~25 min

## Overview

End-to-end pipeline: take a PDF, partition it into chunks, generate embeddings, store in Valkey with an HNSW vector index, then search by meaning using KNN.

## Prerequisites

- Valkey running with Search module (from [01 Getting Started](01-getting-started.md))
- `pip install 'unstructured-ingest[valkey]' 'unstructured[all-docs]' sentence-transformers`

## Step 1: Partition a document

Unstructured breaks documents into typed elements:

```python
from unstructured.partition.auto import partition

elements = partition("quarterly-report.pdf")

for el in elements[:5]:
    print(f"{el.category}: {el.text[:80]}...")
```

Output:
```
Title: Q2 2024 Financial Results...
NarrativeText: Revenue grew 23% year-over-year driven by cloud expansion...
ListItem: Cloud services: $4.2B (+31%)...
ListItem: Enterprise licenses: $2.1B (+12%)...
NarrativeText: Operating margins improved to 28%...
```

## Step 2: Chunk and embed

```python
from unstructured.chunking.title import chunk_by_title
from sentence_transformers import SentenceTransformer

chunks = chunk_by_title(elements, max_characters=500)

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim

data = []
for chunk in chunks:
    data.append({
        "element_id": chunk.id,
        "type": chunk.category,
        "text": chunk.text,
        "metadata": {
            "page_number": chunk.metadata.page_number or 0,
            "filename": chunk.metadata.filename or "quarterly-report.pdf",
        },
        "embeddings": model.encode(chunk.text).tolist(),
    })

print(f"{len(data)} chunks with 384-dim embeddings")
```

## Step 3: Upload to Valkey

```python
import asyncio
from unstructured_ingest.data_types.file_data import FileData, SourceIdentifiers
from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig, ValkeyConnectionConfig, ValkeyUploader, ValkeyUploaderConfig,
)

uploader = ValkeyUploader(
    connection_config=ValkeyConnectionConfig(
        host="localhost", port=6379, ssl=False,
        access_config=ValkeyAccessConfig(),
    ),
    upload_config=ValkeyUploaderConfig(
        batch_size=50,
        key_prefix="doc:reports:",
        index_name="reports_index",
    ),
)

file_data = FileData(
    source_identifiers=SourceIdentifiers(
        fullpath="quarterly-report.pdf", filename="quarterly-report.pdf",
    ),
    connector_type="valkey",
    identifier="q2-report",
)

asyncio.run(uploader.run_data_async(data=data, file_data=file_data))
print(f"Stored {len(data)} chunks with vector index 'reports_index'")
```

## Step 4: Search by meaning

```python
import numpy as np
from glide import GlideClient, GlideClientConfiguration, NodeAddress, FtSearchOptions, ft

async def search(query_text: str, top_k: int = 5):
    config = GlideClientConfiguration(
        addresses=[NodeAddress(host="localhost", port=6379)],
        request_timeout=10000,
    )
    client = await GlideClient.create(config)

    query_vec = model.encode(query_text)
    query_bytes = np.array(query_vec, dtype=np.float32).tobytes()

    ft_query = f"*=>[KNN {top_k} @embedding $vec]"
    options = FtSearchOptions(params={"vec": query_bytes})
    results = await ft.search(client, "reports_index", ft_query, options)

    print(f"\nQuery: '{query_text}' — {results[0]} hits\n")
    for entry in results[1:]:
        if not isinstance(entry, dict):
            continue
        for key, fields in entry.items():
            text = fields.get(b"text", b"").decode()
            score = 1.0 - float(fields.get(b"__embedding_score", b"1.0"))
            print(f"  [{score:.3f}] {text[:120]}...")

    await client.close()

asyncio.run(search("What drove revenue growth?"))
```

Output:
```
Query: 'What drove revenue growth?' — 5 hits

  [0.892] Revenue grew 23% year-over-year driven by expansion in cloud services...
  [0.847] Cloud services: $4.2B (+31%), Enterprise licenses: $2.1B (+12%)...
  [0.781] Q4 revenue of $1.8B exceeded analyst expectations by 4%...
```

## Step 5: Filtered search

Search within specific element types:

```python
async def filtered_search(query_text: str, element_type: str):
    # ... same setup ...
    ft_query = f"(@element_type:{{{element_type}}})=>[KNN 5 @embedding $vec]"
    # ... same execution ...

# Only narrative paragraphs
asyncio.run(filtered_search("operating margins", "NarrativeText"))

# Only titles/headings
asyncio.run(filtered_search("financial summary", "Title"))
```

## Step 6: Build RAG context

Feed search results to an LLM:

```python
async def get_rag_context(question: str, top_k: int = 3) -> str:
    # ... connect and search (same as Step 4) ...

    context_parts = []
    for entry in results[1:]:
        if not isinstance(entry, dict):
            continue
        for key, fields in entry.items():
            text = fields.get(b"text", b"").decode()
            source = fields.get(b"source_document", b"").decode()
            page = fields.get(b"page_number", b"?").decode()
            context_parts.append(f"[{source}, p.{page}] {text}")

    return "\n\n".join(context_parts)

context = asyncio.run(get_rag_context("What drove revenue growth?"))

# Feed to LLM:
# prompt = f"Based on:\n{context}\n\nAnswer: What drove revenue growth?"
```

## How it works

| Step | What happens | Valkey commands |
|------|-------------|----------------|
| First upload | Batch HSET (no index yet) | `HSET doc:reports:{id} text ... embedding ...` × N |
| Index creation | HNSW vector index built | `FT.CREATE reports_index ... VECTOR embedding HNSW ...` |
| Re-upload | Individual HSET (index active) | `HSET doc:reports:{id} ...` per element |
| KNN search | Nearest neighbor retrieval | `FT.SEARCH reports_index "*=>[KNN 5 @embedding $vec]"` |
| Filtered search | Type filter + KNN | `FT.SEARCH reports_index "(@element_type:{Title})=>[KNN 5 ...]"` |

[← Previous: 01 Getting Started](01-getting-started.md) · [Next: 03 Production →](03-production.md)
