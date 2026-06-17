# Getting Started with Stagehand Python + Valkey

> Use the Stagehand Python SDK with a Valkey-backed server so that act() and agent() actions are cached and replayed without LLM inference on subsequent runs.

**Beginner** · Python · ~15 min

Stagehand's `act()` and agent `execute()` methods can cache their resolved actions so that identical instructions replay instantly on subsequent runs. Configuring a Valkey backend enables shared caching across machines, TTL-based expiry, and zero local disk usage.

There are two ways to run Stagehand with Valkey:

1. **Server mode** - run the Stagehand server with Valkey env vars (recommended, full cache support)
2. **Local mode** - pass `valkey_host` to the client constructor (config accepted, cache requires server-side support)

## Prerequisites

- Docker installed
- Python 3.9+
- Node.js 18+ (for the Stagehand server)
- An API key for an LLM provider (OpenAI, Anthropic, Google, etc.) — exported as `MODEL_API_KEY`

> **Note**: The pre-built SEA binary (`server="local"`) accepts Valkey configuration parameters but cannot connect to Valkey at runtime because `@valkey/valkey-glide` relies on a native Rust addon that cannot be embedded in a single-executable binary. To use Valkey caching, run the Stagehand server from source as shown below.

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Start the Stagehand Server

If not already started, from the Stagehand repo, start the server:

```bash
git clone https://github.com/browserbase/stagehand.git
cd stagehand/packages/server-v3

VALKEY_HOST=localhost \
VALKEY_PORT=6379 \
VALKEY_KEY_PREFIX=stagehand \
CACHE_TTL=3600 \
PORT=3000 \
npx tsx src/server.ts
```

## Step 3: Set Up the Python Project

```bash
mkdir stagehand-valkey-demo && cd stagehand-valkey-demo
python -m venv .venv && source .venv/bin/activate
pip install stagehand
```

## Step 4: Create a Cached Browser Action

Create `demo.py`:

```python
import os
from stagehand import Stagehand

def main():
    client = Stagehand(
        base_url="http://localhost:3000",
        model_api_key=os.environ["MODEL_API_KEY"],
    )

    session = client.sessions.start(
        model_name="gpt-4o-mini",
        browser={"type": "local", "launchOptions": {"headless": True}},
    )
    session_id = session.data.session_id

    client.sessions.navigate(id=session_id, url="https://www.example.com")

    # First run: resolves via LLM. Second run: replays from Valkey cache.
    client.sessions.act(id=session_id, input="click on the More information link")

    print("Action completed")
    client.sessions.end(id=session_id)
    client.close()

if __name__ == "__main__":
    main()
```

Run it:

```bash
MODEL_API_KEY=your-key python demo.py
```

On the first run Stagehand calls the LLM to resolve the action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed without any LLM call.

## Step 5: Verify the Cache

```bash
valkey-cli SCAN 0
# stagehand:act:6b1333ed9a7c85bf...

valkey-cli TTL "stagehand:act:6b1333ed..."
# 3590
```

## What Happens Under the Hood

When the server has `VALKEY_HOST` configured, Stagehand:

1. Connects to Valkey via `@valkey/valkey-glide` (GlideClient)
2. On `act()` or agent `execute()`, hashes the instruction + page context into a cache key
3. Stores the resolved action sequence as JSON under `stagehand:act:<hash>` or `stagehand:agent:<hash>`
4. On repeat calls, reads the cached entry with `GET` and replays the actions directly

If the Valkey connection fails at startup, Stagehand logs a warning and falls back to disabled caching. The automation still runs, just without cache benefits.

---

[02 - Cache Categories and TTL →](02-cache-categories-and-ttl.md)
