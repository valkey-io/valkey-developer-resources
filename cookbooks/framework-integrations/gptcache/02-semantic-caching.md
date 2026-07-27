# Semantic Caching Pipeline with GPTCache and Valkey

> Build a production-ready semantic cache with fine-grained control over similarity thresholds, custom embeddings, cache eviction, and multi-tenant isolation — all backed by Valkey's vector search.

**Intermediate** · Python · ~15 min

**Who is this for:** Developers who have completed the getting started guide and want to customize cache behavior for production workloads — tuning hit rates, isolating tenants, and monitoring performance.

## Prerequisites

- Completed [Getting Started with GPTCache and Valkey](01-getting-started.md)
- Valkey running with the search module (`valkey-bundle`)
- OpenAI API key configured

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Similarity Threshold

GPTCache uses a distance score from KNN search to decide whether a cached result is "close enough" to serve. The `SearchDistanceEvaluation` class compares the cosine distance against a threshold:

```python
from gptcache.similarity_evaluation import SearchDistanceEvaluation

# Lower max_distance = stricter matching (fewer cache hits, higher precision)
# Higher max_distance = looser matching (more cache hits, risk of wrong answers)
evaluation = SearchDistanceEvaluation(max_distance=0.1, positive=True)
```

### Tuning the Threshold

| Threshold | Behavior | Use case |
| --- | --- | --- |
| `0.05` | Very strict — only near-identical prompts hit cache | Factual Q&A where precision matters |
| `0.10` | Moderate — semantically similar prompts hit cache | General chatbot, support queries |
| `0.20` | Loose — broadly similar prompts hit cache | Creative tasks where exact answer matters less |

Example: testing threshold behavior:

```python
from gptcache import cache
from gptcache.adapter import openai
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.embedding import OpenAI as OpenAIEmbedding
from gptcache.similarity_evaluation import SearchDistanceEvaluation

embedding = OpenAIEmbedding()

vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6379,
    dimension=embedding.dimension,
    namespace="threshold_test",
)

data_manager = get_data_manager(CacheBase("sqlite"), vector_store)

# Strict threshold — only very similar prompts match
cache.init(
    embedding_func=embedding.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(max_distance=0.05, positive=True),
)
```

## Custom Embedding Functions

GPTCache supports multiple embedding providers. Choose based on cost, latency, and quality:

### Sentence Transformers (local, free)

```python
from gptcache.embedding import SBERT

# Runs locally — no API cost, lower latency
embedding = SBERT("all-MiniLM-L6-v2")  # dimension: 384

vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6379,
    dimension=384,  # Must match model output
    namespace="sbert_cache",
)
```

### Cohere

```python
from gptcache.embedding import Cohere

embedding = Cohere(model="embed-english-v3.0", api_key="your-cohere-key")

vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6379,
    dimension=1024,  # Cohere embed-english-v3.0 dimension
    namespace="cohere_cache",
)
```

### Custom embedding function

```python
from gptcache.embedding.base import BaseEmbedding
import numpy as np


class CustomEmbedding(BaseEmbedding):
    def __init__(self):
        self.__dimension = 768

    def to_embeddings(self, data, **kwargs):
        # Your custom embedding logic here
        # Must return a numpy array of shape (dimension,)
        return np.random.rand(self.__dimension).astype("float32")

    @property
    def dimension(self):
        return self.__dimension
```

## Cache Eviction

For cache workloads, you want to evict stale or least-used entries. Configure Valkey and GPTCache together:

### TTL-based eviction (time-to-live)

Set a TTL on cached entries so they expire automatically:

```python
import valkey

# Connect to Valkey
r = valkey.Valkey(host="localhost", port=6379)

# After GPTCache stores a document, set TTL on the hash keys
# GPTCache keys follow the pattern: {namespace}doc:{id}
namespace = "gptcache_demo"

# Set 1-hour TTL on all cache entries
for key in r.scan_iter(f"{namespace}doc:*"):
    r.expire(key, 3600)
```

### Maxmemory with LRU eviction

Configure Valkey to automatically evict least-recently-used keys when memory is full:

```bash
docker exec valkey-gptcache valkey-cli CONFIG SET maxmemory 512mb
docker exec valkey-gptcache valkey-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Max cache size with manual eviction

Track cache size and evict oldest entries:

```python
import valkey

r = valkey.Valkey(host="localhost", port=6379)


def evict_oldest_entries(namespace: str, max_entries: int = 10000):
    """Remove oldest cache entries when exceeding max size."""
    keys = list(r.scan_iter(f"{namespace}doc:*"))
    if len(keys) <= max_entries:
        return

    # Sort by idle time (least recently accessed last)
    key_idle = []
    for key in keys:
        idle = r.object("idletime", key) or 0
        key_idle.append((key, idle))

    key_idle.sort(key=lambda x: x[1], reverse=True)

    # Remove oldest entries beyond the limit
    to_remove = key_idle[: len(keys) - max_entries]
    if to_remove:
        r.delete(*[k for k, _ in to_remove])
        print(f"Evicted {len(to_remove)} stale cache entries")
```

## Multi-Tenant Caching

Use namespace isolation to separate cache entries per user, application, or environment:

```python
from gptcache import Cache
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.embedding import OpenAI as OpenAIEmbedding
from gptcache.similarity_evaluation import SearchDistanceEvaluation


