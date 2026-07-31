# VoltAgent + Valkey Cookbook

> Build resilient AI agent services with VoltAgent and Valkey — persist A2A task state and enable resumable SSE streams backed by Valkey's key-value store and pub/sub.

## Cookbooks

| Cookbook | Level | Description |
| --- | --- | --- |
| [Getting Started](./01-getting-started.md) | Beginner | Set up VoltAgent with Valkey for A2A task persistence using ValkeyTaskStore |
| [Resumable Streams](./02-resumable-streams.md) | Intermediate | Add resumable SSE stream support with ValkeyResumableStreamStore and pub/sub |

## Prerequisites

- **Valkey 9.1+** (plain `valkey/valkey` — no search module needed)
- **Node.js 20+**
- **Docker** (for running Valkey)

## How VoltAgent Uses Valkey

VoltAgent integrates with Valkey through two stores, both using `@valkey/valkey-glide` as the client:

- **ValkeyTaskStore** (`@voltagent/a2a-server/valkey-store`) — persists A2A task state as JSON strings via SET/GET with optional TTL. Uses composite keys: `{prefix}:{agentId}::{taskId}`.
- **ValkeyResumableStreamStore** (`@voltagent/resumable-streams/valkey-store`) — enables resumable Server-Sent Events
  (SSE) streams using Valkey pub/sub for real-time messaging and key-value storage for stream state. Allocates one
  dedicated GlideClient per subscription channel.

Both stores support standalone and cluster deployment modes.

## Upstream Status

> **Note:** The Valkey stores are introduced in
> PR [VoltAgent/voltagent#1259](https://github.com/VoltAgent/voltagent/pull/1259)
> (currently OPEN). This cookbook documents the designed API so it's ready when the
> packages ship. The sample project tests validate the underlying Valkey patterns
> independently using the `@valkey/valkey-glide` client library (via the `redis`
> compatibility package in tests).

## Quick Start

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { createValkeyTaskStore } from "@voltagent/a2a-server/valkey-store";

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const taskStore = await createValkeyTaskStore({
  client,
  keyPrefix: "a2a-tasks",
  ttlSeconds: 86400, // 24 hours
});
```

---

[← Back to Valkey Samples](../../../README.md)
