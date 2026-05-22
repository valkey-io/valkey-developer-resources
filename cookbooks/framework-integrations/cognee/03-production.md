# Production with ElastiCache

**Advanced** · Python · ~20 min

## Architecture Overview

A production Cognee + Valkey deployment on AWS:

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Application │────▶│  Amazon Bedrock   │     │  ElastiCache for    │
│  (Cognee)    │     │  (LLM + Embed)   │     │  Valkey 8.2+        │
│              │────▶│                   │     │  (Vector Store)     │
└──────────────┘     └──────────────────┘     └─────────────────────┘
       │                                              ▲
       └──────────────────────────────────────────────┘
```

## Step 1: ElastiCache for Valkey Setup

Create a Valkey 8.2+ cluster with the Search module enabled:

```bash
aws elasticache create-serverless-cache \
  --serverless-cache-name cognee-vectors \
  --engine valkey \
  --major-engine-version 8
```

> **Important**: ElastiCache for Valkey 8.2+ includes the Search module by default. No additional configuration needed.

## Step 2: Configure Cognee for ElastiCache

```python
import os

os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
os.environ["LLM_PROVIDER"] = "bedrock"
os.environ["LLM_MODEL"] = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
os.environ["EMBEDDING_PROVIDER"] = "bedrock"
os.environ["EMBEDDING_MODEL"] = "bedrock/amazon.titan-embed-text-v2:0"
os.environ["EMBEDDING_DIMENSIONS"] = "1024"
os.environ["AWS_REGION"] = "us-east-1"

from cognee import config
from cognee_community_vector_adapter_valkey import register  # noqa: F401

# ElastiCache endpoint with TLS
config.set_vector_db_config({
    "vector_db_provider": "valkey",
    "vector_db_url": "valkeys://cognee-vectors-xxxxx.serverless.use1.cache.amazonaws.com:6379",
})
```

> **Note**: Use `valkeys://` (with 's') for TLS connections to ElastiCache.

## Step 3: TLS Configuration

The Valkey adapter uses `valkey-glide` which supports TLS natively. For ElastiCache Serverless, TLS is mandatory:

```python
# The adapter's GlideClientConfiguration supports TLS
# For ElastiCache, modify the adapter connection:
# set use_tls=True in GlideClientConfiguration

# Authentication: use IAM roles, instance profiles, or environment variables.
# Never hardcode credentials in application code.
# See: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html
```

## Step 4: HNSW Tuning

The Valkey adapter creates HNSW indices with default parameters. For production workloads, consider tuning:

| Parameter | Default | Production Recommendation | Effect |
|---|---|---|---|
| `M` | 16 | 16–64 | Higher = better recall, more memory |
| `EF_CONSTRUCTION` | 200 | 200–500 | Higher = better index quality, slower builds |
| `EF_RUNTIME` | 10 | 50–200 | Higher = better recall at query time |

For custom HNSW parameters, modify the adapter's `create_collection` method or pre-create indices:

```bash
FT.CREATE index:my_collection
  ON JSON PREFIX 1 vdb:my_collection:
  SCHEMA
    $.id AS id TAG
    $.vector AS vector VECTOR HNSW 10
      TYPE FLOAT32 DIM 1024 DISTANCE_METRIC COSINE
      M 32 EF_CONSTRUCTION 400 EF_RUNTIME 100
```

## Step 5: Bedrock Model Selection

| Use Case | Model | Notes |
|---|---|---|
| LLM (knowledge extraction) | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Best balance of quality and cost |
| LLM (budget) | `us.anthropic.claude-haiku-4-5-20250929-v1:0` | Faster, cheaper, good for simple docs |
| Embeddings | `amazon.titan-embed-text-v2:0` | 1024 dims, good quality/cost ratio |

## Step 6: Monitoring

### Valkey Metrics

Monitor via CloudWatch (ElastiCache) or directly:

```bash
# Index stats
valkey-cli FT.INFO "index:<collection_name>"

# Memory usage
valkey-cli INFO memory

# Connected clients
valkey-cli INFO clients
```

Key metrics to watch:
- **Vector index size**: `num_docs` in `FT.INFO` output
- **Search latency**: Track `FT.SEARCH` execution time
- **Memory usage**: Vector indices consume significant RAM

### Cognee Logging

```python
import logging
logging.getLogger("ValkeyAdapter").setLevel(logging.INFO)
logging.getLogger("cognee").setLevel(logging.WARNING)
```

## Step 7: Error Handling

```python
from cognee import add, cognify, search, SearchType

async def safe_cognify(documents: list[str]):
    """Add documents with error handling."""
    for doc in documents:
        try:
            await add(doc)
        except Exception as e:
            logging.error("Failed to add document: %s", e)
            continue

    try:
        await cognify()
    except Exception as e:
        logging.error("Cognify failed: %s", e)
        raise

async def safe_search(query: str) -> list[str]:
    """Search with fallback."""
    try:
        return await search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=query,
        )
    except Exception as e:
        logging.warning("Graph search failed, falling back to chunks: %s", e)
        return await search(
            query_type=SearchType.CHUNKS,
            query_text=query,
        )
```

## Cost Considerations

| Component | Cost Driver | Optimization |
|---|---|---|
| ElastiCache Serverless | ECPUs + storage | Right-size based on vector count |
| Bedrock (LLM) | Input/output tokens | Use Haiku for simple extraction |
| Bedrock (Embeddings) | Input tokens | Batch documents before embedding |

## Checklist

- [ ] ElastiCache for Valkey 8.2+ with Search module
- [ ] TLS enabled (`valkeys://` scheme)
- [ ] IAM authentication configured
- [ ] HNSW parameters tuned for your dataset size
- [ ] Bedrock model access enabled in your region
- [ ] CloudWatch alarms on memory and latency
- [ ] Error handling and fallback search strategies
