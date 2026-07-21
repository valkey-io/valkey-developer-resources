# Full Agent with LangChain + Valkey

> Follow `main.py` as it composes checkpointing, exact caching, semantic search, and cleanup in one credential-free run. The optional flow below shows where a provider-backed model fits.

**Advanced** · Python · ~25 min

## Architecture

The archived walkthrough describes the complete agent flow below. The default
sample replaces the provider calls with deterministic local behavior so it can
run without credentials or a model download.

```text
User: "I forgot my password, help!"
        |
        v
   +-- ValkeyStore.search() -- semantic cache lookup
   |   related result -> return the cached answer
   |   no result       -> continue to the model
   |
   +-- ChatBedrockConverse.invoke() -- provider model call
   |
   +-- ValkeyStore.put() -- cache the response
   |
   +-- ValkeySaver -- checkpoint conversation state
```

**Who is this for:** This page is for developers who want to understand the
complete local lifecycle before replacing a deterministic component with a
provider-backed model or embedding implementation.

## Prerequisites

- Complete [01 - Getting Started](01-getting-started.md), or start from the sample directory.
- Python 3.10 or newer and the pinned requirements installed.
- Docker Compose with `valkey/valkey-bundle:9.1.1` running.

```bash
cd cookbooks/framework-integrations/langchain/sample
docker compose up -d
python -m pip install -r requirements.txt
```

## Step 1: Start with the canonical flow

Run the sample exactly as shipped:

```bash
python main.py
```

`main.py` calls `run_demo(settings)`. The default run creates checkpoint, cache,
and store resources, executes one operation through each, prints the results,
and removes data belonging to the `demo` run in a `finally` block.

## Step 2: Construct the three public resources

The sample factories manage client ownership and cleanup. Their underlying public constructors are:

```python
from langgraph_checkpoint_aws import ValkeyCache, ValkeySaver, ValkeyStore
from main import DeterministicEmbeddings, Settings, create_valkey_client

settings = Settings.from_env()
client = create_valkey_client(settings)
embeddings = DeterministicEmbeddings()

try:
    checkpointer = ValkeySaver(
        client=client,
        ttl=settings.checkpoint_ttl_seconds,
    )
    cache = ValkeyCache(
        client=client,
        prefix=settings.cache_prefix,
        ttl=settings.cache_ttl_seconds,
    )
    store = ValkeyStore(
        client=client,
        index={
            "collection_name": settings.store_collection_name,
            "dims": embeddings.dimensions,
            "embed": embeddings,
            "fields": ["text"],
            "index_type": "hnsw",
            "distance_metric": "COSINE",
        },
        ttl={"default_ttl": settings.store_ttl_minutes},
    )
    store.setup()
except BaseException:
    client.close()
    raise
```

These constructor arguments match `create_checkpointer`, `create_cache`, and
`create_store` in the sample's `resources.py` module. For a complete
application, prefer the factories so a client created internally is closed and
`cleanup_sample` can remove only sample-owned data.

## Step 3: Trace one run

The three demo helpers expose the data flow without requiring a hosted model:

This block continues from Step 2 and reuses `settings`, `client`, `checkpointer`,
`cache`, and `store`. Wrap direct experiments in a `try`/`finally` block as
shown so the client and sample data are cleaned up on failure.

```python
from main import (
    cleanup_sample,
    run_cache_demo,
    run_checkpoint_demo,
    run_store_demo,
)

run_id = "lesson"
try:
    checkpoint = run_checkpoint_demo(
        checkpointer,
        thread_id=run_id,
        message=f"Run {run_id}: I forgot my password.",
    )
    cache_result = run_cache_demo(
        cache,
        key=(("langchain-cookbook", run_id), f"answer-{run_id}"),
        value={"answer": "Valkey is a data store for this exercise."},
    )
    store_results = run_store_demo(
        store,
        namespace=(f"{settings.store_namespace}:{run_id}",),
        query="I forgot my password.",
        documents=[
            (
                f"password-{run_id}",
                {
                    "text": "How do I reset my password?",
                    "answer": "Use the password reset page.",
                },
            )
        ],
    )
    print(checkpoint, cache_result, store_results)
finally:
    cleanup_sample(client, settings=settings, run_id=run_id)
    client.close()
```

The actual `run_demo` wrapper also validates the run ID, handles requested
failure stages, and cleans up in `finally`. Direct experiments should use a
unique run ID and call the sample cleanup helpers when they finish.

## Step 4: Verify the complete contract

Run the focused tests:

```bash
python -m pytest -q test_langchain.py
```

The tests cover checkpoint resume, cache miss and hit behavior, store search and namespace isolation, environment overrides, failure cleanup, idempotent cleanup, and preservation of unrelated keys.

## Step 5: Apply deployment safety rules

Keep the default Compose service on loopback and treat the sample data as
disposable development data. Do not expose a shared Valkey endpoint without
authentication, TLS, network controls, and an explicit retention plan. Keep
cache prefixes, store namespaces, and collection names isolated between
applications or tenants, and review provider-generated content before
persisting it.

## How It Works

The flow is intentionally deterministic:

1. `create_valkey_client` applies the URL, fallback host and port, and socket timeout.
2. `create_checkpointer` creates `ValkeySaver` and `run_checkpoint_demo` writes graph state for the run thread.
3. `create_cache` creates `ValkeyCache` and `run_cache_demo` reads, then writes on a miss.
4. `create_store` creates `ValkeyStore`, calls `setup`, writes the sample document, and searches its namespace.
5. `run_demo` calls `cleanup_sample` even when a stage raises.

