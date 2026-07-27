# Vercel + Valkey Streams

> Deploy serverless message queues on Vercel using Valkey Streams for reliable, ordered message processing.

**Who is this for:** Full-stack TypeScript developers building Next.js applications that need background job processing, event-driven workflows, or reliable message delivery with Valkey.

## Cookbooks

| # | Title | Level | Time |
| --- | ----- | ----- | ---- |
| 01 | [Getting Started](./01-getting-started.md) | Beginner | ~20 min |
| 02 | [Streams Deep Dive](./02-streams-deep-dive.md) | Intermediate | ~25 min |
| 03 | [Production Deployment](./03-production.md) | Advanced | ~25 min |

## What You'll Build

A contact form processor that demonstrates reliable serverless message queuing:

- **Producer**: A form submission writes messages to a Valkey Stream
- **Consumer**: A processing view reads messages via consumer groups
- **Acknowledgment**: Processed messages are removed from the pending list

## Valkey Concepts Demonstrated

| Concept | Commands | Use Case |
| ------- | -------- | -------- |
| Streams | `XADD`, `XREADGROUP` | Ordered, persistent message log |
| Consumer Groups | `XGROUP CREATE`, `XAUTOCLAIM` | Distributed processing with at-least-once delivery |
| Acknowledgment | `XACK` | Mark messages as processed |
| Stream Trimming | `XADD ... MAXLEN ~` | Bounded memory usage |

## Prerequisites

- [Node.js](https://nodejs.org/) 20.19+ (LTS)
- [Docker](https://docs.docker.com/get-docker/) or [Finch](https://github.com/runfinch/finch) for running Valkey
- A code editor and terminal

## Quick Start

```bash
cd sample
docker compose up -d
npm install
npm run dev
# Visit http://localhost:3000
```

## References

- [Valkey Streams documentation](https://valkey.io/topics/streams-intro/)
- [Vercel template PR](https://github.com/vercel/examples/pull/1309) — upstream integration
- [@valkey/valkey-glide](https://github.com/valkey-io/valkey-glide) — official TypeScript client
