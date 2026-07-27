# Getting Started with Vercel + Valkey Streams

> Set up a Next.js application that uses Valkey Streams for reliable message queuing, running locally with a single `docker compose up`.

**Beginner** · TypeScript · ~20 min

**Who is this for:** Developers new to Valkey Streams who want to see a working message queue in a Next.js API route.

## Prerequisites

- [Node.js](https://nodejs.org/) 20.19+ (LTS)
- [Docker](https://docs.docker.com/get-docker/) or [Finch](https://github.com/runfinch/finch)
- Basic familiarity with Next.js App Router and TypeScript

## Step 1: Start Valkey

From the `sample/` directory:

```bash
cd cookbooks/framework-integrations/vercel/sample
docker compose up -d
```

> **🔒 Security:** The Docker Compose file binds Valkey to `127.0.0.1` only. Never expose Valkey directly to the public internet.
> In production, use network-level isolation (VPC, Secure Compute) and enable authentication with ACLs.

Verify Valkey is running:

```bash
docker exec valkey-vercel valkey-cli PING
# Expected: PONG
```

## Step 2: Install Dependencies and Start the App

```bash
npm install
npm run dev
```

Visit <http://localhost:3000> to see the contact form.

## Step 3: Understand the Architecture

The application has three API operations on a single route (`/api/messages`):

| Method | Action | Valkey Command |
| ------ | ------ | -------------- |
| `POST` | Produce a message | `XADD contact-messages ...` |
| `GET` | Consume next message | `XAUTOCLAIM` + `XREADGROUP` |
| `DELETE` | Acknowledge message | `XACK contact-messages contact-processors [id]` |

### Connecting to Valkey with GLIDE

The application uses `@valkey/valkey-glide`, the official TypeScript client:

```typescript
import { GlideClient, GlideClientConfiguration } from '@valkey/valkey-glide'

const endpoint = process.env.VALKEY_ENDPOINT || 'localhost:6379'
const [host, portStr] = endpoint.split(':')
const port = parseInt(portStr, 10)

const config: GlideClientConfiguration = {
  addresses: [{ host, port }],
  requestTimeout: 5000,
  clientName: 'vercel_message_queue_client',
}

const client = await GlideClient.createClient(config)
```

Key points:

- `clientName` sets `CLIENT SETNAME` — visible in `CLIENT LIST` for debugging
- `requestTimeout` prevents indefinite hangs on network issues
- The client is reused across requests (singleton pattern)

## Step 4: Produce a Message

Submit the contact form or use `curl`:

```bash
curl -X POST http://localhost:3000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "message": "Hello from Valkey Streams!"
  }'
```

Response:

```json
{
  "streamMessageId": "1764009314892-0",
  "timestamp": "2026-07-24T18:35:14.890Z"
}
```

Under the hood, this calls:

```typescript
const streamMessageId = await client.xadd(STREAM_NAME, [
  ['name', name],
  ['email', email],
  ['message', message],
  ['timestamp', timestamp],
], { trim: { method: "maxlen", threshold: 10000, exact: false } })
```

The `MAXLEN ~ 10000` option keeps the stream bounded — older entries are trimmed approximately when the stream exceeds 10,000 entries.

## Step 5: Consume and Acknowledge

Navigate to <http://localhost:3000/process> or use `curl`:

```bash
# Read next message
curl http://localhost:3000/api/messages

# Acknowledge it (use the streamMessageId from the response)
curl -X DELETE "http://localhost:3000/api/messages?messageId=1764009314892-0"
```

## Step 6: Run Tests

The sample includes tests that validate the API without a running Valkey instance (GLIDE is mocked):

```bash
npm test
```

Expected output: all tests pass.

## Configuration Reference

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VALKEY_ENDPOINT` | `localhost:6379` | Valkey server address in `host:port` format |

## Teardown

```bash
docker compose down -v
```

## What's Next

In the [next cookbook](./02-streams-deep-dive.md), we'll explore consumer groups, auto-claiming idle messages, and the full message lifecycle in detail.

---

[← README](./README.md) | [Next: Streams Deep Dive →](./02-streams-deep-dive.md)
