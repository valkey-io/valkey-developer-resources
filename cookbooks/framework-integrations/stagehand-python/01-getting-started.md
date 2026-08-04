# Getting Started with Stagehand Python + Valkey

> Use the Stagehand Python SDK with a Valkey-backed server so that act() and agent() actions are cached and replayed without LLM inference on subsequent runs.

**Beginner** · Python · ~15 min

**Who is this for:** Python developers driving Stagehand browser automation via the server API who want act/agent results cached in Valkey instead of on one machine's filesystem.

Stagehand's `act()` and agent `execute()` methods can cache their resolved actions so that identical instructions replay instantly on subsequent runs.
Configuring a Valkey backend enables shared caching across machines, TTL-based expiry, and zero local disk usage.

There are two ways to run Stagehand with Valkey:

1. **Server mode** - run the Stagehand server with Valkey env vars (recommended for shared/remote Valkey)
2. **Local mode** - pass `valkey_host` to the client constructor (Valkey config forwarded to the embedded server process)

Stagehand is [Browserbase](https://www.browserbase.com/)'s open-source browser automation framework.
Valkey support for the core server ([browserbase/stagehand#2264](https://github.com/browserbase/stagehand/pull/2264)) and for this Python SDK
([browserbase/stagehand-python#346](https://github.com/browserbase/stagehand-python/pull/346)) are both open but not yet merged, so this cookbook
installs from the maintainer-reviewed forks that implement them — see Steps 2 and 3.

## Prerequisites

- Docker installed
- Python 3.9+
- Node.js 18+ and [pnpm](https://pnpm.io/) 9.x (for the Stagehand server)
- An API key for an LLM provider (OpenAI, Anthropic, Google, etc.) — exported as `MODEL_API_KEY`

## Step 1: Start Valkey

```bash
# Docker
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
```

```bash
# Podman
podman run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
```

```bash
docker exec valkey valkey-cli PING
# PONG
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/) and [03 - Production Configuration](03-production-configuration.md).

## Step 2: Start the Stagehand Server

Valkey caching isn't in a released `stagehand` server yet, so run it from the fork that implements it:

```bash
git clone https://github.com/edlng/stagehand.git
cd stagehand
git checkout e94a0ad06b717b3b7897797153d954dc4147e12a
pnpm install --ignore-scripts --no-frozen-lockfile
cd packages/server-v3

VALKEY_HOST=localhost \
VALKEY_PORT=6379 \
VALKEY_KEY_PREFIX=stagehand \
VALKEY_CACHE_TTL=3600 \
PORT=3000 \
npx tsx src/server.ts
```

Once [#2264](https://github.com/browserbase/stagehand/pull/2264) merges and releases, you can run the published server instead and skip the clone.

## Step 3: Set Up the Python Project

In a new terminal:

```bash
mkdir stagehand-valkey-demo && cd stagehand-valkey-demo
python -m venv .venv && source .venv/bin/activate
pip install "git+https://github.com/edlng/stagehand-python.git@e4bbc4d0268fe83f2fea195621ecd32c4c624a3a"
```

Once [browserbase/stagehand-python#346](https://github.com/browserbase/stagehand-python/pull/346) merges and releases, replace the last command with `pip install stagehand`.

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

    try:
        client.sessions.navigate(id=session_id, url="https://www.example.com")

        # First run: resolves via LLM. Second run: replays from Valkey cache.
        client.sessions.act(id=session_id, input="click on the More information link")

        print("Action completed")
    finally:
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
valkey-cli SCAN 0 MATCH "stagehand:*"
# 1) "0"
# 2) 1) "stagehand:act:6b1333ed9a7c85bf..."

valkey-cli TTL "stagehand:act:6b1333ed9a7c85bf..."
# 3590
```

`SCAN` is used here instead of `KEYS` — `KEYS` blocks the server while it scans the whole keyspace, which is fine for this tiny demo but a habit worth not forming.
`SCAN` returns a two-element reply instead: the next cursor (`"0"` means the iteration is complete) and the array of matching keys found so far — shown above as item 2, itself a numbered array.

## What Happens Under the Hood

When the server has `VALKEY_HOST` configured, Stagehand:

1. Connects to Valkey via `iovalkey`
2. On `act()` or agent `execute()`, hashes the instruction + page context into a cache key
3. Stores the resolved action sequence as JSON under `stagehand:act:<hash>` or `stagehand:agent:<hash>`
4. On repeat calls, reads the cached entry with `GET` and replays the actions directly

If the Valkey connection fails at startup, Stagehand logs a warning and falls back to disabled caching. The automation still runs, just without cache benefits.

---

[02 - Cache Categories and TTL →](02-cache-categories-and-ttl.md)
