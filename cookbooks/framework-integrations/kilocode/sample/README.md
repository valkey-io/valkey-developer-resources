# Kilocode + Valkey Cookbook Sample

Companion scripts for the [Kilocode + Valkey cookbook series](../README.md).

> **Note**: You don't use these scripts to run Kilocode — all indexing and search happens automatically through the Kilocode VS Code extension or CLI. These scripts exist to **inspect** what Kilocode stored in Valkey and to **demonstrate** the underlying GLIDE patterns in a standalone, runnable form.

## Prerequisites

1. **Node.js 18+**
2. **Docker** (for Valkey)

## Setup

```bash
# Start Valkey with ValkeySearch module
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies
npm install
```

## Running

```bash
# Inspect a Kilocode-created index (run after Kilocode has indexed a project)
npx tsx inspect-index.ts

# Standalone vector store example (same GLIDE patterns Kilocode uses internally)
npx tsx standalone-vector-store.ts
```

## Sample Scripts

| Script | Cookbook | What it does |
|--------|---------|--------------|
| `inspect-index.ts` | [02 - How It Works](../02-how-it-works.md) | Connects to Valkey, discovers the Kilocode index, shows FT.INFO, dumps a sample hash, and runs a KNN self-search |
| `standalone-vector-store.ts` | [02 - How It Works](../02-how-it-works.md) | Minimal standalone example: creates an index, upserts vectors with TAG fields, searches with directory filtering — same patterns Kilocode uses internally |

## Why these scripts?

Kilocode manages indexing entirely through its UI/CLI — you configure the Valkey URL, and it handles index creation, embedding, and search behind the scenes. These scripts let you:

1. **Verify** that Kilocode wrote data correctly (inspect-index)
2. **Understand** the GLIDE API patterns without needing the full Kilocode stack (standalone-vector-store)
3. **Experiment** with ValkeySearch queries against real or synthetic data

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **No index found**: Run `inspect-index.ts` after Kilocode has indexed a project, or run `standalone-vector-store.ts` to create a sample index.
