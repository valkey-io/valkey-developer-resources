# Recall + Valkey Cookbook

> Persistent cross-session memory for Claude and AI agents, powered by Valkey.

[Recall](https://github.com/joseairosa/recall) is an MCP (Model Context Protocol) server that
gives AI agents persistent memory across sessions. Self-hosted Recall uses Valkey as its storage
backend via `@valkey/valkey-glide`, providing workspace-isolated or global memory with semantic search.

## Cookbooks

| # | Title | Difficulty | Description |
| --- | ----- | ---------- | ----------- |
| 1 | [Getting Started](01-getting-started.md) | Beginner | Install Recall with Valkey, store and retrieve your first memories |
| 2 | [Workspace Memory](02-workspace-memory.md) | Intermediate | Workspace isolation, global memories, hybrid mode |
| 3 | [Production Deployment](03-production-deployment.md) | Intermediate | TLS, Docker Compose, security hardening, monitoring |

## Prerequisites

- Valkey 7.2+ (or `valkey/valkey:latest`)
- Node.js 18+
- Claude Desktop or Claude Code (for MCP integration)

## How Recall Uses Valkey

Recall connects to Valkey via the official `@valkey/valkey-glide` client. Key patterns:

- **Memory storage:** Hash keys with metadata, content, and embedding vectors
- **Workspace isolation:** Key prefixes scoped by directory path
- **Semantic search:** Cosine similarity on 128-dimensional keyword/trigram embeddings
- **Global memories:** Cross-workspace keys accessible from any project
- **Relationships:** Graph-like links between memories stored as sorted sets

## Quick Start

```bash
# Start Valkey
docker run -d -p 6379:6379 valkey/valkey:8.1.1

# Configure Claude Desktop / Claude Code with Recall + Valkey backend
# See 01-getting-started.md for full setup
```

---

[← Back to Framework Integrations](../README.md)
