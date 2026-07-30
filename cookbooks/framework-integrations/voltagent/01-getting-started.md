# Getting Started with VoltAgent and Valkey

> Persist A2A task state in Valkey so your agent services survive restarts without losing in-flight work.

**Beginner** · TypeScript · ~15 min

**Who is this for:** Developers building AI agent services with VoltAgent who need durable task persistence beyond in-memory storage.

## Prerequisites

- Node.js 20+
- Docker (for running Valkey)
- A VoltAgent project (or willingness to create one)

> **Security note:** This guide runs Valkey without authentication for local development.
> Never expose an unprotected Valkey instance to the internet.
> See the [Valkey security documentation](https://valkey.io/topics/security/) for production hardening.

## Step 1: Start Valkey

VoltAgent's task store only uses SET/GET with JSON strings — no search module required:

```bash
docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey:9.1.0
```

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

Or use the provided docker-compose:

```bash
cd sample/
docker compose up -d
```

## Step 2: Install Packages

```bash
npm install @voltagent/a2a-server @valkey/valkey-glide
```

- `@voltagent/a2a-server` — A2A server with the ValkeyTaskStore factory
- `@valkey/valkey-glide` — official Valkey client (peer dependency, >=2.3.1)

## Step 3: Create the Task Store

```typescript
import { createValkeyTaskStore } from "@voltagent/a2a-server/valkey-store";

const taskStore = createValkeyTaskStore({
  addresses: [{ host: "localhost", port: 6379 }],
  prefix: "a2a:tasks",
  ttlSeconds: 86400, // 24 hours — tasks expire after this
});
```

The store persists tasks as JSON strings using the composite key pattern:

```text
{prefix}:{agentId}::{taskId}
```

For example: `a2a:tasks:weather-agent::task_abc123`

## Step 4: Wire into Your A2A Server

```typescript
import { A2AServer } from "@voltagent/a2a-server";
import { createValkeyTaskStore } from "@voltagent/a2a-server/valkey-store";

const taskStore = createValkeyTaskStore({
  addresses: [{ host: "localhost", port: 6379 }],
  prefix: "a2a:tasks",
  ttlSeconds: 86400,
});

const server = new A2AServer({
  agentId: "weather-agent",
  taskStore, // Valkey-backed persistence
  handler: async (task) => {
    // Your agent logic here
    return { status: "completed", result: "Sunny, 72°F" };
  },
});

server.start({ port: 3000 });
```

## Step 5: Verify Tasks Survive Restarts

1. Send a task to your agent:

```bash
curl -X POST http://localhost:3000/tasks \
  -H "Content-Type: application/json" \
  -d '{"input": "What is the weather in Austin?"}'
```

1. Check the task was stored in Valkey:

```bash
docker exec valkey valkey-cli KEYS "a2a:tasks:*"
# 1) "a2a:tasks:weather-agent::task_abc123"
```

1. Inspect the stored JSON:

```bash
docker exec valkey valkey-cli GET "a2a:tasks:weather-agent::task_abc123"
# {"id":"task_abc123","status":"completed","result":"Sunny, 72°F",...}
```

1. Restart your server — the task is still retrievable because it's in Valkey, not in-process memory.

## How It Works

The `ValkeyTaskStore` implementation is straightforward:

1. **SET** — When a task is created or updated, the entire task object is serialized to JSON and stored with `SET key value EX ttl`.
2. **GET** — When a task is retrieved, the JSON string is fetched and parsed back into the task object.
3. **Key pattern** — The composite key `{prefix}:{agentId}::{taskId}` ensures isolation between agents sharing the same Valkey instance.
   The `::` double-colon separator distinguishes the agentId from the taskId.
4. **TTL** — Optional time-to-live prevents abandoned tasks from consuming memory indefinitely.

## Configuration Reference

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `addresses` | `Array<{host, port}>` | — | Valkey server address(es) |
| `prefix` | `string` | `"voltagent:tasks"` | Key prefix for all task entries |
| `ttlSeconds` | `number` | `undefined` | Optional TTL in seconds for task keys |
| `clusterMode` | `boolean` | `false` | Enable cluster mode (uses GlideClusterClient) |
| `clientOptions` | `object` | `{}` | Additional valkey-glide client options |

## Troubleshooting

### Connection refused on port 6379

Ensure the Valkey container is running:

```bash
docker ps | grep valkey
```

If it's not listed, start it with the command from Step 1.

### Tasks disappear unexpectedly

Check the TTL setting. If `ttlSeconds` is set too low, tasks expire before you retrieve them:

```bash
docker exec valkey valkey-cli TTL "a2a:tasks:weather-agent::task_abc123"
```

### Key collisions between agents

Each agent must have a unique `agentId`. The composite key pattern ensures isolation:

```text
a2a:tasks:agent-one::task_1
a2a:tasks:agent-two::task_1  ← different key, no collision
```

---

**Next →** [02-resumable-streams.md](./02-resumable-streams.md)

**Back to** [README](./README.md)
