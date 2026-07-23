# Getting Started with Recall and Valkey

> Give your AI agent persistent memory that survives session restarts,
> context compaction, and window limits — backed by Valkey.

**Beginner** · TypeScript/Node.js · ~10 min

**Who is this for:** Developers using Claude Desktop or Claude Code who want
persistent cross-session memory without relying on a managed service.
You should be comfortable running Docker containers and editing JSON config files.

## Prerequisites

- Docker (for Valkey) or a running Valkey instance
- Node.js 18+ and npm
- Claude Desktop or Claude Code

> **Security note:** Recall stores conversation context that may include
> credentials, code, and business logic. Always use a dedicated Valkey instance
> with authentication enabled. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Step 1: Start Valkey

```bash
docker run -d --name valkey-recall \
  -p 6379:6379 \
  valkey/valkey:8.1.1 \
  --requirepass your-secure-password
```

Verify it's running:

```bash
docker exec valkey-recall valkey-cli -a your-secure-password PING
# → PONG
```

## Step 2: Install Recall

The simplest approach — no global install needed:

```bash
npx -y @joseairosa/recall
```

Or install globally:

```bash
npm install -g @joseairosa/recall
```

## Step 3: Configure Claude for Valkey Backend

Recall supports Valkey as a first-class backend via `@valkey/valkey-glide`.
Set `BACKEND_TYPE=valkey` to use it.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "recall": {
      "command": "npx",
      "args": ["-y", "@joseairosa/recall"],
      "env": {
        "BACKEND_TYPE": "valkey",
        "VALKEY_HOST": "localhost",
        "VALKEY_PORT": "6379",
        "ANTHROPIC_API_KEY": "your-anthropic-api-key"
      }
    }
  }
}
```

### Claude Code

Edit `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "recall": {
      "command": "recall",
      "env": {
        "BACKEND_TYPE": "valkey",
        "VALKEY_HOST": "localhost",
        "VALKEY_PORT": "6379",
        "ANTHROPIC_API_KEY": "your-anthropic-api-key"
      }
    }
  }
}
```

## Step 4: Restart Claude and Test

Restart Claude Desktop or Claude Code to load the MCP server.

Then ask Claude:

```text
Store a memory that I prefer using Valkey over Redis for all new projects
```

In a **new conversation**, ask:

```text
What do you know about my infrastructure preferences?
```

Claude should recall your preference — the memory persisted across sessions.

## How It Works

```text
┌──────────────┐     MCP      ┌──────────────┐    Glide    ┌──────────────┐
│ Claude       │◄────────────►│ Recall       │◄───────────►│ Valkey       │
│ (Desktop/    │   stdio      │ (MCP Server) │  TCP 6379   │ (Storage)    │
│  Code)       │              │              │             │              │
└──────────────┘              └──────────────┘             └──────────────┘
```

1. Claude sends memory operations via MCP (store, search, recall)
2. Recall processes the request, generates embeddings (128-dim keyword/trigram vectors)
3. Valkey stores the memory as a hash with metadata, content, and embedding
4. On retrieval, Recall computes cosine similarity across stored embeddings
5. Results are returned to Claude as relevant context

## Key Data Structures in Valkey

Recall stores data using these patterns:

```bash
# Memory hash (one per memory)
HGETALL "recall:ws:<workspace_hash>:memory:<uuid>"
# Fields: content, type, tags, importance, embedding, created_at, updated_at

# Workspace index (sorted set for recency)
ZRANGE "recall:ws:<workspace_hash>:index" 0 -1

# Global memories (when WORKSPACE_MODE=global or hybrid)
HGETALL "recall:global:memory:<uuid>"
```

Inspect what's stored:

```bash
docker exec valkey-recall valkey-cli -a your-secure-password \
  KEYS "recall:*"
```

## Configuration Reference

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `BACKEND_TYPE` | `redis` | Set to `valkey` for Valkey backend |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
| `VALKEY_DB` | `0` | Valkey database number |
| `ANTHROPIC_API_KEY` | — | Required for embeddings and analysis |
| `WORKSPACE_MODE` | `isolated` | Memory scope: `isolated`, `global`, or `hybrid` |

## Troubleshooting

### "Connection refused" errors

Verify Valkey is running and accessible:

```bash
docker exec valkey-recall valkey-cli -a your-secure-password PING
```

### Memories not persisting

Check that `BACKEND_TYPE` is set to `valkey` (not the default `redis`).
Without this, Recall tries to connect via the `REDIS_URL` pattern instead.

### Claude doesn't show Recall tools

1. Ensure the MCP server config JSON is valid (no trailing commas)
2. Check that `npx @joseairosa/recall` runs without errors in your terminal
3. Restart Claude completely (quit and reopen, not just close the window)

---

**Next:** [Workspace Memory →](02-workspace-memory.md)

---

[← Back to Recall Cookbook](README.md)
