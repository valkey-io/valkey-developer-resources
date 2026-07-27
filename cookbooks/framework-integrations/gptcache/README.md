# GPTCache + Valkey Cookbook

> Semantic caching for LLM API calls using Valkey as a vector store. Cache responses to semantically similar prompts, dramatically reducing API costs and latency.

## Cookbooks

| # | Title | Level |
| --- | --- | --- |
| 1 | [Getting Started with GPTCache and Valkey](01-getting-started.md) | Beginner |
| 2 | [Semantic Caching Pipeline](02-semantic-caching.md) | Intermediate |
| 3 | [Production Deployment](03-production-deployment.md) | Intermediate |

## Prerequisites

- Python 3.9+
- Valkey 8.1+ with search module (`valkey-bundle` image)
- OpenAI API key (or other supported LLM provider)

## How GPTCache Uses Valkey

GPTCache leverages Valkey's vector search capabilities to implement semantic caching:

- **Vector storage** — Stores prompt embeddings as HASH fields using FLAT algorithm with COSINE similarity
- **KNN search** — Finds semantically similar cached prompts via `FT.SEARCH` with KNN queries
- **Hash-based document storage** — Each cached entry is a Valkey HASH with vector, ID, and metadata fields
- **Automatic SORTBY detection** — Probes the backend at startup; Valkey returns KNN results already sorted by distance, so SORTBY is skipped automatically

## Quick Start

```python
from gptcache import cache
from gptcache.adapter import openai
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.embedding import OpenAI as OpenAIEmbedding
from gptcache.similarity_evaluation import SearchDistanceEvaluation

# Configure embedding function
embedding = OpenAIEmbedding()

# Configure Valkey as vector store
vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6379,
    dimension=embedding.dimension,
    namespace="gptcache",
)

# Initialize cache
data_manager = get_data_manager(CacheBase("sqlite"), vector_store)
cache.init(
    embedding_func=embedding.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(),
)

# Use the cached LLM
response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "What is Python?"}],
)
```

## PR Status

> **Note:** [zilliztech/GPTCache#674](https://github.com/zilliztech/GPTCache/pull/674)
> is an open PR that adds Valkey backend detection (INFO SERVER → `server_name:valkey`)
> and conditionally skips SORTBY. Until merged, install from the PR branch:
>
> ```bash
> pip install git+https://github.com/zilliztech/GPTCache.git@valkey-support
> ```

[← Back to Valkey Samples](../../../README.md)
