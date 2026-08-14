# Getting Started with Semantic Caching

> Build a semantic cache that stores LLM responses and returns cached answers for semantically similar prompts — cutting latency from seconds to milliseconds.

**Beginner** · Python · ~15 min

**Who is this for:** Backend engineers and AI application developers who want to reduce LLM API costs and latency by caching responses for semantically equivalent queries using Valkey's vector search.

## How Semantic Caching Works

```text
User Prompt → Embed → FT.SEARCH KNN → Hit? → Return cached response
                                      → Miss? → Call LLM → HSET → Return
```

"What is Valkey?" and "Can you explain what Valkey is?" are different strings but mean the same thing.
Exact-match caching misses these. Semantic caching uses vector similarity to match by *meaning*,
increasing hit rates significantly.

## Prerequisites

- Docker or Podman installed
- Python 3.9+
- An embedding provider — either:
  - [Ollama](https://ollama.com/) installed locally (free, no API key needed) — **default path**
  - OpenAI API key (optional, shown as alternative)

## Step 1: Start Valkey

Start Valkey Bundle, which includes the Search module needed for vector indexing:

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
```

> **Note:** All examples use `docker`. Substitute `podman` if that's your container runtime — the commands are identical.

<!-- markdownlint-disable-next-line MD028 -->

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

Verify Valkey is running with the search module:

```bash
docker exec valkey valkey-cli MODULE LIST
```

You should see `search` in the output.

## Step 2: Install Dependencies

```bash
pip install -r sample/requirements.txt
```

Or install manually:

```bash
pip install valkey==6.1.1 ollama==0.6.2 numpy==2.0.2
```

```python
import valkey
import numpy as np
import hashlib
import time

client = valkey.Valkey(host="localhost", port=6379)

# Using Ollama with nomic-embed-text (768 dimensions, runs locally)
import ollama

EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768
SIMILARITY_THRESHOLD = 0.15  # COSINE distance threshold (see note below)
CACHE_TTL = 3600  # 1 hour
```

> **Understanding COSINE distance:** Valkey Search returns a COSINE *distance* score, not similarity.
> A score of **0 means identical**, and scores increase as vectors diverge (max 2 = opposite).
> This is the inverse of cosine *similarity* (where 1 = identical).
> So the threshold check is `score < 0.15` — meaning "accept if the distance from identical is less than 0.15."
> Lower threshold = stricter matching = fewer but higher-quality cache hits.

Pull the embedding model (one-time setup):

```bash
ollama pull nomic-embed-text
```

## Step 3: Create the Cache Index

```python
def create_cache_index():
    """Create a vector index for the semantic cache."""
    try:
        client.execute_command(
            "FT.CREATE", "cache_idx",
            "ON", "HASH",
            "PREFIX", "1", "cache:",       # Only index keys starting with "cache:"
            "SCHEMA",
            "prompt", "TEXT",
            "response", "TEXT",
            "embedding", "VECTOR",
            "HNSW",                         # Algorithm: Hierarchical Navigable Small World
            "6",                            # Number of config params that follow (3 pairs)
            "TYPE", "FLOAT32",
            "DIM", str(EMBEDDING_DIM),
            "DISTANCE_METRIC", "COSINE",
        )
        print("Cache index created")
    except valkey.ResponseError as e:
        if "Index already exists" in str(e):
            print("Cache index already exists")
        else:
            raise

create_cache_index()
```

## Step 4: Embedding Helper

```python
def get_embedding(text: str) -> bytes:
    """Embed text using Ollama and return as FLOAT32 bytes."""
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    vec = response["embeddings"][0]
    return np.array(vec, dtype=np.float32).tobytes()
```

<details>
<summary>Alternative: Using OpenAI embeddings</summary>

```bash
pip install openai
```

```python
from openai import OpenAI

openai_client = OpenAI()  # requires OPENAI_API_KEY env var
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # update FT.CREATE DIM accordingly

def get_embedding(text: str) -> bytes:
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    vec = response.data[0].embedding
    return np.array(vec, dtype=np.float32).tobytes()
```

</details>

## Step 5: The Semantic Cache

```python
def semantic_cache_lookup(prompt: str, query_vec: bytes) -> dict:
    """Check if a semantically similar prompt is cached."""
    # KNN search: find the K=1 nearest neighbor by embedding vector
    results = client.execute_command(
        "FT.SEARCH", "cache_idx",
        "*=>[KNN 1 @embedding $query_vec AS score]",  # KNN 1 = return the single closest match
        "PARAMS", "2", "query_vec", query_vec,
    )

    if results[0] > 0:
        # results format: [count, key1, [field, value, ...], ...]
        fields = results[2]
        field_dict = {}
        for j in range(0, len(fields), 2):
            k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
            v = fields[j + 1]
            if isinstance(v, bytes):
                try:
                    v = v.decode()
                except UnicodeDecodeError:
                    pass  # binary field (embedding)
            field_dict[k] = v

        score = float(field_dict.get("score", "999"))
        if score < SIMILARITY_THRESHOLD:
            return {
                "hit": True,
                "response": field_dict.get("response", ""),
                "cached_prompt": field_dict.get("prompt", ""),
                "score": score,
            }

    return {"hit": False}


def cache_response(prompt: str, response: str, embedding_bytes: bytes):
    """Store a prompt+response in the cache."""
    cache_key = f"cache:{hashlib.md5(prompt.encode()).hexdigest()}"
    pipe = client.pipeline()
    pipe.hset(cache_key, mapping={
        "prompt": prompt,
        "response": response,
        "embedding": embedding_bytes,
        "created_at": str(time.time()),
    })
    pipe.expire(cache_key, CACHE_TTL)
    pipe.execute()


def ask_with_cache(prompt: str, llm_func) -> dict:
    """Check cache first, then call LLM if needed."""
    start = time.time()

    # Compute embedding once — reused for both lookup and storage
    embedding = get_embedding(prompt)

    # 1. Check cache
    cache_result = semantic_cache_lookup(prompt, embedding)

    if cache_result["hit"]:
        elapsed = (time.time() - start) * 1000
        return {
            "response": cache_result["response"],
            "source": "cache",
            "similarity_score": cache_result["score"],
            "latency_ms": round(elapsed, 1),
        }

    # 2. Cache miss — call LLM
    answer = llm_func(prompt)

    # 3. Cache the response (reuse embedding computed above)
    cache_response(prompt, answer, embedding)

    elapsed = (time.time() - start) * 1000
    return {
        "response": answer,
        "source": "llm",
        "latency_ms": round(elapsed, 1),
    }
```

## Step 6: Test It

```python
# Simple LLM function using Ollama (no API key needed)
def local_llm(prompt: str) -> str:
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]

