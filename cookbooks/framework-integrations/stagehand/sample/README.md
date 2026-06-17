# Stagehand + Valkey Cookbook Sample

Runnable code for the [Stagehand + Valkey cookbook series](../README.md).

## Prerequisites

1. **Node.js 18+**
2. **Docker** (for Valkey)
3. **An OpenAI API key** (or any Stagehand-supported LLM provider)

## Setup

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install
```

## Running

```bash
OPENAI_API_KEY=your-key npm run demo
```

On the first run, Stagehand calls the LLM to resolve the browser action. On the second run with the same instruction and page state, the cached result is read from Valkey and replayed instantly.

## What It Demonstrates

| Topic | Cookbook | Config Used |
|-------|---------|-------------|
| Basic cached action | [01 - Getting Started](../01-getting-started.md) | `valkeyHost`, `valkeyPort` |
| Key prefix and TTL | [02 - Cache Categories and TTL](../02-cache-categories-and-ttl.md) | `valkeyKeyPrefix`, `cacheTtl` |
| TLS and auth (commented) | [03 - Production Configuration](../03-production-configuration.md) | `valkeyTls`, `valkeyUsername`, `valkeyPassword` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | LLM API key (OpenAI shown; any Stagehand-supported provider works) |
| `VALKEY_HOST` | `localhost` | Valkey host address |
| `VALKEY_PORT` | `6379` | Valkey port |
| `VALKEY_USERNAME` | — | Valkey ACL username (production) |
| `VALKEY_PASSWORD` | — | Valkey auth password/token (production) |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running (`docker compose up -d`).
- **Missing OPENAI_API_KEY**: Export the variable or prefix the run command.
- **Stagehand browser error**: Ensure Chromium/Chrome is installed locally (Stagehand uses Playwright under the hood).
