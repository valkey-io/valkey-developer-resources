# Vector Search and Filtering

> Deep dive into KNN similarity search, full-text retrieval, TAG filtering, and distance metric tuning in Dify's Valkey vector store.

**Intermediate** · Python · ~25 min

**Who is this for:** Developers who have Dify running with Valkey and want to understand or debug the search pipeline — how queries are constructed, how filtering works, and how to tune relevance.

## Prerequisites

- Completed [Getting Started](./01-getting-started.md)
- Valkey running with `valkey-search` module (`valkey/valkey-bundle:9.1.0`)
- Familiarity with Dify knowledge bases

## KNN Vector Search

When a user queries a Dify knowledge base, the platform embeds the query text using the configured embedding model, then issues a KNN (K-Nearest Neighbors) search against the Valkey index.

### Basic KNN Query

```text
FT.SEARCH idx:{collection}
  "(@group_id:{dataset_id})=>[KNN 4 @vector $query_vector]"
  PARAMS 2 query_vector <float32_bytes>
  LIMIT 0 4
```

Breakdown:

| Component | Purpose |
| --- | --- |
| `@group_id:{dataset_id}` | Pre-filter to a specific dataset within the collection |
| `=>[KNN 4 @vector $query_vector]` | Find 4 nearest neighbors by vector distance |
| `PARAMS 2 query_vector <bytes>` | Pass the query embedding as binary parameter |
| `LIMIT 0 4` | Return up to 4 results starting at offset 0 |

### KNN with Python (valkey-glide)

```python
import struct
from glide import GlideClient

async def search_similar(
    client: GlideClient,
    index_name: str,
    query_embedding: list[float],
    group_id: str,
    top_k: int = 4,
) -> list[dict]:
    """Perform KNN vector search matching Dify's internal pattern."""
    query_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

    # Escape special chars in TAG values
    safe_group = group_id.replace("-", "\\-")

    query = f"(@group_id:{{{safe_group}}})=>[KNN {top_k} @vector $query_vector]"

    result = await client.custom_command([
        "FT.SEARCH", index_name, query,
        "PARAMS", "2", "query_vector", query_bytes,
        "LIMIT", "0", str(top_k),
        "RETURN", "4", "page_content", "metadata", "doc_id", "__vector_score",
    ])

    # Parse results: [total, key1, [field, val, ...], key2, ...]
    total = int(result[0])
    documents = []
    i = 1
    while i < len(result):
        key = result[i].decode() if isinstance(result[i], bytes) else str(result[i])
        i += 1
        if i < len(result) and isinstance(result[i], list):
            fields = result[i]
            doc = {"key": key}
            for j in range(0, len(fields), 2):
                fname = fields[j].decode() if isinstance(fields[j], bytes) else str(fields[j])
                fval = fields[j + 1].decode() if isinstance(fields[j + 1], bytes) else str(fields[j + 1])
                doc[fname] = fval
            documents.append(doc)
            i += 1

    return documents
```

### Result Ordering

Valkey's `FT.SEARCH` with KNN returns results **already sorted by distance** (nearest first). The `__vector_score` field contains the raw distance value — lower means more similar.

## Full-Text Search

Dify's Valkey backend also supports keyword-based retrieval using the `TEXT` field on `page_content`. This powers Dify's "full-text search" retrieval mode.

### Full-Text Query

```text
FT.SEARCH idx:{collection}
  "@group_id:{dataset_id} @page_content:(search terms)"
  LIMIT 0 10
  RETURN 3 page_content metadata doc_id
```

### Combining Full-Text with Vector Search

Dify can operate in three retrieval modes:

| Mode | Query type | When to use |
| --- | --- | --- |
| Semantic | KNN vector search | Best for conceptual/meaning-based queries |
| Full-text | `@page_content:(terms)` | Best for exact keyword matching |
| Hybrid | Both, then re-rank | Best overall relevance for most use cases |

In hybrid mode, Dify runs both queries independently, then merges and re-ranks results using a weighted reciprocal rank fusion.

## TAG Filtering

Dify uses TAG fields to scope searches to specific datasets and documents within a collection.

### Filter by Dataset (group_id)

Every query includes a `@group_id` filter to restrict results to the active dataset:

```text
(@group_id:{dataset_abc123})=>[KNN 4 @vector $query_vector]
```

### Filter by Document (document_id)

When Dify needs to search within specific uploaded files:

```text
(@group_id:{dataset_abc123} @document_id:{file_001|file_002})=>[KNN 4 @vector $query_vector]
```

The `|` operator performs an OR match across multiple TAG values.

### Escaping TAG Values

TAG values containing special characters must be escaped. Dify's UUIDs contain hyphens which need escaping:

```python
def escape_tag(value: str) -> str:
    """Escape special characters for FT.SEARCH TAG queries."""
    special = r"\.+*?[{()|^$!<>~@&\"-]"
    return "".join(f"\\{ch}" if ch in special else ch for ch in value)

# Usage
group_id = "abc-123-def"
safe = escape_tag(group_id)  # "abc\\-123\\-def"
query = f"(@group_id:{{{safe}}})=>[KNN 4 @vector $query_vector]"
```

