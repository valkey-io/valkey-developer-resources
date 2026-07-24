# Streams Deep Dive: Consumer Groups and Reliability

> Understand how Valkey Streams provide at-least-once delivery, automatic message recovery, and distributed processing through consumer groups.

**Difficulty** · TypeScript · ~25 min

**Who is this for:** Developers who have completed the Getting Started guide and want to understand the reliability guarantees of Valkey Streams in a serverless environment.

## Prerequisites

- Completed [01 - Getting Started](./01-getting-started.md)
- Valkey running locally (`docker compose up -d` in `sample/`)

## Step 1: Consumer Groups Explained

A consumer group is a named set of consumers that cooperatively read from a stream. Each message is delivered to exactly one consumer in the group — enabling parallel processing without duplication.

```bash
# Inspect the consumer group (created automatically by the app)
docker exec valkey-vercel valkey-cli XINFO GROUPS contact-messages
```

Key properties:

- **Stream**: `contact-messages` — the ordered log of all messages
- **Group**: `contact-processors` — tracks which messages have been delivered
- **Consumer**: `consumer-{hostname}` — identifies each worker instance
- **Pending Entries List (PEL)**: Messages delivered but not yet acknowledged

## Step 2: The Message Lifecycle

```text
┌─────────────────────────────────────────────────────────────┐
│                    Message Lifecycle                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  POST /api/messages                                         │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    XADD                                       │
│  │ Stream  │◄──────────── Producer writes entry             │
│  └────┬────┘                                                │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    XREADGROUP / XAUTOCLAIM                     │
│  │   PEL   │◄──────────── Consumer receives entry           │
│  └────┬────┘                                                │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    XACK                                        │
│  │  Done   │◄──────────── Consumer acknowledges             │
│  └─────────┘                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Step 3: Creating the Consumer Group

The app creates the group on first read, handling the case where it already exists:

```typescript
const STREAM_NAME = 'contact-messages'
const CONSUMER_GROUP = 'contact-processors'

async function ensureConsumerGroup(client: GlideClient): Promise<void> {
  try {
    await client.xgroupCreate(STREAM_NAME, CONSUMER_GROUP, '0', { mkStream: true })
  } catch (error: unknown) {
    // BUSYGROUP means the group already exists — safe to ignore
    if (!(error instanceof Error && error.message.includes('BUSYGROUP'))) {
      throw error
    }
  }
}
```

- `'0'` means the group starts reading from the beginning of the stream
- `{ mkStream: true }` creates the stream if it doesn't exist yet

## Step 4: Auto-Claiming Idle Messages

In serverless environments, a function instance may crash or time out before acknowledging a message. `XAUTOCLAIM` solves this by reclaiming messages that have been pending longer than a threshold:

```typescript
const claimResponse = await client.xautoclaim(
  STREAM_NAME,
  CONSUMER_GROUP,
  CONSUMER_NAME,
  60000,    // Reclaim messages idle > 60 seconds
  '0-0',   // Start scanning from the beginning of the PEL
  { count: 1 }
)

const [_nextId, claimedMessages, _deletedIds] = claimResponse
```

The return value is a tuple:

1. **Next start ID** — use for paginated scanning (pass back on next call)
2. **Claimed messages** — `Record<string, [GlideString, GlideString][]>` mapping message IDs to field-value pairs
3. **Deleted IDs** (optional) — messages that were in the PEL but no longer exist in the stream

## Step 5: Reading New Messages

If no idle messages are claimed, read the next undelivered message:

```typescript
const response = await client.xreadgroup(
  CONSUMER_GROUP,
  CONSUMER_NAME,
  { [STREAM_NAME]: '>' },  // '>' means "messages never delivered to this group"
  { count: 1 }
)
```

The `>` ID is special — it means "give me messages that no consumer in this group has seen yet."

## Step 6: Acknowledging Messages

Once a message is processed successfully, acknowledge it to remove it from the PEL:

```typescript
await client.xack(STREAM_NAME, CONSUMER_GROUP, [messageId])
```

After acknowledgment, the message remains in the stream (for history/replay) but is no longer tracked as pending.

## Step 7: Observe the Stream

Use `valkey-cli` to inspect stream state:

```bash
# View all messages in the stream
docker exec valkey-vercel valkey-cli XRANGE contact-messages - +

# View pending messages (delivered but not acknowledged)
docker exec valkey-vercel valkey-cli XPENDING contact-messages contact-processors

# View stream info (length, groups, first/last entry)
docker exec valkey-vercel valkey-cli XINFO STREAM contact-messages

# View consumer info
docker exec valkey-vercel valkey-cli XINFO CONSUMERS contact-messages contact-processors
```

## How It Works: Reliability in Serverless

| Scenario | What Happens |
| -------- | ------------ |
| Function processes and acknowledges | Normal flow — message removed from PEL |
| Function crashes before acknowledging | Message stays in PEL; reclaimed after 60s by next `XAUTOCLAIM` |
| Function times out | Same as crash — PEL retains the message |
| Multiple instances running | Each gets different messages via consumer group |
| Duplicate delivery (rare) | Application should be idempotent |

## Configuration Reference

| Parameter | Value | Description |
| --------- | ----- | ----------- |
| `STREAM_NAME` | `contact-messages` | The Valkey Stream key |
| `CONSUMER_GROUP` | `contact-processors` | Consumer group name |
| `CONSUMER_NAME` | `consumer-{hostname}` | Unique per serverless instance |
| Idle threshold | `60000` ms | Time before auto-claiming |
| MAXLEN | `~10000` | Approximate stream cap |

## Teardown

```bash
# Reset the stream (removes all messages and groups)
docker exec valkey-vercel valkey-cli DEL contact-messages

# Or just remove the consumer group
docker exec valkey-vercel valkey-cli XGROUP DESTROY contact-messages contact-processors
```

---

[← Getting Started](./01-getting-started.md) | [Next: Production Deployment →](./03-production.md)