The integration packages translate these public calls into Valkey key-value,
JSON, Search, and expiration operations. Raw commands are useful only for
explaining this lifecycle; application code should use the three classes and
the sample helpers.

## Optional provider-backed agent flow

Commonly, Amazon Bedrock is used for the model and embeddings. The
following public-API flow keeps that teaching path available without making it
part of the default requirements. Install a compatible `langchain-aws`
release, configure AWS credentials and permissions, and use a collection whose
dimensions match the selected embedding model before running it.

### Step 1: Create the provider resources

```python
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langgraph_checkpoint_aws import ValkeyCache, ValkeySaver, ValkeyStore
from main import Settings, create_valkey_client

settings = Settings.from_env()
client = create_valkey_client(settings)
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-west-2",
)
model = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-west-2",
)
saver = ValkeySaver(client=client, ttl=settings.checkpoint_ttl_seconds)
store = ValkeyStore(
    client=client,
    index={
        "collection_name": "helpdesk_cache",
        "dims": 1024,
        "embed": embeddings,
        "fields": ["query"],
        "index_type": "hnsw",
        "distance_metric": "COSINE",
    },
    ttl={"default_ttl": settings.store_ttl_minutes},
)
cache = ValkeyCache(
    client=client,
    prefix=settings.cache_prefix,
    ttl=settings.cache_ttl_seconds,
)
store.setup()
```

### Step 2: Route cache misses to the model

This illustrative node uses `ValkeyStore.search` and `ValkeyStore.put`
directly. The exact model response remains provider-specific, while checkpoint
state is still managed by the public `ValkeySaver` API.

This block continues from the provider resources in Step 1:

```python
import hashlib

from langchain_core.messages import AIMessage

SIMILARITY_THRESHOLD = 0.90


def helpdesk_agent(state):
    user_message = state["messages"][-1].content
    hits = store.search(("helpdesk",), query=user_message, limit=1)
    if hits and hits[0].score >= SIMILARITY_THRESHOLD:
        return {"messages": [AIMessage(content=hits[0].value["answer"])]}

    response = model.invoke(state["messages"])
    key = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:16]
    store.put(
        ("helpdesk",),
        key,
        {"query": user_message, "answer": response.content},
    )
    return {"messages": [response]}
```

Compile this node in a `StateGraph` with `saver` as its checkpointer, using the
same `thread_id` on subsequent invocations:

```python
from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState, StateGraph

builder = StateGraph(MessagesState)
builder.add_node("agent", helpdesk_agent)
builder.set_entry_point("agent")
builder.set_finish_point("agent")
graph = builder.compile(checkpointer=saver)

config = {"configurable": {"thread_id": "user-42"}}
first = graph.invoke(
    {"messages": [HumanMessage(content="How do I reset my password?")]},
    config,
)
second = graph.invoke(
    {"messages": [HumanMessage(content="I forgot my password, help!")]},
    config,
)
print(first["messages"][-1].content)
print(second["messages"][-1].content)
```

Use `cache` for exact prompt lookups when that behavior is useful; the
semantic store and exact cache are separate public components with independent
TTLs.

> **Provider safety:** Do not send sensitive prompts or documents to an
> external model without an approved data-handling review. For non-local
> Valkey, configure authentication, TLS, network controls, and bounded client
> timeouts.

## Configuration Reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `VALKEY_URL` | `valkey://127.0.0.1:6379` when unset | Full Valkey URL; takes precedence over host and port. |
| `VALKEY_HOST` | `127.0.0.1` | Host fallback when `VALKEY_URL` is unset. |
| `VALKEY_PORT` | `6379` | Port fallback when `VALKEY_URL` is unset. |
| `VALKEY_SOCKET_TIMEOUT` | `5.0` | Socket and connection timeout in seconds. |
| `CHECKPOINT_TTL_SECONDS` | `3600` | Checkpoint lifetime in seconds. |
| `CACHE_TTL_SECONDS` | `300` | Default exact-cache lifetime in seconds. |
| `STORE_TTL_MINUTES` | `60` | Default store lifetime in minutes. |
| `VALKEY_CACHE_PREFIX` | `langchain:cache:` | Prefix used by `ValkeyCache`. |
| `VALKEY_STORE_COLLECTION` | `langchain_store_idx` | Search collection used by `ValkeyStore`. |
| `VALKEY_STORE_NAMESPACE` | `langchain-cookbook` | Namespace prefix used by the sample store. |

## Optional Bedrock/provider addendum

The default composition is not an LLM agent and does not require Bedrock or any
other provider. To add a provider, supply a compatible embeddings object to
`create_store(settings, client=client, embeddings=provider_embeddings)` and
place a provider model call around the cache and graph helpers in an
application. Provider use requires additional packages, credentials,
permissions, network access, and a review of data sent outside the local
process. Keep those changes separate from the deterministic default.

## Teardown

`run_demo` cleans its own run data. Close clients created by direct snippets and remove the local Compose service:

```python
client.close()
```

```bash
docker compose down --volumes
```

---

[Previous: 03 - Semantic Search](03-semantic-search.md) | [Back to LangChain + Valkey](README.md)
