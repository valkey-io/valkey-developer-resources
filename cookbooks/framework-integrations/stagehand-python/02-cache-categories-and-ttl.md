# Cache Categories and TTL

> Understand how Stagehand namespaces cached actions into act and agent categories, configure key prefixes for multi-tenant setups, and set TTL to expire stale entries automatically.

**Intermediate** · Python · ~15 min

Stagehand stores two categories of cached actions in Valkey: `act` (single-step browser actions) and `agent` (multi-step task sequences). Understanding this structure lets you inspect, tune, and isolate cache data across environments or tenants.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- Valkey running on localhost:6379
- Stagehand server running on localhost:3000

## Step 1: Understand Key Structure

Stagehand keys follow the pattern:

```
{prefix}:{category}:{hash}
```

- **prefix** - configurable via `VALKEY_KEY_PREFIX` env var on the server (default: `"stagehand"`)
- **category** - either `act` or `agent`
- **hash** - deterministic hash of the instruction and page state

## Step 2: Configure a Custom Key Prefix

Start the server with a custom `VALKEY_KEY_PREFIX` to namespace cache keys per environment or tenant:

```bash
VALKEY_HOST=localhost VALKEY_KEY_PREFIX=myapp-staging CACHE_TTL=3600 \
  PORT=3000 npx tsx src/server.ts
```

Then connect the Python client:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url="http://localhost:3000",
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(model_name="gpt-4o-mini")
# ... actions store keys like myapp-staging:act:<hash>
```

Alternatively, pass `valkey_cache` per-session to override server defaults:

```python
session = client.sessions.start(
    model_name="gpt-4o-mini",
    valkey_cache={
        "host": "localhost",
        "port": 6379,
        "key_prefix": "myapp-staging",
        "cache_ttl": 3600,
    },
)
```

This stores keys like `myapp-staging:act:<hash>` instead of the default `stagehand:act:<hash>`.

## Step 3: Set TTL for Automatic Expiry

Set `CACHE_TTL` (in seconds) on the server to automatically expire stale cache entries. This is useful when pages change frequently and cached actions may become invalid:

```bash
VALKEY_HOST=localhost CACHE_TTL=3600 PORT=3000 npx tsx src/server.ts
```

Or per-session:

```python
session = client.sessions.start(
    model_name="gpt-4o-mini",
    valkey_cache={
        "host": "localhost",
        "cache_ttl": 3600,  # Entries expire after 1 hour
    },
)
```

Omitting `cache_ttl` means entries persist indefinitely until manually deleted.

## Step 4: Use the Agent Cache

The agent `execute()` method caches multi-step task sequences under the `agent` category:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url="http://localhost:3000",
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(
    model_name="gpt-4o-mini",
    valkey_cache={
        "host": "localhost",
        "key_prefix": "myapp",
        "cache_ttl": 7200,
    },
)
session_id = session.data.session_id

client.sessions.navigate(id=session_id, url="https://github.com/browserbase/stagehand")
client.sessions.execute(
    id=session_id,
    execute_options={
        "instruction": "Navigate to the Issues tab and find the newest open issue",
        "max_steps": 5,
    },
)
client.sessions.end(id=session_id)
client.close()
```

The resolved step sequence is stored at `myapp:agent:<hash>` and replays on subsequent calls with the same instruction.

## What Happens Under the Hood

| Action | Valkey Command | Key Example |
| --- | --- | --- |
| Cache write (no TTL) | `SET key value` | `myapp:act:a1b2c3d4` |
| Cache write (with TTL) | `SET key value EX 3600` | `myapp:agent:e5f6g7h8` |
| Cache read | `GET key` | `myapp:act:a1b2c3d4` |

---

[← 01 - Getting Started](01-getting-started.md) | [03 - Production Configuration →](03-production-configuration.md)
