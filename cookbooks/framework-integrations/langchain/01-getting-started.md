# Getting Started with LangChain + Valkey

> Start the local LangGraph sample and see how `ValkeySaver` persists conversation state in Valkey.

**Beginner** · Python · ~15 min

**Who is this for:** This page is for Python developers who want a small,
repeatable starting point for LangGraph checkpoint persistence without cloud
credentials.

## Prerequisites

- Python 3.10 or newer
- Docker with Compose
- The files in [`sample/`](sample/), including `main.py`, `requirements.txt`, and `docker-compose.yml`

## Step 1: Open the sample

Run the remaining commands from the sample directory:

```bash
cd cookbooks/framework-integrations/langchain/sample
```

The sample is the canonical runnable path for this cookbook. It creates a Valkey
client from `Settings.from_env()`, constructs the three LangGraph checkpoint,
cache, and store resources, runs the local demo, and cleans up data belonging to
that run.

## Step 2: Start Valkey

Start the pinned Valkey bundle:

```bash
docker compose up -d
docker compose exec valkey valkey-cli ping
# PONG
```

The bundle provides the JSON and Search capabilities used by `ValkeyStore`.

> **Security:** The Compose file binds port `6379` to loopback (`127.0.0.1`) by
> default. Keep that binding for local work, do not publish Valkey on `0.0.0.0`,
> and do not put credentials or private application data in this demo. A shared
> or production deployment needs an approved network boundary plus authentication
> and TLS settings; this local sample does not configure those controls.

## Step 3: Install the pinned requirements

Create an isolated environment and install the versions used by the sample:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Step 4: Construct a checkpointer

`main.py` uses the same public constructor directly inside `create_checkpointer`:

```python
from langgraph_checkpoint_aws import ValkeySaver
from main import (
    Settings,
    cleanup_sample,
    create_valkey_client,
    run_checkpoint_demo,
)

settings = Settings.from_env()
client = create_valkey_client(settings)
checkpointer = ValkeySaver(
    client=client,
    ttl=settings.checkpoint_ttl_seconds,
)

try:
    result = run_checkpoint_demo(
        checkpointer,
        thread_id="lesson-1",
        message="I am learning how Valkey stores state.",
    )
    print(result)
finally:
    cleanup_sample(client, settings=settings, run_id="lesson-1")
    client.close()
```

The `client`, `ttl`, `thread_id`, and `message` arguments match the sample's
construction and helper signatures. The full sample uses its managed factory so
cleanup also handles resources created by the other two components.

## Step 5: Verify persistence after restart

The checkpoint contains graph state associated with a thread. Recreate the
checkpointer and invoke the same thread to verify that the earlier message is
loaded:

```python
from main import (
    Settings,
    cleanup_sample,
    create_checkpointer,
    create_valkey_client,
    run_checkpoint_demo,
)

settings = Settings.from_env()
client = create_valkey_client(settings)
try:
    with create_checkpointer(settings, client=client) as checkpointer:
        first = run_checkpoint_demo(
            checkpointer,
            thread_id="restart-check",
            message="first message",
        )
    with create_checkpointer(settings, client=client) as checkpointer:
        second = run_checkpoint_demo(
            checkpointer,
            thread_id="restart-check",
            message="message after reopening",
        )
    print(first)
    print(second)
finally:
    cleanup_sample(client, settings=settings, run_id="restart-check")
    client.close()
```

The second result contains both messages. In a service, the second block can
run in a later process as long as it uses the same Valkey URL and thread ID.

## Checkpoint data model

The integration serializes checkpoint state together with thread and namespace
metadata. The exact serialized representation is an implementation detail, but
the conceptual record looks like this:

```python
{
    "thread_id": "restart-check",
    "checkpoint_ns": "",
    "channel_values": {"messages": ["first message"]},
    "metadata": {"source": "input"},
}
```

| Operation | Public API | Retention |
| --- | --- | --- |
| Save graph state | `ValkeySaver` used by `graph.invoke` | `CHECKPOINT_TTL_SECONDS` |
| Load the latest state | Reuse the same `thread_id` | Until the TTL expires |
| Inspect history | `checkpointer.list(config)` | Same checkpoint TTL |

## Step 6: Run and verify the sample

Run the complete local demo:

```bash
python main.py
```

Then run the integration tests against the same local Valkey service:

```bash
python -m pytest -q test_langchain.py
```

The demo prints `checkpoint:`, `cache:`, and `semantic search:` results. Its `finally` block removes data created for the `demo` run, so use the tests when you want to verify state across two calls.

## How It Works

`run_checkpoint_demo` builds a one-node `StateGraph`, compiles it with the
supplied `ValkeySaver`, and invokes it with a `thread_id`. A second invocation
with the same thread identifier can load the earlier message from Valkey.
`Settings.from_env()` supplies the checkpoint TTL and connection timeout, while
`create_valkey_client` creates a byte-preserving client for the integration
classes.

Under the hood, the checkpoint package stores structured checkpoint records and
maintains Search indexes for lookup. The package may use Valkey JSON, Search,
key scans, and expiration operations as part of that lifecycle; learners should
use `ValkeySaver` rather than issuing those commands directly.

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

## Teardown

The sample removes its own run data after `main.py` finishes. Stop the pinned Valkey service and remove its Compose resources when you are done:

```bash
docker compose down --volumes
```

---

[Back to LangChain + Valkey](README.md) | [Next: 02 - LLM Response Caching](02-llm-caching.md)
