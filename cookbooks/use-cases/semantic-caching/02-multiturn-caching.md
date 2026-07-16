# Multi-Turn Conversation Caching

> Cache full conversation contexts — not just single prompts. When a user asks a follow-up in a similar conversation flow, return the cached response instead of calling the LLM again.

**Intermediate** · Python · ~20 min

**Who is this for:** Developers building chatbots or multi-turn AI assistants who want to cache conversation-level responses with per-user isolation using Valkey's hybrid TAG + vector search.

## The Challenge

Single-prompt caching works for stateless queries. But in multi-turn conversations, the same message means different things depending on context:

```python
# "Tell me more" means nothing without context:
# Conversation A: "What is Valkey?" → "Tell me more"  (about Valkey)
# Conversation B: "What is Python?" → "Tell me more"  (about Python)
#
# Solution: embed the FULL conversation context, not just the last message
```

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running with the search module
- Ollama with `nomic-embed-text` pulled

## Step 1: Create Index with TAG Filter for User Isolation

```python
import valkey
import numpy as np
import hashlib
import time
import ollama

client = valkey.Valkey(host="localhost", port=6379)
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768

try:
    client.execute_command(
        "FT.CREATE", "conv_cache_idx",
        "ON", "HASH",
        "PREFIX", "1", "conv_cache:",
        "SCHEMA",
        "context_summary", "TEXT",
        "response", "TEXT",
        "user_id", "TAG",
        "turn_count", "NUMERIC",
        "embedding", "VECTOR", "HNSW", "6",
        "TYPE", "FLOAT32",
        "DIM", str(EMBEDDING_DIM),
        "DISTANCE_METRIC", "COSINE",
    )
    print("Conversation cache index created")
except valkey.ResponseError as e:
    if "Index already exists" in str(e):
        print("Conversation cache index already exists")
    else:
        raise
```

## Step 2: Build Context Summary

```python
def build_context_string(messages: list) -> str:
    """Build a cacheable context string from conversation messages."""
    # Use last 3 turns (6 messages: user+assistant pairs)
    recent = messages[-6:]
    parts = []
    for msg in recent:
        role = msg["role"]
        content = msg["content"][:200]  # Truncate long messages
        parts.append(f"{role}: {content}")
    return " | ".join(parts)


def get_embedding(text: str) -> bytes:
    """Embed text using Ollama nomic-embed-text."""
    response = ollama.embed(model=EMBEDDING_MODEL, input=text)
    vec = response["embeddings"][0]
    return np.array(vec, dtype=np.float32).tobytes()
```

## Step 3: Context-Aware Cache Lookup

```python
import re


def sanitize_tag_value(value: str) -> str:
    """Validate tag values to prevent query injection.

    FT.SEARCH query DSL uses special characters ({, }, |, @, \\) that
    could alter query semantics if interpolated unsanitized.
    """
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', value):
        raise ValueError(f"Invalid tag value: {value!r}")
    return value


def lookup_conversation_cache(
    messages: list, user_id: str, threshold: float = 0.12
) -> dict:
    """Search cache for similar conversation contexts, scoped to user."""
    safe_id = sanitize_tag_value(user_id)
    context = build_context_string(messages)
    query_vec = get_embedding(context)

    # Hybrid query: filter by user_id TAG + KNN on context embedding
    results = client.execute_command(
        "FT.SEARCH", "conv_cache_idx",
        f"@user_id:{{{safe_id}}}=>[KNN 1 @embedding $query_vec AS score]",
        "PARAMS", "2", "query_vec", query_vec,
    )

    if results[0] > 0:
        fields = results[2]
        field_dict = {}
        for j in range(0, len(fields), 2):
            k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
            v = fields[j + 1]
            if isinstance(v, bytes):
                try:
                    v = v.decode()
                except UnicodeDecodeError:
                    pass
            field_dict[k] = v

        score = float(field_dict.get("score", "999"))
        if score < threshold:
            return {
                "hit": True,
                "response": field_dict.get("response", ""),
                "score": score,
            }

    return {"hit": False}


def store_conversation_cache(messages: list, response: str, user_id: str):
    """Cache a conversation context + response."""
    context = build_context_string(messages)
    embedding_bytes = get_embedding(context)
    key_hash = hashlib.md5(context.encode()).hexdigest()
    cache_key = f"conv_cache:{user_id}:{key_hash}"

    client.hset(cache_key, mapping={
        "context_summary": context,
        "response": response,
        "user_id": user_id,
        "turn_count": str(len(messages)),
        "embedding": embedding_bytes,
    })
    client.expire(cache_key, 1800)  # 30 min TTL for conversations
```

## Step 4: Full Conversation Flow with Caching

```python
def chat_with_cache(messages: list, user_id: str) -> dict:
    """Chat with LLM, using conversation-aware semantic cache."""
    start = time.time()

    # Check cache
    cache = lookup_conversation_cache(messages, user_id)
    if cache["hit"]:
        return {
            "response": cache["response"],
            "source": "cache",
            "score": cache["score"],
            "latency_ms": round((time.time() - start) * 1000, 1),
        }

    # Cache miss — call LLM
    response = ollama.chat(model="llama3.2:1b", messages=messages)
    answer = response["message"]["content"]

    # Store in cache
    store_conversation_cache(messages, answer, user_id)

    return {
        "response": answer,
        "source": "llm",
        "latency_ms": round((time.time() - start) * 1000, 1),
    }


# Example: multi-turn conversation
convo = [
    {"role": "user", "content": "What is Valkey?"},
    {"role": "assistant", "content": "Valkey is an open-source in-memory data store..."},
    {"role": "user", "content": "How does it handle vector search?"},
]

result = chat_with_cache(convo, user_id="user_123")
print(f"Source: {result['source']}, Latency: {result['latency_ms']}ms")
```

## How It Works

| Component | Role |
|-----------|------|
| `build_context_string` | Combines recent conversation turns into a single embeddable string |
| `@user_id:{user_123}` TAG filter | Ensures User A's cache doesn't leak to User B |
| Hybrid query (TAG + KNN) | Pre-filters by user, then finds nearest context — single atomic operation |
| 30-min TTL | Conversations are ephemeral; shorter TTL prevents stale context |

`@user_id:{user_123}` ensures per-user isolation. The hybrid query runs as a single atomic operation: pre-filter by TAG, then KNN within the filtered set.

## Cache Isolation Strategies

| Strategy | TAG Filter | Best For |
|----------|-----------|----------|
| Per-user | `@user_id:{user_123}` | Personalized assistants |
| Per-session | `@session_id:{sess_abc}` | Short-lived chats |
| Global (shared) | No filter (`*`) | FAQ bots, common queries |
| Per-model | `@model:{llama3}` | Multi-model deployments |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Patterns →](03-production.md)