## Distance Metrics

The distance metric determines how vector similarity is calculated. Dify supports all three metrics offered by valkey-search.

### COSINE (default)

Measures the angle between vectors. Insensitive to magnitude — two vectors pointing in similar directions score well regardless of their length.

- **Distance range:** [0, 2] (0 = identical direction, 2 = opposite)
- **Similarity formula:** `1 - distance / 2`
- **Best for:** Text embeddings (most embedding models produce normalized vectors)

### L2 (Euclidean)

Measures straight-line distance in vector space. Sensitive to magnitude.

- **Distance range:** [0, ∞)
- **Similarity formula:** `1 / (1 + distance)`
- **Best for:** Embeddings where magnitude carries meaning

### IP (Inner Product)

Dot product of two vectors. Fastest to compute but requires normalized vectors for meaningful similarity scores.

- **Distance range:** varies (can be negative)
- **Similarity formula:** `1 - distance`
- **Best for:** Pre-normalized embeddings where you want maximum throughput

### Choosing a Metric

```bash
# Set in Dify environment
VALKEY_DISTANCE_METRIC=COSINE  # default, recommended for most models
```

| Embedding model | Recommended metric |
| --- | --- |
| OpenAI `text-embedding-3-*` | COSINE |
| Cohere `embed-*` | COSINE |
| BGE / E5 | COSINE |
| Custom (non-normalized) | L2 |

## HNSW Index Parameters

Dify creates HNSW indexes with default parameters via the `6` argument to `VECTOR HNSW 6`:

```text
VECTOR HNSW 6 TYPE FLOAT32 DIM {dim} DISTANCE_METRIC {metric}
```

The `6` means 3 key-value pairs follow (TYPE, DIM, DISTANCE_METRIC). Valkey-search uses built-in HNSW defaults:

| Parameter | Default | Effect |
| --- | --- | --- |
| `M` | 16 | Max edges per node. Higher = better recall, more memory |
| `EF_CONSTRUCTION` | 200 | Build-time beam width. Higher = better index quality, slower build |
| `EF_RUNTIME` | 10 | Query-time beam width. Higher = better recall, slower queries |

For most Dify workloads (< 1M documents per collection), the defaults work well. If you need to tune these for large-scale deployments, you would modify the FT.CREATE command in Dify's source.

## Practical Examples

### Debug a Search Query

Connect to Valkey directly to test queries:

```bash
# List all indexes
docker exec valkey-vector valkey-cli FT._LIST

# Check index schema and doc count
docker exec valkey-vector valkey-cli FT.INFO "idx:your_collection"

# Full-text search for a keyword
docker exec valkey-vector valkey-cli FT.SEARCH "idx:your_collection" \
  "@group_id:{your_dataset} @page_content:kubernetes" \
  LIMIT 0 5 RETURN 1 page_content
```

### Inspect Distance Scores

```python
async def search_with_scores(client, index_name, query_vector, group_id, top_k=5):
    """Search and convert distances to similarity scores."""
    docs = await search_similar(client, index_name, query_vector, group_id, top_k)

    for doc in docs:
        distance = float(doc.get("__vector_score", "0"))
        # COSINE conversion (Dify's default)
        similarity = 1.0 - distance / 2.0
        print(f"  {doc['key']}: distance={distance:.4f} similarity={similarity:.4f}")
        print(f"    {doc.get('page_content', '')[:80]}")

    return docs
```

### Score Threshold Filtering

Dify applies a `score_threshold` after search to filter low-relevance results:

```python
def filter_by_threshold(documents: list[dict], threshold: float, metric: str = "COSINE") -> list[dict]:
    """Filter search results by similarity threshold (same logic as Dify)."""
    filtered = []
    for doc in documents:
        distance = float(doc.get("__vector_score", "0"))
        if metric == "COSINE":
            similarity = 1.0 - distance / 2.0
        elif metric == "L2":
            similarity = 1.0 / (1.0 + distance)
        else:  # IP
            similarity = 1.0 - distance

        if similarity >= threshold:
            doc["similarity"] = similarity
            filtered.append(doc)

    return filtered
```

## Troubleshooting

### KNN returns fewer results than top_k

The index may have fewer documents matching the pre-filter. Check:

```bash
# Count docs in a specific group
docker exec valkey-vector valkey-cli FT.SEARCH "idx:your_collection" \
  "@group_id:{your_dataset}" LIMIT 0 0
# First element of result is the total count
```

### Full-text search returns no results

valkey-search tokenizes TEXT fields on whitespace and punctuation. Single-character tokens and common stopwords may be ignored. Try broader search terms.

### High distance scores (low similarity)

If all results have similarity < 0.5 with COSINE metric:

1. Verify the embedding model matches between indexing and querying
2. Check that vector dimensions match (mismatched dims produce garbage distances)
3. Ensure vectors are stored as little-endian FLOAT32 bytes

---

**← Previous:** [Getting Started](./01-getting-started.md) · **Back to** [README](./README.md) · **Next:** [Production Deployment →](./03-production.md)
