# Stagehand + Valkey Cookbook Sample

Runnable code for the [Stagehand + Valkey cookbook series](../README.md).

## Prerequisites

1. **Node.js 18+** and [pnpm](https://pnpm.io/) 9.x
2. **Docker** (for Valkey)
3. **An OpenAI API key** (or any Stagehand-supported LLM provider) — only needed for `npm run demo`, not for the test suite

## Setup

Valkey caching isn't in a published `@browserbasehq/stagehand` release yet ([browserbase/stagehand#2264](https://github.com/browserbase/stagehand/pull/2264) is open, unmerged).
Build it from the fork that implements it:

```bash
# Start Valkey
docker compose up -d

# Build the Valkey-cache fork as a sibling of this directory
git clone https://github.com/edlng/stagehand.git ../stagehand-fork
(cd ../stagehand-fork && git checkout e94a0ad06b717b3b7897797153d954dc4147e12a && pnpm install --ignore-scripts && npx turbo run build --filter=@browserbasehq/stagehand)

# Install sample dependencies (package.json points at the fork build above)
npm install
```

Once #2264 merges and ships in a release, drop the `git clone`/build step and change the `@browserbasehq/stagehand` entry in `package.json` back to a normal version range.

## Running the demo

```bash
OPENAI_API_KEY=your-key npm run demo
```

On the first run, Stagehand calls the LLM to resolve the browser action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed instantly.

## Running the tests

```bash
npm test
```

`__tests__/cache-contract.test.ts` uses `iovalkey` directly — the same client Stagehand's `CacheStorage.createValkey()` uses internally — to prove the
`SET`/`GET`/`EX` commands and `{prefix}:{category}:{hash}` key scheme documented in [02](../02-cache-categories-and-ttl.md) are valid Valkey usage.
It does **not** import or call any code from the fork, and does **not** exercise `demo.ts`'s real `act()`/`agent()` calls (those need a paid LLM and a real browser).
It's a CI-friendly check that the documented protocol is sound, not proof that the fork's actual caching code path is bug-free.

## What It Demonstrates

| Topic | Cookbook | Config Used |
|-------|---------|-------------|
| Basic cached action | [01 - Getting Started](../01-getting-started.md) | `valkeyHost`, `valkeyPort` |
| Key prefix and TTL | [02 - Cache Categories and TTL](../02-cache-categories-and-ttl.md) | `valkeyKeyPrefix`, `cacheTtl` |
| TLS and auth (commented) | [03 - Production Configuration](../03-production-configuration.md) | `valkeyTls`, `valkeyUsername`, `valkeyPassword` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required for `npm run demo`) | LLM API key (OpenAI shown; any Stagehand-supported provider works) |
| `VALKEY_HOST` | `localhost` | Valkey host address |
| `VALKEY_PORT` | `6379` | Valkey port |
| `VALKEY_USERNAME` | — | Valkey ACL username (production) |
| `VALKEY_PASSWORD` | — | Valkey auth password/token (production) |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running (`docker compose up -d`).
- **Missing OPENAI_API_KEY**: Export the variable or prefix the run command. Not needed for `npm test`.
- **Stagehand browser error**: Ensure Chromium/Chrome is installed locally (Stagehand uses Playwright under the hood).
- **`npm install` fails on the fork**: Make sure you ran `npx turbo run build --filter=@browserbasehq/stagehand` inside `../stagehand-fork` first.
  A plain `npm install github:edlng/stagehand` fails because it triggers the monorepo's full `prepare` script instead of just building `packages/core`.

## Cleanup

```bash
docker compose down -v
```