def create_tenant_cache(tenant_id: str) -> Cache:
    """Create an isolated cache instance for a specific tenant."""
    embedding = OpenAIEmbedding()

    # Each tenant gets its own namespace — separate Valkey index
    vector_store = VectorBase(
        "redis",
        host="localhost",
        port=6379,
        dimension=embedding.dimension,
        namespace=f"tenant_{tenant_id}",
    )

    data_manager = get_data_manager(CacheBase("sqlite"), vector_store)

    tenant_cache = Cache()
    tenant_cache.init(
        embedding_func=embedding.to_embeddings,
        data_manager=data_manager,
        similarity_evaluation=SearchDistanceEvaluation(),
    )
    return tenant_cache


# Create isolated caches per tenant
cache_user_a = create_tenant_cache("user_a")
cache_user_b = create_tenant_cache("user_b")
```

Each tenant gets:

- A separate Valkey index (`FT.CREATE` with unique prefix `tenant_{id}doc:`)
- Isolated KNN search results (no cross-tenant data leakage)
- Independent cache hit/miss behavior

## Monitoring Cache Performance

Track cache effectiveness to validate your configuration:

```python
import time
from dataclasses import dataclass


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    total_hit_latency: float = 0.0
    total_miss_latency: float = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_hit_latency_ms(self) -> float:
        return (self.total_hit_latency / self.hits * 1000) if self.hits > 0 else 0.0

    @property
    def avg_miss_latency_ms(self) -> float:
        return (self.total_miss_latency / self.misses * 1000) if self.misses > 0 else 0.0

    def report(self) -> str:
        return (
            f"Cache Hit Rate: {self.hit_rate:.1%}\n"
            f"Hits: {self.hits}, Misses: {self.misses}\n"
            f"Avg Hit Latency: {self.avg_hit_latency_ms:.1f}ms\n"
            f"Avg Miss Latency: {self.avg_miss_latency_ms:.1f}ms\n"
            f"Estimated Cost Savings: {self.hit_rate:.0%} of LLM API calls avoided"
        )
```

### Valkey index statistics

```bash
# Check memory usage
docker exec valkey-gptcache valkey-cli INFO memory | grep used_memory_human

# Check index statistics
docker exec valkey-gptcache valkey-cli FT.INFO gptcache_demo

# List all indexes
docker exec valkey-gptcache valkey-cli FT._LIST
```

## Valkey-Specific Behavior

GPTCache's `RedisVectorStore` automatically detects whether it is connected to Valkey or Redis:

1. On initialization, it runs `INFO SERVER` and checks for `server_name:valkey`
2. It performs a probe query to test whether `SORTBY` is supported
3. If connected to Valkey (valkey-search module), SORTBY is skipped because KNN results are already returned sorted by distance

This detection is transparent — **no code changes are needed** when switching from Redis to Valkey:

```python
# Same code works for both Redis and Valkey
# The backend is detected automatically
vector_store = VectorBase(
    "redis",  # Backend name stays "redis" — uses redis-py client
    host="localhost",  # Point to Valkey instead of Redis
    port=6379,
    dimension=1536,
    namespace="my_cache",
)
```

### What happens under the hood

```text
┌─────────────────────────────────────────────────┐
│          RedisVectorStore Initialization         │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Connect via redis-py                        │
│  2. INFO SERVER → server_name:valkey?           │
│     ├── Yes → mark as Valkey backend            │
│     └── No  → mark as Redis backend            │
│  3. Probe SORTBY support                        │
│     ├── Supported → use SORTBY in queries       │
│     └── Not needed → skip SORTBY (Valkey)      │
│  4. FT.CREATE index (if not exists)             │
│                                                 │
└─────────────────────────────────────────────────┘
```

The KNN search query adapts accordingly:

```python
# With SORTBY (Redis):
# FT.SEARCH idx "*=>[KNN 5 @vector $vec as score]" SORTBY score DIALECT 2

# Without SORTBY (Valkey — results already sorted):
# FT.SEARCH idx "*=>[KNN 5 @vector $vec as score]" DIALECT 2
```

## Troubleshooting

### Cache hit rate is too low

- Lower the similarity threshold (`max_distance`): try `0.15` or `0.20`
- Check your embedding model — smaller models may not capture semantic similarity well
- Verify queries are being embedded consistently (same preprocessing)

### Cache hit rate is too high (wrong answers being served)

- Raise the similarity threshold: try `0.05`
- Consider using a higher-quality embedding model
- Add a post-retrieval validation step

### Different tenants seeing each other's data

- Verify each tenant has a unique `namespace` value
- Check that indexes are created with correct prefixes: `FT._LIST` should show separate indexes
- Ensure SQLite scalar store is also isolated (use separate DB files per tenant)

### SORTBY errors with Valkey

If you see errors related to SORTBY when using Valkey, ensure you are using the version of GPTCache with Valkey detection:

```bash
pip install "git+https://github.com/zilliztech/GPTCache.git@valkey-support#egg=gptcache[redis]"
```

---

[← Previous: Getting Started](01-getting-started.md) · [Next: Production Deployment →](03-production-deployment.md)
