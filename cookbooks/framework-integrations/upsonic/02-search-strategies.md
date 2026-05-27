# Search Strategies

> Dense KNN, full-text, hybrid (RRF), and tag-filtered search — choose the right retrieval strategy for your Upsonic agents.

**Intermediate** · Python · ~15 min

Upsonic's Valkey provider supports three search modes that can be combined with tag filters. Each mode suits different retrieval scenarios.

## Setup

All examples below assume you have a connected provider with indexed data:

```python
import asyncio
from upsonic.vectordb import ValkeyProvider, ValkeyConfig
from upsonic.vectordb.config import (
    ConnectionConfig, Mode, DistanceMetric, HNSWIndexConfig,
)

config = ValkeyConfig(
    vector_size=384,
    collection_name="search_demo",
    key_prefix="demo:",
    connection=ConnectionConfig(mode=Mode.LOCAL, host="localhost", port=6379),
    distance_metric=DistanceMetric.COSINE,
    index=HNSWIndexConfig(m=16, ef_construction=200),
)

provider = ValkeyProvider(config)
```

## Dense Search (KNN)

Pure vector similarity — finds the semantically closest documents regardless of keyword overlap:

```python
async def dense_example():
    await provider.aconnect()

    results = await provider.adense_search(
        query_vector=[0.15] * 384,  # Your embedded query
        top_k=5,
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.text[:80]}")

    await provider.adisconnect()

asyncio.run(dense_example())
```

**Best for:** Semantic similarity, paraphrase matching, concept-level retrieval.

## Full-Text Search

Keyword-based search using Valkey Search's text indexing. No embeddings needed for the query:

```python
async def fulltext_example():
    await provider.aconnect()

    results = await provider.afull_text_search(
        query_text="nearest neighbor algorithm",
        top_k=5,
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.text[:80]}")

    await provider.adisconnect()

asyncio.run(fulltext_example())
```

**Best for:** Exact keyword matching, technical terms, proper nouns, code identifiers.

## Hybrid Search (RRF)

Combines dense vector search and full-text search using Reciprocal Rank Fusion. Gets the best of both worlds — semantic understanding plus keyword precision:

```python
async def hybrid_example():
    await provider.aconnect()

    results = await provider.ahybrid_search(
        query_vector=[0.15] * 384,
        query_text="vector similarity search",
        top_k=5,
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.text[:80]}")

    await provider.adisconnect()

asyncio.run(hybrid_example())
```

**Best for:** General-purpose retrieval where you want both semantic relevance and keyword matching. This is typically the best default for RAG pipelines.

### Tuning RRF

The `rrf_k` parameter (default: 60) controls how much weight is given to rank position vs. score magnitude:

```python
config = ValkeyConfig(
    # ...
    rrf_k=30,  # Lower = more weight to top-ranked results from each method
)
```

| `rrf_k` | Behavior |
|---------|----------|
| 1–20 | Aggressive — top results dominate |
| 60 (default) | Balanced |
| 100+ | Conservative — more uniform blending |

## Filtered Search

Add tag filters to any search mode. Filters narrow results to documents matching specific metadata:

```python
async def filtered_example():
    await provider.aconnect()

    # Only search within a specific document
    results = await provider.adense_search(
        query_vector=[0.15] * 384,
        top_k=5,
        filter={"document_name": "valkey_intro.md"},
    )

    for r in results:
        print(f"[{r.score:.3f}] {r.document_name}: {r.text[:60]}")

    await provider.adisconnect()

asyncio.run(filtered_example())
```

### Available Filter Fields

| Field | Type | Description |
|-------|------|-------------|
| `document_name` | TAG | Source file/document name |
| `document_id` | TAG | Parent document identifier |
| `knowledge_base_id` | TAG | KnowledgeBase isolation |

> `knowledge_base_id` is populated by passing `knowledge_base_ids` to `aupsert()` (one per chunk).
> It is also set automatically when ingesting via Upsonic's `KnowledgeBase` API.

Filters use exact TAG matching. Multiple filters are ANDed together:

```python
results = await provider.adense_search(
    query_vector=query_vec,
    top_k=10,
    filter={
        "document_name": "architecture.md",
        "knowledge_base_id": "project_alpha",
    },
)
```

## HNSW Tuning

The HNSW index parameters control the recall/speed trade-off:

```python
from upsonic.vectordb.config import HNSWIndexConfig

config = ValkeyConfig(
    # ...
    index=HNSWIndexConfig(
        m=32,                # Connections per node (default: 16)
        ef_construction=400, # Build-time search width (default: 200)
    ),
    ef_runtime=200,          # Query-time search width (default: None = Valkey default)
)
```

| Parameter | Effect of Increasing | Trade-off |
|-----------|---------------------|-----------|
| `m` | Better recall, more memory | 2× m ≈ 2× memory per vector |
| `ef_construction` | Better index quality, slower builds | One-time cost at index creation |
| `ef_runtime` | Better recall at query time, slower queries | Per-query latency increase |

**Guidelines:**
- Small datasets (< 10k vectors): defaults are fine
- Medium (10k–1M): `m=32`, `ef_construction=300`, `ef_runtime=100`
- Large (1M+): `m=48`, `ef_construction=400`, `ef_runtime=200`

## FLAT Index (Exact Search)

For small collections where you need exact results (no approximation):

```python
from upsonic.vectordb.config import FlatIndexConfig

config = ValkeyConfig(
    # ...
    index=FlatIndexConfig(),  # Brute-force exact search
)
```

FLAT scans every vector — O(n) per query. Only use for collections under ~10k vectors.

## Choosing a Strategy

| Scenario | Recommended Mode |
|----------|-----------------|
| General RAG retrieval | Hybrid (RRF) |
| Semantic Q&A | Dense |
| Code/API lookup | Full-text |
| Known-item search | Full-text + filter |
| Multi-tenant isolation | Any mode + `knowledge_base_id` filter |

---

[← 01 - Getting Started](01-getting-started.md) · [03 - Production Deployment →](03-production-deployment.md)
