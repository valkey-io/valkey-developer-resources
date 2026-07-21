# Getting Started with LangChain + Valkey

> Persist LangGraph conversation state in Valkey and resume it after a restart.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers building LangGraph agents who want
checkpoint persistence backed by Valkey.

## Prerequisites

- Docker installed
- Python 3.10 or newer
- The files in [`sample/`](sample/) for the credential-free local path

## What is LangGraph + Valkey?

LangGraph lets you build multi-step AI agents with branching logic and tool use.
The problem: if your agent crashes mid-conversation or you restart your server,
all state is lost. Valkey stores checkpoints after every step, so agents pick up
exactly where they left off.

[LangGraph](https://github.com/langchain-ai/langgraph) agents are stateless by
default. `ValkeySaver` from the `langgraph-checkpoint-aws` package adds
persistent checkpointing backed by Valkey. The package is an AWS-published
integration; the local sample uses only its Valkey APIs and does not require AWS
credentials:

- **Checkpoint persistence** - conversation state survives process restarts
- **Atomic writes** - no partial state corruption
- **Built-in TTL** - sessions expire automatically
- **Local-first setup** - the same Valkey API can be used with a remote deployment

## Step 1: Start Valkey

Docker installed and Python 3.10+ required.

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.1
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

The `valkey-bundle` image includes JSON and Search modules needed for ValkeyStore. Verify:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install the Package

For the deterministic local sample, install its pinned dependencies:

```bash
python -m pip install -r sample/requirements.txt
```

This installs `ValkeySaver`, `ValkeyStore`, and `ValkeyCache` from
`langgraph-checkpoint-aws`. The runnable sample uses deterministic local
embeddings and does not require a hosted model or provider credentials.

## Step 3: Understand the Data Model

`ValkeySaver` stores each checkpoint as a JSON document in Valkey:

```python
# Key format: checkpoint:{thread_id}:{checkpoint_ns}:{checkpoint_id}
# Each checkpoint contains:
{
    "v": 1,
    "ts": "2026-03-12T10:00:00+00:00",
    "channel_values": {"messages": [...]},
    "channel_versions": {"__start__": 2, "messages": 3},
    "versions_seen": {...}
}
```

**Under the Hood:** `ValkeySaver` uses Valkey JSON (`JSON.SET`) for structured storage and `FT.CREATE`/`FT.SEARCH` for indexing checkpoints by thread ID and namespace. TTL is applied via `EXPIRE`.

## Step 4: Persist a LangGraph Agent

The following provider-neutral example uses the same public `ValkeySaver`
constructor as the local sample:

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph
from langgraph_checkpoint_aws import ValkeySaver
from valkey import Valkey


def chatbot(state: MessagesState):
    message = state["messages"][-1].content
    return {"messages": [AIMessage(content=f"Valkey received: {message}")]}


builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.set_entry_point("chatbot")
builder.set_finish_point("chatbot")

client = Valkey.from_url(
    "valkey://127.0.0.1:6379",
    decode_responses=False,
)
checkpointer = ValkeySaver(client=client, ttl=3600)

try:
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "session-1"}}

    result = graph.invoke(
        {"messages": [HumanMessage(content="What is Valkey?")]},
        config,
    )
    print(result["messages"][-1].content)

    # Continue the conversation - state is persisted!
    result = graph.invoke(
        {"messages": [HumanMessage(content="How fast is it?")]},
        config,
    )
    print(result["messages"][-1].content)
finally:
    client.close()
```

For a complete run that also demonstrates caching and semantic search, use
[`sample/main.py`](sample/main.py).

## Step 5: Verify Persistence

Stop and restart your script - the conversation state is still in Valkey:

Run this block from the sample directory so `main.py` is importable:

```python
# In a NEW Python process:
from main import Settings, create_checkpointer, create_valkey_client

settings = Settings.from_env()
client = create_valkey_client(settings)
config = {"configurable": {"thread_id": "session-1"}}

try:
    with create_checkpointer(settings, client=client) as checkpointer:
        for checkpoint in checkpointer.list(config):
            print(checkpoint.metadata)  # Shows previous conversation
finally:
    client.close()
```

## How It Works Under the Hood

| Operation | Valkey Command |
|-----------|---------------|
| Save checkpoint | `JSON.SET checkpoint:{thread}:{ns}:{id} $ '{...}'` |
| Set TTL | `EXPIRE checkpoint:{thread}:{ns}:{id} 3600` |
| Load latest | `FT.SEARCH checkpoints_idx '@thread_id:{session-1}' LIMIT 0 1` |
| List history | `FT.SEARCH checkpoints_idx '@thread_id:{session-1}'` |

**Source:** [`langgraph-checkpoint-aws`](https://github.com/langchain-ai/langgraph-checkpoint-aws) - the package that provides the Valkey checkpointer used here.

## Configuration Reference

| Option | Default | Description |
| --- | --- | --- |
| `VALKEY_URL` | `valkey://127.0.0.1:6379` | Valkey connection URL used by the sample. |
| `thread_id` | — | Identifier used to resume one conversation. |
| `ttl` | `3600` | Checkpoint retention in seconds. |

## Teardown

Remove the local Valkey container when you are done:

```bash
docker stop valkey
docker rm valkey
```

---

[Next: 02 LLM Response Caching →](02-llm-caching.md)
