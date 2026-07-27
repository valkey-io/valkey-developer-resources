# Getting Started with GPTCache and Valkey

> Reduce LLM API costs by up to 90% with semantic caching. GPTCache stores embeddings of your prompts in Valkey and returns cached responses for semantically similar queries — no repeated API calls needed.

**Beginner** · Python · ~10 min

**Who is this for:** Developers who want to add semantic caching to their LLM applications and reduce API costs and latency with minimal setup.

## Prerequisites

- Docker installed and running
- Python 3.9+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)

> **Security:** This cookbook uses Valkey without authentication for local development.
> For any network-accessible or production deployment, see the
> [Valkey security documentation](https://valkey.io/topics/security/) to configure
> authentication and TLS.

## Step 1: Start Valkey with Search Module

Start a Valkey instance with the search module enabled using the `valkey-bundle` image:

```bash
docker run -d --name valkey-gptcache \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:8.1.1
```

Verify the search module is loaded:

```bash
docker exec valkey-gptcache valkey-cli MODULE LIST
```

You should see `search` in the module list.

## Step 2: Install GPTCache

Install GPTCache with the Redis/Valkey backend:

```bash
pip install "gptcache[redis]" openai
```

> **Note:** Until [zilliztech/GPTCache#674](https://github.com/zilliztech/GPTCache/pull/674) is merged, install from the PR branch to get Valkey backend detection:
>
> ```bash
> pip install "git+https://github.com/zilliztech/GPTCache.git@valkey-support#egg=gptcache[redis]"
> ```

## Step 3: Configure the Cache

Create a file `cache_demo.py`:

```python
import os
from gptcache import cache
from gptcache.adapter import openai
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.embedding import OpenAI as OpenAIEmbedding
from gptcache.similarity_evaluation import SearchDistanceEvaluation

# Ensure API key is set
assert os.getenv("OPENAI_API_KEY"), "Set OPENAI_API_KEY environment variable"

# Configure embedding function (uses OpenAI text-embedding-ada-002)
embedding = OpenAIEmbedding()

# Configure Valkey as vector store
vector_store = VectorBase(
    "redis",
    host="localhost",
    port=6379,
    dimension=embedding.dimension,  # 1536 for ada-002
    namespace="gptcache_demo",
)

# Set up data manager with SQLite for scalar data and Valkey for vectors
data_manager = get_data_manager(CacheBase("sqlite"), vector_store)

# Initialize the cache
cache.init(
    embedding_func=embedding.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(),
)

print("Cache initialized with Valkey vector store!")
```

## Step 4: Use the Cache

Add LLM calls that go through the cache:

```python
import time

# First call — cache miss, hits the OpenAI API
start = time.time()
response1 = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
first_call_time = time.time() - start
print(f"First call (API): {first_call_time:.2f}s")
print(f"Response: {response1['choices'][0]['message']['content'][:100]}")

# Second call — semantically similar, cache hit
start = time.time()
response2 = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Tell me the capital city of France"}],
)
second_call_time = time.time() - start
print(f"\nSecond call (cache): {second_call_time:.2f}s")
print(f"Response: {response2['choices'][0]['message']['content'][:100]}")
print(f"\nSpeedup: {first_call_time / second_call_time:.1f}x faster")
```

Run the demo:

```bash
python cache_demo.py
```

Expected output:

```text
Cache initialized with Valkey vector store!
First call (API): 1.23s
Response: The capital of France is Paris...

Second call (cache): 0.03s
Response: The capital of France is Paris...

Speedup: 41.0x faster
```

## How It Works

```text
┌─────────────────────────────────────────────────────────────┐
│                    GPTCache Pipeline                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Query                                                 │
│      │                                                      │
│      ▼                                                      │
│  ┌──────────┐     ┌─────────────────────┐                  │
│  │ Embed    │────▶│ KNN Search (Valkey) │                  │
│  │ Prompt   │     │ FT.SEARCH + KNN     │                  │
│  └──────────┘     └─────────┬───────────┘                  │
│                             │                               │
│                    ┌────────┴────────┐                      │
│                    │                 │                       │
│               Cache Hit         Cache Miss                  │
│               (similar          (no match)                  │
│                found)               │                       │
│                    │                 ▼                       │
│                    │          ┌────────────┐                │
│                    │          │ Call LLM   │                │
│                    │          │ API        │                │
│                    │          └─────┬──────┘                │
│                    │                │                       │
│                    │                ▼                       │
│                    │          ┌────────────┐                │
│                    │          │ Store in   │                │
│                    │          │ Valkey     │                │
│                    │          └─────┬──────┘                │
│                    │                │                       │
│                    ▼                ▼                       │
│              ┌──────────────────────────┐                  │
│              │     Return Response      │                  │
│              └──────────────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Reference

| Parameter | Default | Description |
| --- | --- | --- |
| `host` | `localhost` | Valkey server hostname |
| `port` | `6379` | Valkey server port |
| `dimension` | (required) | Embedding vector dimension (e.g., 1536 for OpenAI ada-002) |
| `top_k` | `1` | Number of nearest neighbors to retrieve |
| `namespace` | `gptcache` | Key prefix for stored documents (`{namespace}doc:`) |
| `password` | `None` | Valkey authentication password |

## Troubleshooting

### Connection refused on port 6379

Verify the container is running:

```bash
docker ps | grep valkey-gptcache
```

If not running, start it:

```bash
docker start valkey-gptcache
```

### Module 'search' not found

You must use the `valkey-bundle` image which includes the search module. The base `valkey/valkey` image does not include it:

```bash
docker rm -f valkey-gptcache
docker run -d --name valkey-gptcache -p 127.0.0.1:6379:6379 valkey/valkey-bundle:8.1.1
```

### Cache never hits (always misses)

- Check that your similarity threshold is not too strict (default is usually fine)
- Verify the index was created: `docker exec valkey-gptcache valkey-cli FT._LIST`
- Ensure your embedding function is deterministic (same input → same vector)

---

[← Back to README](README.md) · [Next: Semantic Caching Pipeline →](02-semantic-caching.md)
