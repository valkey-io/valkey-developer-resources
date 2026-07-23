# Workspace Memory with Recall and Valkey

> Organize AI memories by project with workspace isolation, share knowledge
> globally, or use hybrid mode for the best of both worlds.

**Intermediate** · TypeScript/Node.js · ~15 min

**Who is this for:** Developers managing multiple projects who want fine-grained
control over which memories are shared and which stay project-specific.
You should have completed the [Getting Started](01-getting-started.md) guide.

## Prerequisites

- Recall configured with Valkey backend (from Getting Started)
- At least two project directories to demonstrate isolation

> **Security note:** Global memories are accessible from any workspace.
> Never store credentials or secrets as global memories. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Workspace Modes

Recall supports three workspace modes, controlled by the `WORKSPACE_MODE`
environment variable:

| Mode | Behavior | Use Case |
| ---- | -------- | -------- |
| `isolated` (default) | Each directory has its own memory space | Multi-project development |
| `global` | All memories shared across all workspaces | Personal knowledge base |
| `hybrid` | Workspace-specific + global memories coexist | Team + personal patterns |

## How Workspace Isolation Works

In `isolated` mode (default), Recall hashes the working directory path to create
a unique namespace in Valkey:

```text
/Users/you/project-alpha/  → recall:ws:a1b2c3...:memory:*
/Users/you/project-beta/   → recall:ws:d4e5f6...:memory:*
```

This means:

- Memories stored while working in `project-alpha` are invisible from `project-beta`
- Each workspace has its own index, categories, and relationships
- No configuration needed — isolation happens automatically

### Verify Isolation in Valkey

```bash
# List all workspace namespaces
docker exec valkey-recall valkey-cli -a your-secure-password \
  KEYS "recall:ws:*:index"

# Count memories per workspace
docker exec valkey-recall valkey-cli -a your-secure-password \
  ZCARD "recall:ws:<workspace_hash>:index"
```

## Global Memories

Set `WORKSPACE_MODE=global` to share all memories across every workspace:

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
        "WORKSPACE_MODE": "global",
        "ANTHROPIC_API_KEY": "your-anthropic-api-key"
      }
    }
  }
}
```

Global memories are stored under a shared prefix:

```bash
# Global memory keys
docker exec valkey-recall valkey-cli -a your-secure-password \
  KEYS "recall:global:*"
```

### When to Use Global Mode

- Personal coding standards that apply everywhere
- Organizational conventions (naming, architecture patterns)
- Infrastructure knowledge (deployment procedures, credentials locations)
- Cross-project decisions ("we always use Valkey for caching")

## Hybrid Mode

The most flexible option. `WORKSPACE_MODE=hybrid` gives you:

- Workspace-specific memories (auto-isolated by directory)
- Global memories (accessible from anywhere)
- Tools to promote/demote between scopes

```json
{
  "env": {
    "WORKSPACE_MODE": "hybrid"
  }
}
```

### Converting Between Scopes

Once in hybrid mode, use these Recall tools via Claude:

**Promote a workspace memory to global:**

```text
Convert the memory about our logging conventions to global
```

This calls the `convert_to_global` tool, moving the memory from
`recall:ws:<hash>:memory:<id>` to `recall:global:memory:<id>`.

**Demote a global memory to workspace-specific:**

```text
Convert the memory about this project's API design to workspace-only
```

This calls `convert_to_workspace`, scoping it back to the current directory.

### Hybrid Key Layout in Valkey

```bash
# Workspace-specific memories
recall:ws:<hash>:memory:<uuid>
recall:ws:<hash>:index

# Global memories (accessible from any workspace)
recall:global:memory:<uuid>
recall:global:index
```

## Memory Relationships

Recall (v1.4+) supports linking related memories into a graph:

```text
Link the "API authentication" memory to "JWT token format" memory
```

This creates relationship entries in Valkey:

```bash
# Relationships stored as sorted sets
recall:ws:<hash>:relations:<memory_id>
# Members are related memory IDs with relevance scores
```

### Traversing the Graph

```text
What memories are related to our authentication approach?
```

Recall follows links to provide connected context, even across
relationship chains (A → B → C).

## Organizing Memories by Category

Use categories (v1.5+) to group memories:

```text
Set the category of that memory to "architecture-decisions"
```

```text
Show me all memories in the "coding-standards" category
```

Categories are stored as tags on the memory hash and indexed for fast retrieval.

## Valkey Memory Usage

Each memory consumes approximately:

- ~500 bytes for metadata (type, tags, importance, timestamps)
- ~200 bytes for the 128-dimensional embedding (stored as binary float array)
- Variable content size (typically 100–2000 bytes)

For a typical developer with 1000 memories: **~1–2 MB** total Valkey usage.

Monitor with:

```bash
docker exec valkey-recall valkey-cli -a your-secure-password INFO memory
```

## Backup and Restore

### Export memories (via Claude)

```text
Export all my memories to JSON
```

This uses the `export_memories` tool to dump all workspace memories.

### Direct Valkey backup

```bash
# RDB snapshot
docker exec valkey-recall valkey-cli -a your-secure-password BGSAVE

# Copy the dump file
docker cp valkey-recall:/data/dump.rdb ./recall-backup.rdb
```

### Import memories

```text
Import memories from the JSON file at ./memories-backup.json
```

## Multi-Machine Sync

To share memories across machines, point all instances to the same Valkey server:

```json
{
  "env": {
    "BACKEND_TYPE": "valkey",
    "VALKEY_HOST": "your-valkey-server.internal",
    "VALKEY_PORT": "6379",
    "WORKSPACE_MODE": "hybrid"
  }
}
```

All Claude instances connecting to the same Valkey will share global memories
and see the same workspace memories when working in the same directory path.

---

**Next:** [Production Deployment →](03-production-deployment.md)

---

[← Back to Recall Cookbook](README.md)