# First call — cache MISS (calls LLM)
result1 = ask_with_cache("What is Valkey?", local_llm)
print(f"Source: {result1['source']}, Latency: {result1['latency_ms']}ms")
# Source: llm, Latency: ~1200ms

# Second call — semantically similar — cache HIT
result2 = ask_with_cache("Can you explain what Valkey is?", local_llm)
print(f"Source: {result2['source']}, Latency: {result2['latency_ms']}ms")
# Source: cache, Latency: ~15ms  ← 80x faster!

# Third call — different topic — cache MISS
result3 = ask_with_cache("How do I cook pasta?", local_llm)
print(f"Source: {result3['source']}, Latency: {result3['latency_ms']}ms")
# Source: llm, Latency: ~980ms
```

## How It Works

| Component | Role |
|-----------|------|
| `FT.CREATE` | Creates a vector index on hash fields (one-time setup) |
| `FT.SEARCH ... KNN` | Finds the nearest cached embedding in ~0.1ms |
| `HSET` | Stores prompt + response + embedding vector |
| `EXPIRE` | Sets TTL so stale entries are auto-evicted |
| Ollama `nomic-embed-text` | Converts text to 768-dim vectors locally |

## Configuration Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `EMBEDDING_DIM` | ✓ | — | Must match your embedding model's output dimensions |
| `SIMILARITY_THRESHOLD` | ✓ | `0.15` | COSINE distance cutoff (lower = stricter matching) |
| `CACHE_TTL` | — | `3600` | Seconds before cached entries expire |
| `EMBEDDING_MODEL` | ✓ | — | Model name for your embedding provider |

## Teardown

```bash
docker stop valkey && docker rm valkey
```

---

[02 - Multi-Turn Conversation Caching →](02-multiturn-caching.md)
