# Production Configuration

> Configure TLS, ACL authentication, and environment variable-based setup for deploying Stagehand with Valkey in production.

**Intermediate** · Python · ~15 min

Moving from a local dev setup to production means adding TLS encryption, authentication, and configuring the Stagehand server to connect to a managed Valkey instance.

## Prerequisites

- Completed [01 - Getting Started](01-getting-started.md)
- A Valkey instance with TLS and/or ACL authentication (e.g., AWS ElastiCache for Valkey, or a self-hosted TLS-enabled instance)

## Step 1: Server-Side Configuration via Environment Variables

Configure the Stagehand server with production Valkey settings:

```bash
export VALKEY_HOST=my-valkey.example.com
export VALKEY_PORT=6379
export VALKEY_TLS=true
export VALKEY_USERNAME=stagehand-svc
export VALKEY_PASSWORD=secret-token
export CACHE_TTL=3600
export VALKEY_KEY_PREFIX=prod-stagehand

npx tsx src/server.ts
```

The server reads these at startup. Every session uses these defaults automatically.

## Step 2: Connect the Python Client

The Python client connects to the server as normal - no Valkey config needed on the client side:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url=os.environ["STAGEHAND_SERVER_URL"],
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(model_name="gpt-4o-mini")
# ... automation code, caching happens server-side ...
client.sessions.end(id=session.data.session_id)
client.close()
```

## Step 3: Per-Session Override via the Client API

Clients can override server-side Valkey defaults for a specific session using `valkey_cache`:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    base_url=os.environ["STAGEHAND_SERVER_URL"],
    model_api_key=os.environ["MODEL_API_KEY"],
)

session = client.sessions.start(
    model_name="gpt-4o-mini",
    valkey_cache={
        "host": "custom-valkey.internal",
        "port": 6379,
        "use_tls": True,
        "password": os.environ["CUSTOM_VALKEY_TOKEN"],
        "cache_ttl": 1800,
        "key_prefix": "team-a",
    },
)
# ... automation code ...
client.sessions.end(id=session.data.session_id)
client.close()
```

This overrides any server-side environment defaults for that session.

## Step 4: Client Constructor Params (Local Mode)

When using `server="local"`, pass Valkey config directly to the constructor. These parameters are forwarded as environment variables to the server process. Note that the pre-built SEA binary cannot load the native `@valkey/valkey-glide` addon, so this mode requires running the server from source for actual Valkey connectivity:

```python
import os
from stagehand import Stagehand

client = Stagehand(
    server="local",
    model_api_key=os.environ["MODEL_API_KEY"],
    valkey_host=os.environ["VALKEY_HOST"],
    valkey_port=6379,
    valkey_tls=True,
    valkey_username=os.environ["VALKEY_USERNAME"],
    valkey_password=os.environ["VALKEY_PASSWORD"],
    cache_ttl=3600,
    valkey_key_prefix="prod-stagehand",
)
```

These params are passed as environment variables to the underlying server process.

## Graceful Degradation

If the Valkey connection fails (wrong host, network issues, auth failure), Stagehand logs the error and continues with caching disabled. Automations still execute, they just make LLM calls on every run instead of replaying cached actions.

```
[cache] unable to initialize valkey cache: connection refused
```

No exceptions are thrown and no automation is interrupted.

---

[← 02 - Cache Categories and TTL](02-cache-categories-and-ttl.md)
