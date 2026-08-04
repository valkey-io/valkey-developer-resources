# Stagehand Python + Valkey Cookbook Sample

Runnable code for the [Stagehand Python + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.9+**
2. **Docker** (for Valkey)
3. **Node.js 18+** and [pnpm](https://pnpm.io/) 9.x (for the Stagehand server)
4. **A MODEL_API_KEY** (OpenAI, Anthropic, Google, or any Stagehand-supported LLM provider) — only needed for `demo.py`, not for the test suite

## Setup

Valkey caching isn't in released versions of the server or this SDK yet ([browserbase/stagehand#2264](https://github.com/browserbase/stagehand/pull/2264) and
[browserbase/stagehand-python#346](https://github.com/browserbase/stagehand-python/pull/346) are both open). Run both from the forks that implement them:

```bash
# Start Valkey
docker compose up -d

# Start the Stagehand server from the fork with Valkey support
git clone https://github.com/edlng/stagehand.git ../stagehand-fork
cd ../stagehand-fork && git checkout e94a0ad06b717b3b7897797153d954dc4147e12a && pnpm install --ignore-scripts
cd packages/server-v3
VALKEY_HOST=localhost VALKEY_PORT=6379 VALKEY_KEY_PREFIX=stagehand-demo \
  VALKEY_CACHE_TTL=3600 PORT=3000 npx tsx src/server.ts

# In another terminal, back in this sample/ directory:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Once both PRs merge and release, drop the fork clone/checkout and change the `stagehand` entry in `requirements.txt` back to a normal version pin.

## Running the demo

```bash
MODEL_API_KEY=your-key python demo.py
```

On the first run, Stagehand calls the LLM to resolve the browser action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed instantly.

Verify with:

```bash
valkey-cli SCAN 0 MATCH "stagehand-demo:*"
```

## Running the tests

```bash
pytest test_valkey_cache_config.py -v
```

This checks that `stagehand.types.ValkeyCacheOptions` still exposes the field names used in this cookbook, and uses the `valkey` client
directly to prove the `SET`/`GET`/`EX` commands and `{prefix}:{category}:{hash}` key scheme are valid Valkey usage, against a live container.
It does not import or call any code from the fork's server-side caching implementation, and does not start the Stagehand server or call
`demo.py`'s `act()` — those need the real server, a real browser, and a paid LLM call. It's a CI-friendly check that the documented
protocol is sound, not proof that the fork's actual caching code is bug-free.

## What It Demonstrates

| Topic | Cookbook | Config Used |
|-------|---------|-------------|
| Basic cached action | [01 - Getting Started](../01-getting-started.md) | `valkey_host`, `valkey_port` (server env) |
| Key prefix and TTL | [02 - Cache Categories and TTL](../02-cache-categories-and-ttl.md) | `VALKEY_KEY_PREFIX`, `VALKEY_CACHE_TTL` (server env) |
| TLS and auth | [03 - Production Configuration](../03-production-configuration.md) | `valkey_tls`, `valkey_username`, `valkey_password` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_API_KEY` | (required for `demo.py`) | LLM API key |
| `STAGEHAND_SERVER_URL` | `http://localhost:3000` | Stagehand server URL |

## Troubleshooting

- **Connection refused on port 3000**: Start the Stagehand server first (see Setup).
- **Connection refused on port 6379**: Start Valkey (`docker compose up -d`).
- **Missing MODEL_API_KEY**: Export the variable or prefix the run command. Not needed for the test suite.
- **No cache keys in Valkey**: Ensure the server was started with `VALKEY_HOST=localhost` and check that you're using `VALKEY_CACHE_TTL`, not `CACHE_TTL`
  — see the note in the [TypeScript track's Step 3](../../stagehand/03-production-configuration.md#step-3-server-side-configuration-via-environment-variables).

## Cleanup

```bash
docker compose down -v
```
