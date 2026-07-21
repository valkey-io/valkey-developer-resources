# Full Agent with LangChain + Valkey

> Combine checkpointing, exact caching, and semantic search in one LangGraph flow.

**Advanced** · Python · ~25 min

**Who is this for:** Python developers composing Valkey-backed persistence,
caching, and semantic search in a LangGraph agent.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start from the sample directory.
- Python 3.10 or newer with the pinned requirements installed
- A local Valkey Bundle running on `127.0.0.1:6379`

## Architecture

```text
User: "I forgot my password, help!"
        │
        ▼
   ┌─ ValkeyStore.search() ─── semantic cache lookup
   │   related result → ✅ return cached answer
   │   no result       → ❌ continue to the local model
   │
   ├─ local model function ─── deterministic response
   │
   ├─ ValkeyStore.put() ─── cache the response
   │
   └─ ValkeySaver ─── checkpoint conversation state
```

The default walkthrough is credential-free. A provider-backed LangChain model
can replace the local model function without changing the Valkey APIs.

## Step 1: Shared Valkey Connection

```python
from langchain_core.messages import AIMessage
from langgraph_checkpoint_aws import ValkeyCache, ValkeySaver, ValkeyStore
from main import DeterministicEmbeddings
from valkey import Valkey

# Single Valkey connection shared across all components
valkey_client = Valkey.from_url(
    "valkey://127.0.0.1:6379",
    decode_responses=False,
)

# Deterministic local embeddings for semantic search
embeddings = DeterministicEmbeddings()


def local_model(messages):
    prompt = messages[-1].content
    return AIMessage(content=f"Local answer for: {prompt}")
```

## Step 2: Initialize All Three Components

Create resources inside the setup guard so a failure in any constructor or in
`store.setup()` still closes the client:

```python
try:
    # 1. Checkpointer - persists conversation state
    saver = ValkeySaver(client=valkey_client, ttl=3600)

    # 2. Semantic store - vector search for cache lookups
    store = ValkeyStore(
        client=valkey_client,
        index={
            "collection_name": "helpdesk_cache",
            "dims": embeddings.dimensions,
            "embed": embeddings,
            "fields": ["text"],
            "index_type": "hnsw",
            "distance_metric": "COSINE",
        },
        ttl={"default_ttl": 60.0},
    )
    store.setup()

    # 3. Exact cache - fast key-value cache for repeated prompts
    cache = ValkeyCache(client=valkey_client, prefix="llm_cache:", ttl=3600)
except BaseException:
    valkey_client.close()
    raise
```

## Step 3: Build the Agent Graph

```python
from langgraph.graph import MessagesState, StateGraph
from langchain_core.messages import HumanMessage
import hashlib

SIMILARITY_THRESHOLD = 0.90


def helpdesk_agent(state: MessagesState):
    user_msg = state["messages"][-1].content

    # 1. Check semantic cache
    hits = store.search(("helpdesk",), query=user_msg, limit=1)
    if hits and hits[0].score >= SIMILARITY_THRESHOLD:
        cached_answer = hits[0].value["answer"]
        return {"messages": [AIMessage(content=cached_answer)]}

    # 2. Cache miss - use the deterministic local model
    response = local_model(state["messages"])

    # 3. Store response in semantic cache for future hits
    key = hashlib.sha256(user_msg.encode("utf-8")).hexdigest()[:12]
    store.put(
        ("helpdesk",),
        key,
        {"text": user_msg, "answer": response.content},
    )

    return {"messages": [response]}


# Build and compile with ValkeySaver
builder = StateGraph(MessagesState)
builder.add_node("agent", helpdesk_agent)
builder.set_entry_point("agent")
builder.set_finish_point("agent")

graph = builder.compile(checkpointer=saver)
```

## Step 4: Run the Complete Flow

```python
import time

config = {"configurable": {"thread_id": "user-42"}}

# First question - cache miss, uses the local model
t0 = time.time()
r1 = graph.invoke(
    {"messages": [HumanMessage(content="How do I reset my password?")]},
    config,
)
print(f"MISS: {r1['messages'][-1].content}")

# Paraphrased question - semantic cache hit
t0 = time.time()
r2 = graph.invoke(
    {"messages": [HumanMessage(content="I forgot my password, help!")]},
    config,
)
print(f"HIT:  {r2['messages'][-1].content}")
```

**Complete Valkey Command Sequence (cache miss):**

```text
# 1. Semantic cache lookup
FT.SEARCH helpdesk_cache_idx "(*)==>[KNN 1 @embedding $vec]" ...

# 2. (No match - run the local model)

# 3. Store response in semantic cache
JSON.SET store:helpdesk_cache:helpdesk:a1b2c3d4e5f6 $ '{...}'
EXPIRE store:helpdesk_cache:helpdesk:a1b2c3d4e5f6 3600

# 4. Checkpoint conversation state
JSON.SET checkpoint:user-42:__empty__:cp_001 $ '{...}'
EXPIRE checkpoint:user-42:__empty__:cp_001 3600
```

The integration performs these operations behind the public
`ValkeyStore` and `ValkeySaver` APIs. Application code should call those
classes rather than issuing the commands directly.

## Configuration Reference

| Option | Default | Description |
| --- | --- | --- |
| `ttl` | `3600` | Checkpoint and exact-cache retention in seconds. |
| `default_ttl` | `60.0` | Semantic-store retention setting. |
| `dims` | `4` | Dimensions of the deterministic local embeddings. |
| `SIMILARITY_THRESHOLD` | `0.90` | Minimum score for a semantic-cache hit. |

## Optional Provider Addendum

The local model can be replaced with a LangChain chat model, and
`DeterministicEmbeddings` can be replaced with a compatible provider embedding.
For example, `langchain-aws` and Bedrock are optional provider choices; they
require separately installed dependencies, credentials, permissions, and a
review of data sent outside the local process. The Valkey connection and
`ValkeySaver`, `ValkeyStore`, and `ValkeyCache` calls remain the same.

## Teardown

Close the shared client after the complete flow:

```python
valkey_client.close()
```

For the runnable sample, use its failure-safe cleanup and then remove the
local Valkey container:

```bash
docker stop valkey
docker rm valkey
```

---

[Previous: 03 Semantic Search](03-semantic-search.md) |
[Back to LangChain Cookbooks](README.md)
