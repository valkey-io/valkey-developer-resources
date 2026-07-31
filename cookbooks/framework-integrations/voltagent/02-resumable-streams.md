# Resumable Streams with VoltAgent and Valkey

> Enable clients to reconnect to SSE streams without losing events, using Valkey pub/sub for real-time delivery and key-value storage for stream state.

**Intermediate** · TypeScript · ~20 min

**Who is this for:** Developers building agent services that stream responses via Server-Sent Events (SSE) and need clients to resume after disconnections without replaying from scratch.

## Prerequisites

- Node.js 20+
- Docker (for running Valkey)
- Completed [01-getting-started.md](./01-getting-started.md) (familiar with VoltAgent + Valkey setup)

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey

Same as the getting-started guide — plain Valkey with pub/sub support (built-in, no modules needed):

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:9.1.0
```

## Step 2: Install Packages

```bash
npm install @voltagent/resumable-streams @valkey/valkey-glide
```

- `@voltagent/resumable-streams` — Resumable SSE stream abstraction with the ValkeyResumableStreamStore factory
- `@valkey/valkey-glide` — official Valkey client (peer dependency, >=2.3.1)

## Step 3: Create the Resumable Stream Store

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { createResumableStreamValkeyStore } from "@voltagent/resumable-streams/valkey-store";

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const streamStore = await createResumableStreamValkeyStore({
  client,
  clientConfig: { addresses: [{ host: "localhost", port: 6379 }] },
  keyPrefix: "resumable-stream",
  ttlSeconds: 3600, // Active stream keys expire after 1 hour
  maxSubscriptions: 100, // Cap on concurrent pub/sub channels
});
```

## Step 4: Understand the Pub/Sub Model

The `ValkeyResumableStreamStore` uses a **one-client-per-channel** architecture:

```text
┌─────────────────────────────────────────────────────────────┐
│ VoltAgent Server                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stream A ──► GlideClient #1 ──► SUBSCRIBE stream:task_1   │
│  Stream B ──► GlideClient #2 ──► SUBSCRIBE stream:task_2   │
│  Stream C ──► GlideClient #3 ──► SUBSCRIBE stream:task_3   │
│                                                             │
│  Publisher ──► Shared GlideClient ──► PUBLISH stream:*      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Why one client per channel?** Valkey's pub/sub protocol puts a connection into subscriber mode — once subscribed,
it cannot execute other commands. Each active stream subscription requires its own dedicated connection.

The `maxSubscriptions` setting caps the number of concurrent subscriber connections to prevent resource exhaustion.

## Step 5: Wire into Your A2A Server

```typescript
import { GlideClient } from "@valkey/valkey-glide";
import { A2AServer } from "@voltagent/a2a-server";
import { createValkeyTaskStore } from "@voltagent/a2a-server/valkey-store";
import { createResumableStreamValkeyStore } from "@voltagent/resumable-streams/valkey-store";

const client = await GlideClient.createClient({
  addresses: [{ host: "localhost", port: 6379 }],
});

const taskStore = await createValkeyTaskStore({
  client,
  keyPrefix: "a2a-tasks",
  ttlSeconds: 86400,
});

const streamStore = await createResumableStreamValkeyStore({
  client,
  clientConfig: { addresses: [{ host: "localhost", port: 6379 }] },
  keyPrefix: "resumable-stream",
  ttlSeconds: 3600,
  maxSubscriptions: 100,
});

const server = new A2AServer({
  agentId: "streaming-agent",
  taskStore,
  streamStore, // Enables resumable SSE
  handler: async (task, { stream }) => {
    // Stream partial results
    await stream.send({ type: "progress", data: "Thinking..." });
    await stream.send({ type: "progress", data: "Almost done..." });
    return { status: "completed", result: "Final answer" };
  },
});

server.start({ port: 3000 });
```

## Step 6: Client-Side Resumption

When a client reconnects, it provides the last received event ID:

```bash
# Initial connection
curl -N http://localhost:3000/tasks/task_123/stream

# After disconnect — resume from last event
curl -N -H "Last-Event-ID: 5" http://localhost:3000/tasks/task_123/stream
```

The stream store replays missed events from Valkey storage, then switches to live pub/sub delivery.

## How It Works

The resumable stream store uses two Valkey patterns together:

### 1. Key-Value for Stream State

Each active stream has metadata stored as a JSON string:

```text
resumable-stream:active:{userId}-{conversationId} → {"streamId": "...", ...}
```

The sequence number (managed via `INCR`) tracks how many events have been published. Clients use this as their `Last-Event-ID`.

### 2. Pub/Sub for Real-Time Delivery

New events are published to a channel matching the stream:

```text
PUBLISH resumable-stream:channel:{streamId} '{"seq":7,"type":"progress","data":"Thinking..."}'
```

Subscriber clients receive events in real-time. If a client disconnects and reconnects, the store:

1. Reads the stored events from key-value (events between client's last ID and current sequence)
2. Replays them immediately
3. Subscribes to the pub/sub channel for new events going forward

### 3. TTL for Cleanup

Active stream keys have a TTL. Once a stream completes or expires:

- The active key is removed (or expires)
- The subscriber client is unsubscribed and closed
- The pub/sub channel becomes idle (no resource cost)

## Configuration Reference

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `client` | `GlideClient \| GlideClusterClient` | — | Connected Valkey client instance (required) |
| `clientConfig` | `ValkeyConnectionConfig` | — | Connection config reused for per-channel subscription clients (required) |
| `keyPrefix` | `string` | `"resumable-stream"` | Key prefix for stream state |
| `ttlSeconds` | `number` | `undefined` | TTL for active stream keys |
| `maxSubscriptions` | `number` | `1000` | Maximum concurrent pub/sub subscriber connections |
| `waitUntil` | `function \| null` | `null` | Optional callback to keep the process alive during background work |

## Resource Considerations

Each active stream subscription consumes one Valkey client connection. Plan accordingly:

- **Valkey `maxclients`** — default is 10,000. With 100 concurrent streams, the store uses ~101 connections (100 subscribers + 1 publisher).
- **`maxSubscriptions`** — defaults to 1000 in the library. Set this below your Valkey `maxclients` limit, leaving room for the task store and other clients.
- **TTL** — shorter TTLs free connections faster but risk expiring streams that are still active. Match to your expected stream duration.

```bash
# Check current connection count
docker exec valkey valkey-cli INFO clients | grep connected_clients
```

## Troubleshooting

### "Max subscriptions reached" error

The store has hit the `maxSubscriptions` cap. Either:

- Increase the limit (ensure Valkey can handle the connections)
- Reduce stream TTL so completed streams release their connections faster
- Scale horizontally with multiple server instances

### Events missing after reconnect

Verify the stream state key still exists (hasn't expired):

```bash
docker exec valkey valkey-cli TTL "streams:active:task_123"
```

If it returns `-2`, the key expired. Increase `ttlSeconds` or ensure streams complete before the TTL.

### High connection count on Valkey

Each stream uses a dedicated connection. Monitor with:

```bash
docker exec valkey valkey-cli CLIENT LIST | wc -l
```

If connection count is too high, reduce `maxSubscriptions` or ensure streams are properly cleaned up on completion.

---

**Back to** [README](./README.md)
